from __future__ import annotations

import sys
from pathlib import Path

from dotenv import load_dotenv
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from telegramautomation.config import load_config  # noqa: E402

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

CONTACTS_HEADERS = [
    "row_id",
    "username",
    "phone",
    "chat_id",
    "template_id",
    "payload_type",
    "payload_ref",
    "send_after",
    "priority",
    "enabled",
    "state",
    "attempts",
    "last_error",
    "sent_at",
    "message_id",
]

TEMPLATES_HEADERS = ["template_id", "text", "file_ref", "parse_mode", "active"]
SETTINGS_HEADERS = ["key", "value"]


def main() -> None:
    load_dotenv(ROOT / ".env")
    cfg = load_config()

    creds = Credentials.from_service_account_file(cfg.google_service_account_file, scopes=SCOPES)
    service = build("sheets", "v4", credentials=creds, cache_discovery=False)

    _write_headers(service, cfg.google_sheet_id, cfg.contacts_sheet, CONTACTS_HEADERS)
    _write_headers(service, cfg.google_sheet_id, cfg.templates_sheet, TEMPLATES_HEADERS)
    _write_headers(service, cfg.google_sheet_id, cfg.settings_sheet, SETTINGS_HEADERS)

    _upsert_settings(service, cfg.google_sheet_id, cfg.settings_sheet)
    _upsert_templates(service, cfg.google_sheet_id, cfg.templates_sheet)
    _upsert_contacts(service, cfg.google_sheet_id, cfg.contacts_sheet)

    print("Sample data populated successfully.")


def _write_headers(service, sheet_id: str, sheet_name: str, headers: list[str]) -> None:
    service.spreadsheets().values().update(
        spreadsheetId=sheet_id,
        range=f"{sheet_name}!A1",
        valueInputOption="RAW",
        body={"values": [headers]},
    ).execute()


def _fetch_rows(service, sheet_id: str, sheet_name: str, cell_range: str) -> tuple[list[str], list[list[str]]]:
    result = service.spreadsheets().values().get(spreadsheetId=sheet_id, range=f"{sheet_name}!{cell_range}").execute()
    values = result.get("values", [])
    if not values:
        return [], []
    headers = values[0]
    rows = values[1:]
    return headers, rows


def _upsert_settings(service, sheet_id: str, sheet_name: str) -> None:
    _, rows = _fetch_rows(service, sheet_id, sheet_name, "A1:B1000")
    existing = {r[0].strip(): idx + 2 for idx, r in enumerate(rows) if r and r[0].strip()}

    required = {
        "batch_size": "20",
        "interval_hours": "24",
        "min_delay_seconds": "2",
        "max_retries": "2",
    }

    append_rows: list[list[str]] = []
    for key, value in required.items():
        if key in existing:
            row_no = existing[key]
            service.spreadsheets().values().update(
                spreadsheetId=sheet_id,
                range=f"{sheet_name}!B{row_no}",
                valueInputOption="RAW",
                body={"values": [[value]]},
            ).execute()
        else:
            append_rows.append([key, value])

    if append_rows:
        service.spreadsheets().values().append(
            spreadsheetId=sheet_id,
            range=f"{sheet_name}!A2:B2",
            valueInputOption="RAW",
            insertDataOption="INSERT_ROWS",
            body={"values": append_rows},
        ).execute()


def _upsert_templates(service, sheet_id: str, sheet_name: str) -> None:
    _, rows = _fetch_rows(service, sheet_id, sheet_name, "A1:E1000")
    existing = {r[0].strip() for r in rows if r and r[0].strip()}

    samples = [
        ["tpl_text_welcome", "Assalomu alaykum, bu test xabar.", "", "", "true"],
        ["tpl_text_reminder", "Eslatma: taklifimiz bugun amal qiladi.", "", "", "true"],
    ]

    to_add = [row for row in samples if row[0] not in existing]
    if to_add:
        service.spreadsheets().values().append(
            spreadsheetId=sheet_id,
            range=f"{sheet_name}!A2:E2",
            valueInputOption="RAW",
            insertDataOption="INSERT_ROWS",
            body={"values": to_add},
        ).execute()


def _upsert_contacts(service, sheet_id: str, sheet_name: str) -> None:
    _, rows = _fetch_rows(service, sheet_id, sheet_name, "A1:O2000")
    existing = {r[0].strip() for r in rows if r and r[0].strip()}

    samples = [
        [
            "demo_001",
            "",
            "",
            "",
            "tpl_text_welcome",
            "text",
            "",
            "",
            "1",
            "true",
            "pending",
            "0",
            "",
            "",
            "",
        ],
        [
            "demo_002",
            "",
            "",
            "",
            "tpl_text_reminder",
            "text",
            "",
            "",
            "2",
            "true",
            "pending",
            "0",
            "",
            "",
            "",
        ],
    ]

    to_add = [row for row in samples if row[0] not in existing]
    if to_add:
        service.spreadsheets().values().append(
            spreadsheetId=sheet_id,
            range=f"{sheet_name}!A2:O2",
            valueInputOption="RAW",
            insertDataOption="INSERT_ROWS",
            body={"values": to_add},
        ).execute()


if __name__ == "__main__":
    main()
