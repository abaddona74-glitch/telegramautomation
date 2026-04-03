from __future__ import annotations

import sys
import time
from pathlib import Path

from dotenv import load_dotenv
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from telegramautomation.config import load_config  # noqa: E402
from telegramautomation.scheduler_service import AppRuntime  # noqa: E402

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


def main() -> None:
    load_dotenv(ROOT / ".env")
    cfg = load_config()

    creds = Credentials.from_service_account_file(cfg.google_service_account_file, scopes=SCOPES)
    service = build("sheets", "v4", credentials=creds, cache_discovery=False)

    row_id = f"itest_{int(time.time())}"
    template_id = "tpl_integration_test"

    _append_template_if_missing(service, cfg.google_sheet_id, cfg.templates_sheet, template_id)
    _append_contact(service, cfg.google_sheet_id, cfg.contacts_sheet, row_id, template_id)

    app = AppRuntime()
    app.cycle()

    status = _get_contact_status(service, cfg.google_sheet_id, cfg.contacts_sheet, row_id)
    print(f"TEST_ROW_ID={row_id}")
    print(f"STATE={status.get('state', '')}")
    print(f"ATTEMPTS={status.get('attempts', '')}")
    print(f"LAST_ERROR={status.get('last_error', '')}")


def _append_template_if_missing(service, sheet_id: str, sheet_name: str, template_id: str) -> None:
    result = service.spreadsheets().values().get(spreadsheetId=sheet_id, range=f"{sheet_name}!A:A").execute()
    values = result.get("values", [])
    existing = {row[0].strip() for row in values[1:] if row and row[0].strip()}
    if template_id in existing:
        return

    service.spreadsheets().values().append(
        spreadsheetId=sheet_id,
        range=f"{sheet_name}!A:E",
        valueInputOption="RAW",
        insertDataOption="INSERT_ROWS",
        body={
            "values": [
                [
                    template_id,
                    "Salom, bu integratsiya test xabari.",
                    "",
                    "",
                    "true",
                ]
            ]
        },
    ).execute()


def _append_contact(service, sheet_id: str, sheet_name: str, row_id: str, template_id: str) -> None:
    # Empty target fields are intentional for safe integration verification (no real recipients messaged).
    service.spreadsheets().values().append(
        spreadsheetId=sheet_id,
        range=f"{sheet_name}!A:O",
        valueInputOption="RAW",
        insertDataOption="INSERT_ROWS",
        body={
            "values": [
                [
                    row_id,
                    "",
                    "",
                    "",
                    template_id,
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
                ]
            ]
        },
    ).execute()


def _get_contact_status(service, sheet_id: str, sheet_name: str, row_id: str) -> dict[str, str]:
    result = service.spreadsheets().values().get(spreadsheetId=sheet_id, range=f"{sheet_name}!A:O").execute()
    values = result.get("values", [])
    if not values:
        return {}

    headers = values[0]
    for raw in values[1:]:
        row = raw + [""] * max(0, len(headers) - len(raw))
        mapped = dict(zip(headers, row))
        if mapped.get("row_id", "").strip() == row_id:
            return mapped
    return {}


if __name__ == "__main__":
    main()
