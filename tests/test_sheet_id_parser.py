from telegramautomation.config import extract_sheet_id_from_url, resolve_google_sheet_id


def test_extract_sheet_id_from_url():
    url = "https://docs.google.com/spreadsheets/d/1AbCDefGhIJKLmnOPQ_12345-xyz/edit#gid=0"
    assert extract_sheet_id_from_url(url) == "1AbCDefGhIJKLmnOPQ_12345-xyz"


def test_resolve_google_sheet_id_prefers_id():
    assert resolve_google_sheet_id("sheet-id-123", "") == "sheet-id-123"


def test_resolve_google_sheet_id_from_url():
    url = "https://docs.google.com/spreadsheets/d/abcXYZ_999/edit"
    assert resolve_google_sheet_id("", url) == "abcXYZ_999"
