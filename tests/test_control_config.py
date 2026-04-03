from telegramautomation.config import parse_admin_chat_ids


def test_parse_admin_chat_ids_empty():
    assert parse_admin_chat_ids("") == tuple()


def test_parse_admin_chat_ids_values():
    assert parse_admin_chat_ids("123,-10011,  77") == (123, -10011, 77)
