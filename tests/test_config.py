from telegramautomation.config import normalize_dispatch_settings


def test_normalize_dispatch_settings_defaults():
    settings = normalize_dispatch_settings({})
    assert settings.batch_size == 20
    assert settings.interval_hours == 24
    assert settings.min_delay_seconds == 2
    assert settings.max_retries == 2


def test_normalize_dispatch_settings_minimums():
    settings = normalize_dispatch_settings(
        {
            "batch_size": "0",
            "interval_hours": "0",
            "min_delay_seconds": "-1",
            "max_retries": "-2",
        }
    )
    assert settings.batch_size == 1
    assert settings.interval_hours == 1
    assert settings.min_delay_seconds == 0
    assert settings.max_retries == 0
