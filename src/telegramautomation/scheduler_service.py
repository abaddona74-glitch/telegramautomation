from __future__ import annotations

import asyncio
import logging
import time
import threading

from apscheduler.schedulers.background import BackgroundScheduler
from googleapiclient.errors import HttpError

from telegramautomation.config import load_config, normalize_dispatch_settings
from telegramautomation.dispatcher import Dispatcher
from telegramautomation.sheet_grid import SheetGridFormatter
from telegramautomation.sheets_client import SheetsClient
from telegramautomation.storage import SQLiteStateStore
from telegramautomation.telegram_client import TelegramClient

logger = logging.getLogger(__name__)

class AppRuntime:
    def __init__(self) -> None:
        cfg = load_config()
        logging.basicConfig(
            level=getattr(logging, cfg.log_level.upper(), logging.INFO),
            format="%(asctime)s %(levelname)s %(name)s - %(message)s",
        )
        self._cfg = cfg
        self._sheets = SheetsClient(cfg)
        self._store = SQLiteStateStore(cfg.sqlite_path)
        self._grid_formatter = SheetGridFormatter(cfg)
        self._cycle_no = 0
        self._scheduler = BackgroundScheduler(timezone=self._cfg.timezone)
        
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._start_loop, daemon=True)
        self._thread.start()
        
        self._telegram: TelegramClient | None = None
        self._dispatcher: Dispatcher | None = None

    def _start_loop(self):
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    async def _async_init(self):
        self._telegram = TelegramClient(self._cfg)
        await self._telegram.initialize()
        self._dispatcher = Dispatcher(self._sheets, self._telegram, self._store)

    async def _async_cycle(self, settings):
        if not self._dispatcher:
            await self._async_init()
        await self._dispatcher.run_cycle(settings)

    def cycle(self) -> None:
        self._cycle_no += 1
        settings = normalize_dispatch_settings(self._sheets.load_settings())
        logger.info(
            "Cycle start | batch_size=%s interval_hours=%s min_delay_seconds=%s max_retries=%s",
            settings.batch_size,
            settings.interval_hours,
            settings.min_delay_seconds,
            settings.max_retries,
        )
        
        future = asyncio.run_coroutine_threadsafe(self._async_cycle(settings), self._loop)
        try:
            future.result()
        except Exception:
            logger.exception("Dispatch cycle failed")

        if self._cfg.enable_contacts_compact: # noqa
            try:
                removed = self._sheets.compact_contacts()
                if removed:
                    logger.info(f"Contacts compacted | removed_rows={removed}")
            except Exception:
                logger.exception("Contacts compaction failed")
        
        if self._cfg.enable_auto_grid_format and self._cycle_no % self._cfg.auto_grid_check_every_cycles == 0:
            try:
                changed = self._grid_formatter.apply_if_needed(force=False)
                if changed:
                    logger.info("Auto grid format updated")
            except HttpError as exc:
                if getattr(exc.resp, "status", None) == 429:
                    logger.warning("Auto grid format skipped due Sheets API quota")
                else:
                    logger.exception("Auto grid format update failed")
            except Exception:
                logger.exception("Auto grid format update failed")

    def run(self) -> None:
        future = asyncio.run_coroutine_threadsafe(self._async_init(), self._loop)
        try:
            future.result()
        except Exception as e:
            logger.error(f"Initialization failed: {e}")
            self._loop.call_soon_threadsafe(self._loop.stop)
            return

        self._scheduler.add_job(self.cycle, "interval", seconds=self._cfg.poll_interval_seconds)
        self.cycle()
        self._scheduler.start()

        logger.info("Agent mode running. Press Ctrl+C to stop.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Stopping scheduler")
            self._scheduler.shutdown(wait=False)
            self._loop.call_soon_threadsafe(self._loop.stop)

def run() -> None:
    app = AppRuntime()
    app.run()
