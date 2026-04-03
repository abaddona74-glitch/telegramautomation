from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from telegramautomation.config import DispatchSettings
from telegramautomation.models import ContactRow, ContactState, DispatchResult, TemplateRow
from telegramautomation.sheets_client import SheetsClient
from telegramautomation.storage import SQLiteStateStore
from telegramautomation.telegram_client import TelegramClient

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DispatchStats:
    processed: int = 0
    sent: int = 0
    delayed: int = 0
    failed: int = 0


class Dispatcher:
    def __init__(
        self,
        sheets: SheetsClient,
        telegram: TelegramClient,
        store: SQLiteStateStore,
    ) -> None:
        self._sheets = sheets
        self._telegram = telegram
        self._store = store

    async def run_cycle(self, settings: DispatchSettings) -> DispatchStats:
        templates = self._sheets.load_templates()
        contacts = self._sheets.load_contacts()
        if not contacts:
            logger.info("No pending contacts found")
            self._store.prune_old_events()
            return DispatchStats()

        now_utc = datetime.now(timezone.utc)
        sent_in_window = self._store.count_sent_in_window(settings.interval_hours, now_utc)
        remaining_capacity = max(0, settings.batch_size - sent_in_window)

        stats = DispatchStats(processed=0, sent=0, delayed=0, failed=0)

        for contact in contacts:
            if contact.send_after and contact.send_after.astimezone(timezone.utc) > now_utc:
                continue

            stats = DispatchStats(
                processed=stats.processed + 1,
                sent=stats.sent,
                delayed=stats.delayed,
                failed=stats.failed,
            )

            if remaining_capacity <= 0:
                self._delay_contact(contact, settings.interval_hours)
                stats = DispatchStats(
                    processed=stats.processed,
                    sent=stats.sent,
                    delayed=stats.delayed + 1,
                    failed=stats.failed,
                )
                continue

            template = templates.get(contact.template_id)
            if not template:
                self._mark_failed(contact, "template not found or inactive")
                stats = DispatchStats(
                    processed=stats.processed,
                    sent=stats.sent,
                    delayed=stats.delayed,
                    failed=stats.failed + 1,
                )
                continue

            result = await self._send_contact(contact, template, settings)

            if result.state == ContactState.SENT and result.sent_at:
                remaining_capacity -= 1
                self._store.register_send(contact.row_id, result.sent_at)
                stats = DispatchStats(
                    processed=stats.processed,
                    sent=stats.sent + 1,
                    delayed=stats.delayed,
                    failed=stats.failed,
                )
            elif result.state == ContactState.DELAYED:
                stats = DispatchStats(
                    processed=stats.processed,
                    sent=stats.sent,
                    delayed=stats.delayed + 1,
                    failed=stats.failed,
                )
            else:
                stats = DispatchStats(
                    processed=stats.processed,
                    sent=stats.sent,
                    delayed=stats.delayed,
                    failed=stats.failed + 1,
                )

            if settings.min_delay_seconds > 0:
                await asyncio.sleep(settings.min_delay_seconds)

        logger.info(
            "Dispatch cycle finished | processed=%s sent=%s delayed=%s failed=%s",
            stats.processed,
            stats.sent,
            stats.delayed,
            stats.failed,
        )
        return stats

    async def _send_contact(
        self,
        contact: ContactRow,
        template: TemplateRow,
        settings: DispatchSettings,
    ) -> DispatchResult:
        identity_error = self._validate_identity_fields(contact)
        if identity_error:
            self._mark_failed(contact, identity_error)
            return DispatchResult(ContactState.FAILED, None, identity_error, None)

        target = self._resolve_target(contact)
        if not target:
            self._mark_failed(contact, "target not resolvable (username/phone/chat_id missing)")
            return DispatchResult(ContactState.FAILED, None, "target not resolvable", None)

        try:
            sent = await self._telegram.send(
                target=target,
                payload_type=contact.payload_type,
                payload_ref=contact.payload_ref,
                template=template,
            )
            self._sheets.update_status(
                contact.row_id,
                {
                    "state": ContactState.SENT.value,
                    "sent_at": sent.sent_at.strftime("%Y-%m-%d %H:%M:%S"),
                    "last_error": "",
                    "message_id": sent.message_id,
                    "attempts": contact.attempts + 1,
                },
            )
            return DispatchResult(ContactState.SENT, sent.message_id, None, sent.sent_at)
        except Exception as exc:  # noqa: BLE001
            next_attempt = contact.attempts + 1
            if next_attempt <= settings.max_retries:
                self._sheets.update_status(
                    contact.row_id,
                    {
                        "state": ContactState.RETRY.value,
                        "last_error": str(exc),
                        "attempts": next_attempt,
                    },
                )
                return DispatchResult(ContactState.RETRY, None, str(exc), None)

            self._mark_failed(contact, str(exc), attempts=next_attempt)
            return DispatchResult(ContactState.FAILED, None, str(exc), None)

    def _mark_failed(self, contact: ContactRow, reason: str, attempts: int | None = None) -> None:
        self._sheets.update_status(
            contact.row_id,
            {
                "state": ContactState.FAILED.value,
                "last_error": reason,
                "attempts": attempts if attempts is not None else contact.attempts + 1,
    def _delay_contact(self, contact: ContactRow, interval_hours: int) -> None:
        next_time = datetime.now(timezone.utc) + timedelta(hours=interval_hours)
        self._sheets.update_status(
            contact.row_id,
            {
                "state": ContactState.DELAYED.value,
                "send_after": next_time.strftime("%Y-%m-%d %H:%M:%S"),
                "last_error": "",
            },
        )

    @staticmethod
    def _resolve_target(contact: ContactRow) -> str | None:
        if contact.chat_id:
            return contact.chat_id
        if contact.username:
            username = contact.username if contact.username.startswith("@") else f"@{contact.username}"
            return username
        if contact.phone:
            # Telethon allows phone numbers
            return contact.phone
        return None

    @staticmethod
    def _validate_identity_fields(contact: ContactRow) -> str | None:
        has_username = bool(contact.username)
        has_phone = bool(contact.phone)
        has_chat_id = bool(contact.chat_id)

        if not (has_username or has_phone or has_chat_id):
            return "No identifier provided. Needs username, phone, or chat_id."

        identifiers = sum([has_username, has_phone, has_chat_id])
        if identifiers > 1 and not has_chat_id:
             # Just note it but let it pass. We'll prioritize chat_id > username > phone
             pass

        return None
