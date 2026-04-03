from __future__ import annotations

import argparse
from pathlib import Path

from dotenv import load_dotenv
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

from telegramautomation.config import extract_sheet_id_from_url

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
DEFAULT_SETTINGS = [
    ["batch_size", "20"],
    ["interval_hours", "24"],
    ["min_delay_seconds", "2"],
    ["max_retries", "2"],
]


def main() -> None:
    load_dotenv()
    args = _parse_args()

    service_account_file = args.service_account_file.strip()
    if not service_account_file:
        raise ValueError("--service-account-file is required")

    creds = Credentials.from_service_account_file(service_account_file, scopes=SCOPES)
    service = build("sheets", "v4", credentials=creds, cache_discovery=False)

    sheet_id = _resolve_sheet_id(args, service)
    _ensure_sheets(service, sheet_id, args.contacts_sheet, args.templates_sheet, args.settings_sheet)
    _ensure_headers(service, sheet_id, args.contacts_sheet, CONTACTS_HEADERS)
    _ensure_headers(service, sheet_id, args.templates_sheet, TEMPLATES_HEADERS)
    _ensure_headers(service, sheet_id, args.settings_sheet, SETTINGS_HEADERS)
    _ensure_default_settings(service, sheet_id, args.settings_sheet)

    if args.update_env:
        _update_env(Path(args.env_file), service_account_file=service_account_file, sheet_id=sheet_id)

    print("Bootstrap completed successfully.")
    print(f"Spreadsheet ID: {sheet_id}")
    print(f"Spreadsheet URL: https://docs.google.com/spreadsheets/d/{sheet_id}/edit")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Initialize Google Sheets structure for telegramautomation.")
    parser.add_argument("--service-account-file", required=True, help="Path to service account JSON")
    parser.add_argument("--sheet-id", default="", help="Existing Google Sheet ID")
    parser.add_argument("--sheet-url", default="", help="Google Sheet URL; ID will be auto-extracted")
    parser.add_argument("--create-sheet", action="store_true", help="Create a new sheet if ID/URL is not provided")
    parser.add_argument("--sheet-title", default="Telegram Automation", help="Title for created sheet")
    parser.add_argument("--contacts-sheet", default="contacts")
    parser.add_argument("--templates-sheet", default="templates")
    parser.add_argument("--settings-sheet", default="settings")
    parser.add_argument("--update-env", action="store_true", help="Write GOOGLE_SHEET_ID and GOOGLE_SERVICE_ACCOUNT_FILE into .env")
    parser.add_argument("--env-file", default=".env")
    return parser.parse_args()


def _resolve_sheet_id(args: argparse.Namespace, service) -> str:
    if args.sheet_id.strip():
        return args.sheet_id.strip()
    if args.sheet_url.strip():
        extracted = extract_sheet_id_from_url(args.sheet_url.strip())
        if extracted:
            return extracted
        raise ValueError("Invalid --sheet-url. Could not extract sheet ID")
    if args.create_sheet:
        response = (
            service.spreadsheets()
            .create(body={"properties": {"title": args.sheet_title.strip() or "Telegram Automation"}})
            .execute()
        )
        return response["spreadsheetId"]
    raise ValueError("Provide --sheet-id, --sheet-url, or --create-sheet")


def _ensure_sheets(service, sheet_id: str, contacts_sheet: str, templates_sheet: str, settings_sheet: str) -> None:
    spreadsheet = service.spreadsheets().get(spreadsheetId=sheet_id).execute()
    existing = {s["properties"]["title"] for s in spreadsheet.get("sheets", [])}
    missing = [name for name in [contacts_sheet, templates_sheet, settings_sheet] if name not in existing]
    if not missing:
        return

    requests = [{"addSheet": {"properties": {"title": name}}} for name in missing]
    service.spreadsheets().batchUpdate(spreadsheetId=sheet_id, body={"requests": requests}).execute()


def _ensure_headers(service, sheet_id: str, sheet_name: str, expected_headers: list[str]) -> None:
    result = (
        service.spreadsheets()
        .values()
        .get(spreadsheetId=sheet_id, range=f"{sheet_name}!1:1")
        .execute()
    )
    values = result.get("values", [])
    current = values[0] if values else []

    if current == expected_headers:
        return

    service.spreadsheets().values().update(
        spreadsheetId=sheet_id,
        range=f"{sheet_name}!A1",
        valueInputOption="RAW",
        body={"values": [expected_headers]},
    ).execute()


def _ensure_default_settings(service, sheet_id: str, settings_sheet: str) -> None:
    result = (
        service.spreadsheets()
        .values()
        .get(spreadsheetId=sheet_id, range=f"{settings_sheet}!A2:B999")
        .execute()
    )
    values = result.get("values", [])
    keys = {row[0].strip() for row in values if row and row[0].strip()}

    to_append = [row for row in DEFAULT_SETTINGS if row[0] not in keys]
    if not to_append:
        return

    service.spreadsheets().values().append(
        spreadsheetId=sheet_id,
        range=f"{settings_sheet}!A2:B2",
        valueInputOption="RAW",
        insertDataOption="INSERT_ROWS",
        body={"values": to_append},
    ).execute()


def _update_env(env_file: Path, service_account_file: str, sheet_id: str) -> None:
    if not env_file.exists():
        env_file.write_text("", encoding="utf-8")

    lines = env_file.read_text(encoding="utf-8").splitlines()
    lines = _upsert_env(lines, "GOOGLE_SERVICE_ACCOUNT_FILE", service_account_file)
    lines = _upsert_env(lines, "GOOGLE_SHEET_ID", sheet_id)
    env_file.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _upsert_env(lines: list[str], key: str, value: str) -> list[str]:
    needle = f"{key}="
    replaced = False
    output: list[str] = []
    for line in lines:
        if line.startswith(needle):
            output.append(f"{key}={value}")
            replaced = True
        else:
            output.append(line)

    if not replaced:
        output.append(f"{key}={value}")

    return output


if __name__ == "__main__":
    main()
