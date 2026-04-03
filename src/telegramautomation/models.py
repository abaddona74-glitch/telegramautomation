from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional


class PayloadType(str, Enum):
    TEXT = "text"
    FILE = "file"
    TEXT_FILE = "text_file"


class ContactState(str, Enum):
    PENDING = "pending"
    DELAYED = "delayed"
    RETRY = "retry"
    SENT = "sent"
    FAILED = "failed"


@dataclass(frozen=True)
class ContactRow:
    row_id: str
    username: Optional[str]
    phone: Optional[str]
    chat_id: Optional[str]
    template_id: str
    payload_type: PayloadType
    payload_ref: Optional[str]
    send_after: Optional[datetime]
    priority: int
    enabled: bool
    state: ContactState
    attempts: int


@dataclass(frozen=True)
class TemplateRow:
    template_id: str
    text: str
    file_ref: Optional[str]
    parse_mode: Optional[str]
    active: bool


@dataclass(frozen=True)
class DispatchResult:
    state: ContactState
    message_id: Optional[str]
    error: Optional[str]
    sent_at: Optional[datetime]
