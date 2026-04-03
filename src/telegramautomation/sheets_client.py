from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

from telegramautomation.config import AppConfig
from telegramautomation.models import ContactRow, ContactState, PayloadType, TemplateRow

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


@dataclass
class SheetTable:
    headers: list[str]
    rows: list[dict[str, str]]


class SheetsClient:
    def __init__(self, config: AppConfig) -> None:
        creds = Credentials.from_service_account_file(config.google_service_account_file, scopes=SCOPES)
        self._sheet_id = config.google_sheet_id
        self._service = build("sheets", "v4", credentials=creds, cache_discovery=False)
        self._contacts_sheet = config.contacts_sheet
        self._templates_sheet = config.templates_sheet
        self._settings_sheet = config.settings_sheet

    def load_contacts(self) -> list[ContactRow]:
        table = self._read_table(self._contacts_sheet)
        contacts: list[ContactRow] = []
        for row_number, row in enumerate(table.rows, start=2):
            has_identity = bool(_clean(row.get("username")) or _clean(row.get("phone")) or _clean(row.get("chat_id")))
            row_id_existing = row.get("row_id", "").strip()

            if (not has_identity) and row_id_existing.startswith("auto_"):
                self._clear_contact_row(table.headers, row_number)
                continue

            if has_identity:
                self._autofill_contact_defaults(table.headers, row, row_number)

            row_id = row.get("row_id", "").strip()

            state = _parse_state(row.get("state", "pending"))
            if not _parse_bool(row.get("enabled", "true")):
                continue
            if state not in {ContactState.PENDING, ContactState.RETRY, ContactState.DELAYED}:
                continue

            contacts.append(
                ContactRow(
                    row_id=row_id,
                    username=_clean(row.get("username")),
                    phone=_clean(row.get("phone")),
                    chat_id=_clean(row.get("chat_id")),
                    template_id=row.get("template_id", "").strip(),
                    payload_type=_parse_payload_type(row.get("payload_type", "text")),
                    payload_ref=_clean(row.get("payload_ref")),
                    send_after=_parse_datetime(row.get("send_after")),
                    priority=_parse_int(row.get("priority"), default=100),
                    enabled=True,
                    state=state,
                    attempts=_parse_int(row.get("attempts"), default=0),
                )
            )

        contacts.sort(key=lambda c: (c.priority, c.send_after or datetime.min))
        return [c for c in contacts if c.row_id and c.template_id]

    def _clear_contact_row(self, headers: list[str], row_number: int) -> None:
        if not headers:
            return
        end_col = _column_number_to_letter(len(headers))
        self._service.spreadsheets().values().clear(
            spreadsheetId=self._sheet_id,
            range=f"{self._contacts_sheet}!A{row_number}:{end_col}{row_number}",
            body={},
        ).execute()

    def _autofill_contact_defaults(self, headers: list[str], row: dict[str, str], row_number: int) -> None:
        updates: dict[str, str] = {}

        if not row.get("row_id", "").strip():
            updates["row_id"] = _generate_row_id(row_number)
        elif row.get("row_id", "").strip().startswith("auto_") and not _is_valid_auto_row_id(row.get("row_id", "").strip()):
            updates["row_id"] = _generate_row_id(row_number)
        if not row.get("payload_type", "").strip():
            updates["payload_type"] = "text"
        priority_current = row.get("priority", "").strip()
        if not priority_current or not _is_non_negative_int(priority_current):
            updates["priority"] = "100"
        else:
            priority_norm = str(int(priority_current))
            if priority_norm != priority_current:
                updates["priority"] = priority_norm

        enabled_current = row.get("enabled", "").strip()
        if not enabled_current:
            updates["enabled"] = "true"
        else:
            enabled_norm = "true" if enabled_current.lower() == "true" else "false"
            if enabled_norm != enabled_current.lower():
                updates["enabled"] = enabled_norm

        if not row.get("state", "").strip():
            updates["state"] = "pending"

        attempts_current = row.get("attempts", "").strip()
        if not attempts_current or not _is_non_negative_int(attempts_current):
            updates["attempts"] = "0"
        else:
            attempts_norm = str(int(attempts_current))
            if attempts_norm != attempts_current:
                updates["attempts"] = attempts_norm

        if not updates:
            return

        for key, value in updates.items():
            row[key] = value
            if key not in headers:
                continue
            col_index = headers.index(key)
            col_letter = _column_number_to_letter(col_index + 1)
            self._service.spreadsheets().values().update(
                spreadsheetId=self._sheet_id,
                range=f"{self._contacts_sheet}!{col_letter}{row_number}",
                valueInputOption="USER_ENTERED",
                body={"values": [[value]]},
            ).execute()

    def load_templates(self) -> dict[str, TemplateRow]:
        table = self._read_table(self._templates_sheet)
        output: dict[str, TemplateRow] = {}
        for row in table.rows:
            template_id = row.get("template_id", "").strip()
            if not template_id:
                continue
            active = _parse_bool(row.get("active", "true"))
            if not active:
                continue
            output[template_id] = TemplateRow(
                template_id=template_id,
                text=row.get("text", ""),
                file_ref=_clean(row.get("file_ref")),
                parse_mode=_clean(row.get("parse_mode")),
                active=active,
            )
        return output

    def load_settings(self) -> dict[str, str]:
        table = self._read_table(self._settings_sheet)
        settings: dict[str, str] = {}
        for row in table.rows:
            key = row.get("key", "").strip()
            if not key:
                continue
            settings[key] = row.get("value", "").strip()
        return settings

    def upsert_setting(self, key: str, value: str) -> None:
        table = self._read_table(self._settings_sheet)
        row_index = None
        for idx, row in enumerate(table.rows, start=2):
            if row.get("key", "").strip() == key:
                row_index = idx
                break

        if row_index is None:
            self._service.spreadsheets().values().append(
                spreadsheetId=self._sheet_id,
                range=f"{self._settings_sheet}!A2:B2",
                valueInputOption="RAW",
                insertDataOption="INSERT_ROWS",
                body={"values": [[key, value]]},
            ).execute()
            return

        self._service.spreadsheets().values().update(
            spreadsheetId=self._sheet_id,
            range=f"{self._settings_sheet}!B{row_index}",
            valueInputOption="RAW",
            body={"values": [[value]]},
        ).execute()

    def update_status(self, row_id: str, values: dict[str, str]) -> None:
        table = self._read_table(self._contacts_sheet)
        row_index = None
        for idx, row in enumerate(table.rows, start=2):
            if row.get("row_id", "").strip() == row_id:
                row_index = idx
                break

        if row_index is None:
            return

        for key, value in values.items():
            if key not in table.headers:
                continue
            col_index = table.headers.index(key)
            col_letter = _column_number_to_letter(col_index + 1)
            cell = f"{self._contacts_sheet}!{col_letter}{row_index}"
            self._service.spreadsheets().values().update(
                spreadsheetId=self._sheet_id,
                range=cell,
                valueInputOption="RAW",
                body={"values": [[value]]},
            ).execute()

    def _read_table(self, sheet_name: str) -> SheetTable:
        result = (
            self._service.spreadsheets()
            .values()
            .get(spreadsheetId=self._sheet_id, range=f"{sheet_name}!A:ZZ")
            .execute()
        )
        values = result.get("values", [])
        if not values:
            return SheetTable(headers=[], rows=[])
        headers = [v.strip() for v in values[0]]
        rows: list[dict[str, str]] = []
        for raw in values[1:]:
            normalized = [str(v) for v in raw] + [""] * max(0, len(headers) - len(raw))
            rows.append(dict(zip(headers, normalized)))
        return SheetTable(headers=headers, rows=rows)

    def compact_contacts(self) -> int:
        table = self._read_table(self._contacts_sheet)
        if not table.headers:
            return 0

        delete_rows: list[int] = []
        for row_number, row in enumerate(table.rows, start=2):
            if _should_delete_contact_row(row):
                delete_rows.append(row_number)

        if not delete_rows:
            return 0

        requests = []
        for row_number in sorted(delete_rows, reverse=True):
            requests.append(
                {
                    "deleteDimension": {
                        "range": {
                            "sheetId": self._sheet_id_by_title(self._contacts_sheet),
                            "dimension": "ROWS",
                            "startIndex": row_number - 1,
                            "endIndex": row_number,
                        }
                    }
                }
            )

        self._service.spreadsheets().batchUpdate(
            spreadsheetId=self._sheet_id,
            body={"requests": requests},
        ).execute()
        return len(delete_rows)

    def compact_templates(self) -> int:
        table = self._read_table(self._templates_sheet)
        if not table.headers:
            return 0

        delete_rows: list[int] = []
        for row_number, row in enumerate(table.rows, start=2):
            if _should_delete_template_row(row):
                delete_rows.append(row_number)

        if not delete_rows:
            return 0

        requests = []
        for row_number in sorted(delete_rows, reverse=True):
            requests.append(
                {
                    "deleteDimension": {
                        "range": {
                            "sheetId": self._sheet_id_by_title(self._templates_sheet),
                            "dimension": "ROWS",
                            "startIndex": row_number - 1,
                            "endIndex": row_number,
                        }
                    }
                }
            )

        self._service.spreadsheets().batchUpdate(
            spreadsheetId=self._sheet_id,
            body={"requests": requests},
        ).execute()
        return len(delete_rows)

    def _sheet_id_by_title(self, title: str) -> int:
        spreadsheet = self._service.spreadsheets().get(spreadsheetId=self._sheet_id).execute()
        for item in spreadsheet.get("sheets", []):
            props = item.get("properties", {})
            if props.get("title") == title:
                return int(props.get("sheetId"))
        raise ValueError(f"Sheet not found: {title}")


