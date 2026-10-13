import pytest

from app.config import ConfigError, load_settings

BASE = {"DATABASE_URL": "postgresql://u:p@localhost:5432/db"}


def make(monkeypatch: pytest.MonkeyPatch, **env: str):
    for key in list(__import__("os").environ):
        if key.startswith(("GEMINI_", "DATABASE_URL", "ENV", "CORS_", "BUSINESS_TZ")):
            monkeypatch.delenv(key, raising=False)
    for key, value in {**BASE, **env}.items():
        monkeypatch.setenv(key, value)
    return load_settings(env_file=None)


def test_gemini_keys_follow_slot_order_and_drop_duplicates(monkeypatch):
    s = make(
        monkeypatch,
        GEMINI_API_KEY="k1",
        GEMINI_API_KEY_2="k2",
        GEMINI_API_KEY_3="k1",
        GEMINI_API_KEY_FALLBACKS=" k4 , ,k2",
    )
    assert [k.get_secret_value() for k in s.gemini_keys] == ["k1", "k2", "k4"]


def test_default_model_chain_is_heavy_then_fast(monkeypatch):
    s = make(monkeypatch)
    assert s.gemini_models == [
        "gemini-3.6-flash",
        "gemini-3.8-flash",
        "gemini-3.5-flash-lite",
        "gemini-3.1-flash-lite",
    ]


def test_model_chain_override_replaces_tiers(monkeypatch):
    s = make(monkeypatch, GEMINI_MODEL_CHAIN="a, b ,a", GEMINI_MODEL_HEAVY="ignored")
    assert s.gemini_models == ["a", "b"]


def test_missing_database_url_fails_with_variable_name(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(ConfigError, match="DATABASE_URL"):
        load_settings(env_file=None)


def test_non_postgres_database_url_is_rejected(monkeypatch):
    with pytest.raises(ConfigError, match="DATABASE_URL"):
        make(monkeypatch, DATABASE_URL="mysql://x")


def test_config_error_never_contains_secret_values(monkeypatch):
    with pytest.raises(ConfigError) as exc:
        make(monkeypatch, DATABASE_URL="mysql://user:supersecret@h/db")
    assert "supersecret" not in str(exc.value)


def test_fake_ai_is_refused_in_production(monkeypatch):
    with pytest.raises(ConfigError, match="GEMINI_FAKE"):
        make(monkeypatch, ENV="production", GEMINI_FAKE="1")


def test_cors_origins_parse_from_csv(monkeypatch):
    s = make(monkeypatch, CORS_ORIGINS="https://a.app, http://localhost:3000")
    assert s.cors_origin_list == ["https://a.app", "http://localhost:3000"]


def test_invalid_business_timezone_is_rejected(monkeypatch):
    with pytest.raises(ConfigError, match="BUSINESS_TZ"):
        make(monkeypatch, BUSINESS_TZ="Mars/Olympus")
