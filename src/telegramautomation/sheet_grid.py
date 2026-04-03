from __future__ import annotations

from dataclasses import dataclass, field
import hashlib

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

from telegramautomation.config import AppConfig

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


@dataclass
class GridState:
    last_end_rows: dict[str, int] = field(default_factory=dict)
    last_signatures: dict[str, str] = field(default_factory=dict)


class SheetGridFormatter:
    def __init__(self, config: AppConfig) -> None:
        self._cfg = config
        creds = Credentials.from_service_account_file(config.google_service_account_file, scopes=SCOPES)
        self._service_account_email = creds.service_account_email
        self._service = build("sheets", "v4", credentials=creds, cache_discovery=False)
        self._state = GridState()

    def apply_if_needed(self, force: bool = False) -> bool:
        spreadsheet = self._service.spreadsheets().get(spreadsheetId=self._cfg.google_sheet_id).execute()
        sheets_meta = {
            item["properties"]["title"]: item
            for item in spreadsheet.get("sheets", [])
        }
        sheet_ids = {title: meta["properties"]["sheetId"] for title, meta in sheets_meta.items()}

        targets = [
            (self._cfg.contacts_sheet, 15),
            (self._cfg.templates_sheet, 5),
            (self._cfg.settings_sheet, 2),
        ]

        changed = False
        for title, col_count in targets:
            sheet_id = sheet_ids.get(title)
            if sheet_id is None:
                continue
            end_row = self._detect_end_row(title, col_count)
            signature = self._build_signature(title, col_count, end_row)
            if (
                (not force)
                and self._state.last_end_rows.get(title) == end_row
                and self._state.last_signatures.get(title) == signature
            ):
                continue
            self._format_sheet(title, sheet_id, col_count, end_row)
            self._state.last_end_rows[title] = end_row
            self._state.last_signatures[title] = signature
            changed = True

        contacts_meta = sheets_meta.get(self._cfg.contacts_sheet)
        if contacts_meta:
            if self._ensure_row_id_protection(contacts_meta):
                changed = True

        return changed

    def _format_sheet(self, title: str, sheet_id: int, col_count: int, end_row: int) -> None:
        max_rows = max(2, end_row)
        black = {"red": 0.0, "green": 0.0, "blue": 0.0}
        requests = [
            {
                "updateSheetProperties": {
                    "properties": {
                        "sheetId": sheet_id,
                        "gridProperties": {"frozenRowCount": 1},
                    },
                    "fields": "gridProperties.frozenRowCount",
                }
            },
            {
                "repeatCell": {
                    "range": {
                        "sheetId": sheet_id,
                        "startRowIndex": 0,
                        "endRowIndex": 1,
                        "startColumnIndex": 0,
                        "endColumnIndex": col_count,
                    },
                    "cell": {
                        "userEnteredFormat": {
                            "textFormat": {"bold": True, "foregroundColor": {"red": 1, "green": 1, "blue": 1}},
                            "backgroundColor": {"red": 0.17, "green": 0.17, "blue": 0.17},
                            "horizontalAlignment": "CENTER",
                        }
                    },
                    "fields": "userEnteredFormat(textFormat,backgroundColor,horizontalAlignment)",
                }
            },
            {
                "repeatCell": {
                    "range": {
                        "sheetId": sheet_id,
                        "startRowIndex": 0,
                        "endRowIndex": max_rows,
                        "startColumnIndex": 0,
                        "endColumnIndex": col_count,
                    },
                    "cell": {
                        "userEnteredFormat": {
                            "borders": {
                                "top": {"style": "SOLID_MEDIUM", "color": black},
                                "bottom": {"style": "SOLID_MEDIUM", "color": black},
                                "left": {"style": "SOLID_MEDIUM", "color": black},
                                "right": {"style": "SOLID_MEDIUM", "color": black},
                            }
                        }
                    },
                    "fields": "userEnteredFormat.borders",
                }
            },
            {
                "updateBorders": {
                    "range": {
                        "sheetId": sheet_id,
                        "startRowIndex": 0,
                        "endRowIndex": max_rows,
                        "startColumnIndex": 0,
                        "endColumnIndex": col_count,
                    },
                    "top": {"style": "SOLID_MEDIUM", "color": black},
                    "bottom": {"style": "SOLID_MEDIUM", "color": black},
                    "left": {"style": "SOLID_MEDIUM", "color": black},
                    "right": {"style": "SOLID_MEDIUM", "color": black},
                    "innerHorizontal": {"style": "SOLID_MEDIUM", "color": black},
                    "innerVertical": {"style": "SOLID_MEDIUM", "color": black},
                }
            },
            {
                "setBasicFilter": {
                    "filter": {
                        "range": {
                            "sheetId": sheet_id,
                            "startRowIndex": 0,
                            "endRowIndex": max_rows,
                            "startColumnIndex": 0,
                            "endColumnIndex": col_count,
                        }
                    }
                }
            },
            {
                "updateDimensionProperties": {
                    "range": {
                        "sheetId": sheet_id,
                        "dimension": "COLUMNS",
                        "startIndex": 0,
                        "endIndex": col_count,
                    },
                    "properties": {
                        "pixelSize": 110,
                    },
                    "fields": "pixelSize",
                }
            },
        ]

        if title == self._cfg.contacts_sheet and col_count >= 13:
            # last_error column text in red for visibility.
            requests.append(
                {
                    "repeatCell": {
                        "range": {
                            "sheetId": sheet_id,
                            "startRowIndex": 1,
                            "endRowIndex": max_rows,
                            "startColumnIndex": 12,
                            "endColumnIndex": 13,
                        },
                        "cell": {
                            "userEnteredFormat": {
                                "textFormat": {
                                    "foregroundColor": {"red": 0.8, "green": 0.1, "blue": 0.1}
                                }
                            }
                        },
                        "fields": "userEnteredFormat.textFormat.foregroundColor",
                    }
                }
            )

        if title == self._cfg.contacts_sheet:
            requests.extend(self._contacts_column_width_requests(sheet_id))

        requests.extend(self._boolean_color_requests(title, sheet_id, col_count, max_rows))
        if title == self._cfg.contacts_sheet:
            requests.extend(self._state_color_requests(sheet_id, max_rows))
            requests.extend(self._contacts_validation_requests(sheet_id, max_rows))
        elif title == self._cfg.templates_sheet:
            requests.extend(self._templates_validation_requests(sheet_id, max_rows))

        self._service.spreadsheets().batchUpdate(
            spreadsheetId=self._cfg.google_sheet_id,
            body={"requests": requests},
        ).execute()

    def _detect_end_row(self, sheet_name: str, col_count: int) -> int:
        if sheet_name == self._cfg.contacts_sheet:
            # Use row_id + identity columns so lower rows with username are included.
            range_expr = f"{sheet_name}!A1:C"
        elif sheet_name == self._cfg.templates_sheet:
            # Template IDs in column A define actual rows.
            range_expr = f"{sheet_name}!A1:A"
        elif sheet_name == self._cfg.settings_sheet:
            range_expr = f"{sheet_name}!A1:B"
        else:
            last_col = _column_number_to_letter(col_count)
            range_expr = f"{sheet_name}!A1:{last_col}"

        values = (
            self._service.spreadsheets()
            .values()
            .get(spreadsheetId=self._cfg.google_sheet_id, range=range_expr)
            .execute()
            .get("values", [])
        )
        return len(values) + 1

    def _build_signature(self, sheet_name: str, col_count: int, end_row: int) -> str:
        if sheet_name != self._cfg.contacts_sheet:
            return str(end_row)

        values = (
            self._service.spreadsheets()
            .values()
            .get(
                spreadsheetId=self._cfg.google_sheet_id,
                range=f"{sheet_name}!J2:M{max(2, end_row)}",
            )
            .execute()
            .get("values", [])
        )
        raw = f"{end_row}|{values}"
        return hashlib.sha1(raw.encode("utf-8")).hexdigest()

    def _boolean_color_requests(self, sheet_name: str, sheet_id: int, col_count: int, max_rows: int) -> list[dict]:
        last_col = _column_number_to_letter(col_count)
        values = (
            self._service.spreadsheets()
            .values()
            .get(spreadsheetId=self._cfg.google_sheet_id, range=f"{sheet_name}!A2:{last_col}{max_rows}")
            .execute()
            .get("values", [])
        )

        requests: list[dict] = []
        for row_offset, row in enumerate(values, start=2):
            for col_offset in range(col_count):
                value = row[col_offset].strip().lower() if len(row) > col_offset else ""
                if value not in {"true", "false"}:
                    continue

                if value == "true":
                    bg = {"red": 0.85, "green": 0.95, "blue": 0.85}
                    fg = {"red": 0.12, "green": 0.45, "blue": 0.12}
                else:
                    bg = {"red": 0.98, "green": 0.86, "blue": 0.86}
                    fg = {"red": 0.72, "green": 0.1, "blue": 0.1}

                requests.append(
                    {
                        "repeatCell": {
                            "range": {
                                "sheetId": sheet_id,
                                "startRowIndex": row_offset - 1,
                                "endRowIndex": row_offset,
                                "startColumnIndex": col_offset,
                                "endColumnIndex": col_offset + 1,
                            },
                            "cell": {
                                "userEnteredFormat": {
                                    "backgroundColor": bg,
                                    "textFormat": {"foregroundColor": fg, "bold": True},
                                    "horizontalAlignment": "CENTER",
                                }
                            },
                            "fields": "userEnteredFormat(backgroundColor,textFormat,horizontalAlignment)",
                        }
                    }
                )

        return requests

    def _state_color_requests(self, sheet_id: int, max_rows: int) -> list[dict]:
        values = (
            self._service.spreadsheets()
            .values()
            .get(spreadsheetId=self._cfg.google_sheet_id, range=f"{self._cfg.contacts_sheet}!K2:K{max_rows}")
            .execute()
            .get("values", [])
        )

        requests: list[dict] = []
        for idx, row in enumerate(values, start=2):
            state = row[0].strip().lower() if row else ""
            if state in {"failed"}:
                bg = {"red": 0.98, "green": 0.84, "blue": 0.84}
                fg = {"red": 0.72, "green": 0.1, "blue": 0.1}
            elif state in {"pending", "retry", "delayed"}:
                bg = {"red": 0.84, "green": 0.9, "blue": 0.98}
                fg = {"red": 0.1, "green": 0.3, "blue": 0.72}
            elif state in {"sent", "success"}:
                bg = {"red": 0.85, "green": 0.95, "blue": 0.85}
                fg = {"red": 0.12, "green": 0.45, "blue": 0.12}
            else:
                continue

            requests.append(
                {
                    "repeatCell": {
                        "range": {
                            "sheetId": sheet_id,
                            "startRowIndex": idx - 1,
                            "endRowIndex": idx,
                            "startColumnIndex": 10,
                            "endColumnIndex": 11,
                        },
                        "cell": {
                            "userEnteredFormat": {
                                "backgroundColor": bg,
                                "textFormat": {"foregroundColor": fg, "bold": True},
                                "horizontalAlignment": "CENTER",
                            }
                        },
                        "fields": "userEnteredFormat(backgroundColor,textFormat,horizontalAlignment)",
                    }
                }
            )

        return requests

    def _contacts_validation_requests(self, sheet_id: int, max_rows: int) -> list[dict]:
        template_values = self._template_id_options()
        username_values = self._username_options()
        tail_start = max_rows
        tail_end = 2000
        return [
            {
                "setDataValidation": {
                    "range": {
                        "sheetId": sheet_id,
                        "startRowIndex": tail_start,
                        "endRowIndex": tail_end,
                        "startColumnIndex": 1,
                        "endColumnIndex": 2,
                    },
                    "rule": None,
                }
            },
            {
                "setDataValidation": {
                    "range": {
                        "sheetId": sheet_id,
                        "startRowIndex": 1,
                        "endRowIndex": max_rows,
                        "startColumnIndex": 1,
                        "endColumnIndex": 2,
                    },
                    "rule": {
                        "condition": {
                            "type": "ONE_OF_LIST",
                            "values": username_values,
                        },
                        "strict": False,
                        "showCustomUi": True,
                    },
                }
            },
            {
                "setDataValidation": {
                    "range": {
                        "sheetId": sheet_id,
                        "startRowIndex": 1,
                        "endRowIndex": max_rows,
                        "startColumnIndex": 4,
                        "endColumnIndex": 5,
                    },
                    "rule": {
                        "condition": {
                            "type": "ONE_OF_LIST",
                            "values": template_values,
                        },
                        "strict": True,
                        "showCustomUi": True,
                    },
                }
            },
            {
                "setDataValidation": {
                    "range": {
                        "sheetId": sheet_id,
                        "startRowIndex": 1,
                        "endRowIndex": max_rows,
                        "startColumnIndex": 8,
                        "endColumnIndex": 9,
                    },
                    "rule": {
                        "condition": {
                            "type": "NUMBER_GREATER_THAN_EQ",
                            "values": [{"userEnteredValue": "0"}],
                        },
                        "strict": True,
                        "showCustomUi": True,
                    },
                }
            },
            {
                "setDataValidation": {
                    "range": {
                        "sheetId": sheet_id,
                        "startRowIndex": 1,
                        "endRowIndex": max_rows,
                        "startColumnIndex": 11,
                        "endColumnIndex": 12,
                    },
                    "rule": {
                        "condition": {
                            "type": "NUMBER_GREATER_THAN_EQ",
                            "values": [{"userEnteredValue": "0"}],
                        },
                        "strict": True,
                        "showCustomUi": True,
                    },
                }
            },
            {
                "setDataValidation": {
                    "range": {
                        "sheetId": sheet_id,
                        "startRowIndex": 1,
                        "endRowIndex": max_rows,
                        "startColumnIndex": 9,
                        "endColumnIndex": 10,
                    },
                    "rule": {
                        "condition": {
                            "type": "BOOLEAN",
                        },
                        "strict": True,
                        "showCustomUi": True,
                    },
                }
            },
            {
                "setDataValidation": {
                    "range": {
                        "sheetId": sheet_id,
                        "startRowIndex": 1,
                        "endRowIndex": max_rows,
                        "startColumnIndex": 10,
                        "endColumnIndex": 11,
                    },
                    "rule": {
                        "condition": {
                            "type": "ONE_OF_LIST",
                            "values": [
                                {"userEnteredValue": "pending"},
                                {"userEnteredValue": "retry"},
                                {"userEnteredValue": "delayed"},
                                {"userEnteredValue": "failed"},
                                {"userEnteredValue": "sent"},
                                {"userEnteredValue": "success"},
                            ],
                        },
                        "strict": True,
                        "showCustomUi": True,
                    },
                }
            },
            {
                "setDataValidation": {
                    "range": {
                        "sheetId": sheet_id,
                        "startRowIndex": tail_start,
                        "endRowIndex": tail_end,
                        "startColumnIndex": 1,
                        "endColumnIndex": 2,
                    },
                    "rule": None,
                }
            },
            {
                "setDataValidation": {
                    "range": {
                        "sheetId": sheet_id,
                        "startRowIndex": tail_start,
                        "endRowIndex": tail_end,
                        "startColumnIndex": 4,
                        "endColumnIndex": 5,
                    },
                    "rule": None,
                }
            },
            {
                "setDataValidation": {
                    "range": {
                        "sheetId": sheet_id,
                        "startRowIndex": tail_start,
                        "endRowIndex": tail_end,
                        "startColumnIndex": 8,
                        "endColumnIndex": 12,
                    },
                    "rule": None,
                }
            },
        ]

    def _template_id_options(self) -> list[dict[str, str]]:
        values = (
            self._service.spreadsheets()
            .values()
            .get(spreadsheetId=self._cfg.google_sheet_id, range=f"{self._cfg.templates_sheet}!A2:E")
            .execute()
            .get("values", [])
        )

        out: list[dict[str, str]] = []
        seen: set[str] = set()
        for row in values:
            template_id = row[0].strip() if len(row) > 0 else ""
            active = row[4].strip().lower() if len(row) > 4 else ""
            if not template_id:
                continue
            if active not in {"", "true", "1", "yes", "y"}:
                continue
            if template_id in seen:
                continue
            seen.add(template_id)
            out.append({"userEnteredValue": template_id})

        if not out:
            out.append({"userEnteredValue": "tpl_default"})
        return out

    def _username_options(self) -> list[dict[str, str]]:
        values = (
            self._service.spreadsheets()
            .values()
            .get(spreadsheetId=self._cfg.google_sheet_id, range=f"{self._cfg.contacts_sheet}!B2:B")
            .execute()
            .get("values", [])
        )

        out: list[dict[str, str]] = []
        seen: set[str] = set()
        for row in values:
            username = row[0].strip() if row else ""
            if not username:
                continue
            if username in seen:
                continue
            seen.add(username)
            out.append({"userEnteredValue": username})

        if not out:
            out.append({"userEnteredValue": "@username"})
        return out

    def _contacts_column_width_requests(self, sheet_id: int) -> list[dict]:
        # Bugun qo'shilgan o'zgarish: tizim siz tortgan o'lchamni joyiga qaytarib qoymasligi uchun buni bo'sh ro'yxat qoldiramiz.
        return []

    def _templates_validation_requests(self, sheet_id: int, max_rows: int) -> list[dict]:
        tail_start = max_rows
        tail_end = 2000
        return [
            {
                "setDataValidation": {
                    "range": {
                        "sheetId": sheet_id,
                        "startRowIndex": 1,
                        "endRowIndex": max_rows,
                        "startColumnIndex": 4,
                        "endColumnIndex": 5,
                    },
                    "rule": {
                        "condition": {
                            "type": "BOOLEAN",
                        },
                        "strict": True,
                        "showCustomUi": True,
                    },
                }
            },
            {
                "setDataValidation": {
                    "range": {
                        "sheetId": sheet_id,
                        "startRowIndex": tail_start,
                        "endRowIndex": tail_end,
                        "startColumnIndex": 4,
                        "endColumnIndex": 5,
                    },
                    "rule": None,
                }
            }
        ]

    def _ensure_row_id_protection(self, contacts_meta: dict) -> bool:
        protections = contacts_meta.get("protectedRanges", [])
        for item in protections:
            if item.get("description") == "telegramautomation-row-id-lock":
                return False

        sheet_id = contacts_meta["properties"]["sheetId"]
        request = {
            "addProtectedRange": {
                "protectedRange": {
                    "description": "telegramautomation-row-id-lock",
                    "range": {
                        "sheetId": sheet_id,
                        "startRowIndex": 1,
                        "startColumnIndex": 0,
                        "endColumnIndex": 1,
                    },
                    "warningOnly": False,
                    "editors": {
                        "users": [self._service_account_email],
                    },
                }
            }
        }
        self._service.spreadsheets().batchUpdate(
            spreadsheetId=self._cfg.google_sheet_id,
            body={"requests": [request]},
        ).execute()
        return True


def _column_number_to_letter(column: int) -> str:
    letters: list[str] = []
    current = column
    while current > 0:
        current, remainder = divmod(current - 1, 26)
        letters.append(chr(65 + remainder))
    return "".join(reversed(letters))
