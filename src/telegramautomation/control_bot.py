from __future__ import annotations

import asyncio
import logging
from typing import Callable

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from telegramautomation.config import AppConfig
from telegramautomation.sheets_client import SheetsClient

logger = logging.getLogger(__name__)

_ALLOWED_KEYS = {"batch_size", "interval_hours", "min_delay_seconds", "max_retries"}


class ControlBot:
    def __init__(
        self,
        config: AppConfig,
        sheets: SheetsClient,
        run_once_callback: Callable[[], None],
    ) -> None:
        self._config = config
        self._sheets = sheets
        self._run_once_callback = run_once_callback
        self._admin_chat_ids = set(config.admin_chat_ids)
        self._app = Application.builder().token(config.telegram_bot_token).build()
        self._register_handlers()

    def _register_handlers(self) -> None:
        self._app.add_handler(CommandHandler("help", self._help))
        self._app.add_handler(CommandHandler("settings", self._settings))
        self._app.add_handler(CommandHandler("set", self._set_key_value))
        self._app.add_handler(CommandHandler("setbatch", self._set_batch))
        self._app.add_handler(CommandHandler("setinterval", self._set_interval))
        self._app.add_handler(CommandHandler("setdelay", self._set_delay))
        self._app.add_handler(CommandHandler("setretries", self._set_retries))
        self._app.add_handler(CommandHandler("runonce", self._run_once))

    def run(self) -> None:
        logger.info("Telegram control bot polling started")
        # asyncio.run in dispatch cycles can close the default loop; recreate it for polling.
        try:
            asyncio.get_event_loop()
        except RuntimeError:
            asyncio.set_event_loop(asyncio.new_event_loop())
        self._app.run_polling(close_loop=False)

    async def _help(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not self._is_allowed(update):
            return
        text = (
            "Commands:\n"
            "/settings - current dispatch settings\n"
            "/set <key> <value> - update setting in Google Sheets\n"
            "/setbatch <n>\n"
            "/setinterval <hours>\n"
            "/setdelay <seconds>\n"
            "/setretries <n>\n"
            "/runonce - trigger one dispatch cycle now"
        )
        await update.effective_message.reply_text(text)

    async def _settings(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not self._is_allowed(update):
            return
        settings = self._sheets.load_settings()
        lines = [f"{key}={settings.get(key, '')}" for key in sorted(_ALLOWED_KEYS)]
        await update.effective_message.reply_text("\n".join(lines))

    async def _set_key_value(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not self._is_allowed(update):
            return
        if len(context.args) != 2:
            await update.effective_message.reply_text("Usage: /set <key> <value>")
            return

        key, value = context.args[0].strip(), context.args[1].strip()
        await self._update_setting(update, key, value)

    async def _set_batch(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await self._set_short(update, context, "batch_size")

    async def _set_interval(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await self._set_short(update, context, "interval_hours")

    async def _set_delay(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await self._set_short(update, context, "min_delay_seconds")

    async def _set_retries(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await self._set_short(update, context, "max_retries")

    async def _set_short(self, update: Update, context: ContextTypes.DEFAULT_TYPE, key: str) -> None:
        if not self._is_allowed(update):
            return
        if len(context.args) != 1:
            await update.effective_message.reply_text(f"Usage: /{update.effective_message.text.split()[0][1:]} <value>")
            return
        await self._update_setting(update, key, context.args[0].strip())

    async def _run_once(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not self._is_allowed(update):
            return
        try:
            self._run_once_callback()
        except Exception as exc:  # noqa: BLE001
            logger.exception("runonce failed")
            await update.effective_message.reply_text(f"Run failed: {exc}")
            return

        await update.effective_message.reply_text("Dispatch cycle started.")

    async def _update_setting(self, update: Update, key: str, value: str) -> None:
        if key not in _ALLOWED_KEYS:
            await update.effective_message.reply_text("Allowed keys: batch_size, interval_hours, min_delay_seconds, max_retries")
            return

        if not value.isdigit():
            await update.effective_message.reply_text("Value must be non-negative integer")
            return

        normalized = str(max(0, int(value)))
        if key in {"batch_size", "interval_hours"}:
            normalized = str(max(1, int(normalized)))

        self._sheets.upsert_setting(key, normalized)
        await update.effective_message.reply_text(f"Updated {key}={normalized} in Google Sheets")

    def _is_allowed(self, update: Update) -> bool:
        if not update.effective_chat:
            return False
        chat_id = update.effective_chat.id

        if self._admin_chat_ids and chat_id not in self._admin_chat_ids:
            if update.effective_message:
                # Restrict command usage to configured admins.
                return False
            return False
        return True
