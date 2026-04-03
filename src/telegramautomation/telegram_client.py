from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
import asyncio

from telethon import TelegramClient as TelethonClient
from telethon.errors import RPCError

from telegramautomation.models import PayloadType, TemplateRow
from telegramautomation.config import AppConfig

logger = logging.getLogger(__name__)

@dataclass(frozen=True)
class SentMessage:
    message_id: str
    sent_at: datetime

class TelegramClient:
    def __init__(self, config: AppConfig) -> None:
        self._cfg = config
        self._client = TelethonClient(
            self._cfg.telegram_session_name,
            self._cfg.telegram_api_id,
            self._cfg.telegram_api_hash,
            system_version="4.1.6",
            device_model="Desktop",
            app_version="1.0"
        )
        self.raw_client = self._client

    async def initialize(self) -> None:
        await self._client.connect()
        if not await self._client.is_user_authorized():
            raise RuntimeError("User is not authorized! Run python -m telegramautomation.auth to login.")
    
    async def destroy(self) -> None:
        await self._client.disconnect()

    async def send(
        self,
        target: str,
        payload_type: PayloadType,
        payload_ref: str | None,
        template: TemplateRow,
    ) -> SentMessage:
        if target.startswith("@"):
            target = target[1:]
        
        parse_mode = "html" if template.parse_mode and template.parse_mode.lower() == "html" else "md"

        try:
            if payload_type in {PayloadType.FILE, PayloadType.TEXT_FILE}:
                file_to_send = payload_ref or template.file_ref
                if not file_to_send:
                    raise ValueError(f"{payload_type.value} payload selected but file_ref is missing")
                
                msg = await self._client.send_file(
                    entity=target,
                    file=file_to_send,
                    caption=template.text or None,
                    parse_mode=parse_mode,
                )
            else:
                msg = await self._client.send_message(
                    entity=target,
                    message=template.text or "",
                    parse_mode=parse_mode,
                    link_preview=False,
                )
            
            return SentMessage(
                message_id=str(msg.id),
                sent_at=datetime.now(timezone.utc),
            )
        except RPCError as exc:
            raise RuntimeError(str(exc)) from exc
        except ValueError as exc:
            raise RuntimeError("User/entity not found or not registered on Telegram.") from exc
        except Exception as exc:
            raise RuntimeError(str(exc)) from exc
