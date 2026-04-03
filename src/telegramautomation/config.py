from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class AppConfig:
    telegram_session_name: str
    telegram_api_id: int
    telegram_api_hash: str
    google_service_account_file: str
    google_sheet_id: str
    contacts_sheet: str
    templates_sheet: str
    settings_sheet: str
    timezone: str
    sqlite_path: str
    poll_interval_seconds: int
    log_level: str
    enable_telegram_control: bool
    admin_chat_ids: tuple[int, ...]
    enable_auto_grid_format: bool
    auto_grid_check_every_cycles: int
    enable_contacts_compact: bool


@dataclass(frozen=True)
class DispatchSettings:
    batch_size: int
    interval_hours: int
    min_delay_seconds: int
    max_retries: int


def load_config() -> AppConfig:
    load_dotenv()

    sheet_id = resolve_google_sheet_id(
        sheet_id=os.getenv("GOOGLE_SHEET_ID", ""),
        sheet_url=os.getenv("GOOGLE_SHEET_URL", ""),
    )

    api_id_env = _required("TELEGRAM_API_ID")
    if not api_id_env.isdigit():
        raise ValueError("TELEGRAM_API_ID must be a number")

    cfg = AppConfig(
        telegram_session_name=os.getenv("TELEGRAM_SESSION_NAME", "session"),    
        telegram_api_id=int(api_id_env),
        telegram_api_hash=_required("TELEGRAM_API_HASH"),
        google_service_account_file=_required("GOOGLE_SERVICE_ACCOUNT_FILE"),
        google_sheet_id=sheet_id,
        contacts_sheet=os.getenv("CONTACTS_SHEET", "contacts"),
        templates_sheet=os.getenv("TEMPLATES_SHEET", "templates"),
        settings_sheet=os.getenv("SETTINGS_SHEET", "settings"),
        timezone=os.getenv("TIMEZONE", "Asia/Tashkent"),
        sqlite_path=os.getenv("SQLITE_PATH", "runtime/state.db"),
        poll_interval_seconds=int(os.getenv("POLL_INTERVAL_SECONDS", "60")),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
        enable_telegram_control=_parse_bool_env("ENABLE_TELEGRAM_CONTROL", default=True),
        admin_chat_ids=parse_admin_chat_ids(os.getenv("ADMIN_CHAT_IDS", "")),
        enable_auto_grid_format=_parse_bool_env("ENABLE_AUTO_GRID_FORMAT", default=True),
        auto_grid_check_every_cycles=max(1, int(os.getenv("AUTO_GRID_CHECK_EVERY_CYCLES", "1"))),
        enable_contacts_compact=_parse_bool_env("ENABLE_CONTACTS_COMPACT", default=True),
    )

    sqlite_parent = Path(cfg.sqlite_path).parent
    sqlite_parent.mkdir(parents=True, exist_ok=True)
    return cfg


def normalize_dispatch_settings(raw: dict[str, str]) -> DispatchSettings:
    def _get_int(key: str, default: int) -> int:
        value = raw.get(key)
        if value is None or value == "":
            return default
        return int(value)

    batch_size = max(1, _get_int("batch_size", 20))
    interval_hours = max(1, _get_int("interval_hours", 24))
    min_delay_seconds = max(0, _get_int("min_delay_seconds", 2))
    max_retries = max(0, _get_int("max_retries", 2))

    return DispatchSettings(
        batch_size=batch_size,
        interval_hours=interval_hours,
        min_delay_seconds=min_delay_seconds,
        max_retries=max_retries,
    )


def _required(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise ValueError(f"Missing required environment variable: {name}")
    return value


def resolve_google_sheet_id(sheet_id: str, sheet_url: str) -> str:
    normalized_id = (sheet_id or "").strip()
    if normalized_id:
        return normalized_id

    url = (sheet_url or "").strip()
    if url:
        extracted = extract_sheet_id_from_url(url)
        if extracted:
            return extracted

    raise ValueError("Missing Google Sheet identifier. Set GOOGLE_SHEET_ID or GOOGLE_SHEET_URL")


def extract_sheet_id_from_url(url: str) -> str | None:
    match = re.search(r"/spreadsheets/d/([a-zA-Z0-9-_]+)", url)
    if not match:
        return None
    return match.group(1)


def parse_admin_chat_ids(raw: str) -> tuple[int, ...]:
    if not raw.strip():
        return tuple()

    ids: list[int] = []
    for chunk in raw.split(","):
        text = chunk.strip()
        if not text:
            continue
        ids.append(int(text))
    return tuple(ids)


def _parse_bool_env(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}