def _parse_bool(value: str) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def _parse_payload_type(value: str) -> PayloadType:
    val = value.strip().lower()
    if val == PayloadType.FILE.value:
        return PayloadType.FILE
    if val == PayloadType.TEXT_FILE.value:
        return PayloadType.TEXT_FILE
    return PayloadType.TEXT


def _parse_state(value: str) -> ContactState:
    val = value.strip().lower()
    for state in ContactState:
        if state.value == val:
            return state
    return ContactState.PENDING


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _parse_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    text = value.strip()
    return text or None


def _column_number_to_letter(column: int) -> str:
    letters: list[str] = []
    current = column
    while current > 0:
        current, remainder = divmod(current - 1, 26)
        letters.append(chr(65 + remainder))
    return "".join(reversed(letters))


def _generate_row_id(row_number: int) -> str:
    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    return f"auto_{timestamp}_{row_number}"


def _is_non_negative_int(value: str) -> bool:
    text = str(value).strip()
    return bool(text) and text.isdigit()


def _is_valid_auto_row_id(value: str) -> bool:
    text = str(value).strip()
    return text.startswith("auto_") and len(text.split("_")) >= 3


def _should_delete_contact_row(row: dict[str, str]) -> bool:
    row_id = (row.get("row_id") or "").strip()
    username = (row.get("username") or "").strip()
    phone = (row.get("phone") or "").strip()
    chat_id = (row.get("chat_id") or "").strip()
    template_id = (row.get("template_id") or "").strip()
    payload_type = (row.get("payload_type") or "").strip()
    payload_ref = (row.get("payload_ref") or "").strip()
    send_after = (row.get("send_after") or "").strip()
    last_error = (row.get("last_error") or "").strip()
    sent_at = (row.get("sent_at") or "").strip()
    message_id = (row.get("message_id") or "").strip()

    identity_empty = not (username or phone or chat_id)
    payload_empty = not (template_id or payload_type or payload_ref or send_after or last_error or sent_at or message_id)

    if identity_empty and payload_empty and not row_id:
        return True
    if identity_empty and payload_empty and row_id.startswith("auto_"):
        return True
    return False


def _should_delete_template_row(row: dict[str, str]) -> bool:
    template_id = (row.get("template_id") or "").strip()
    text = (row.get("text") or "").strip()
    file_ref = (row.get("file_ref") or "").strip()
    parse_mode = (row.get("parse_mode") or "").strip()

    # If there is no template identifier and no template payload, row is junk and can be removed.
    return not template_id and not text and not file_ref and not parse_mode
