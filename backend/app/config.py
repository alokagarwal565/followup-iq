from pathlib import Path
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, SecretStr, ValidationError, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# The backend reads only its own env file; env files elsewhere in the repo are never consulted.
BACKEND_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"

DEFAULT_MODEL_HEAVY = "gemini-3.6-flash"
DEFAULT_MODEL_FALLBACK_HEAVY = "gemini-3.8-flash"
DEFAULT_MODEL_FAST = "gemini-3.5-flash-lite"
DEFAULT_MODEL_FALLBACK_FAST = "gemini-3.1-flash-lite"


class ConfigError(RuntimeError):
    """Startup configuration problem; the message names variables, never their values."""


def _csv(value: str | None) -> list[str]:
    return [part.strip() for part in (value or "").split(",") if part.strip()]


def _dedupe(items: list[str]) -> list[str]:
    return list(dict.fromkeys(items))


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore", case_sensitive=False)

    env: Literal["development", "test", "production"] = "development"
    database_url: SecretStr
    # Optional Postgres schema for an isolated environment (e.g. local dev on a shared database).
    database_schema: str | None = Field(default=None, pattern=r"^[a-z_][a-z0-9_]{0,62}$")
    test_database_url: SecretStr | None = None
    business_tz: str = "Asia/Kolkata"
    cors_origins: str = "http://localhost:3000"
    cors_origin_regex: str | None = None
    log_level: str = "INFO"

    gemini_api_key: SecretStr | None = None
    gemini_api_key_2: SecretStr | None = None
    gemini_api_key_3: SecretStr | None = None
    gemini_api_key_fallbacks: SecretStr | None = None
    gemini_model_heavy: str = DEFAULT_MODEL_HEAVY
    gemini_model_fallback_heavy: str = DEFAULT_MODEL_FALLBACK_HEAVY
    gemini_model_fast: str = DEFAULT_MODEL_FAST
    gemini_model_fallback_fast: str = DEFAULT_MODEL_FALLBACK_FAST
    gemini_model_chain: str | None = None
    gemini_request_timeout_seconds: float = Field(default=20.0, gt=0, le=120)
    gemini_analysis_deadline_seconds: float = Field(default=60.0, gt=0, le=300)
    gemini_max_retries: int = Field(default=1, ge=0, le=3)
    gemini_retry_backoff_base_seconds: float = Field(default=0.5, ge=0, le=10)
    gemini_max_attempts: int = Field(default=8, ge=1, le=20)
    gemini_fake: bool = False

    rate_limit_writes_per_min: int = Field(default=60, ge=1)
    rate_limit_analyze_per_min: int = Field(default=10, ge=1)
    max_body_bytes: int = Field(default=64 * 1024, ge=1024)

    @field_validator("database_url", "test_database_url")
    @classmethod
    def _must_be_postgres(cls, value: SecretStr | None) -> SecretStr | None:
        if value is not None and not value.get_secret_value().startswith(
            ("postgres://", "postgresql://")
        ):
            raise ValueError("must be a postgres:// or postgresql:// URL")
        return value

    @field_validator("business_tz")
    @classmethod
    def _must_be_iana_zone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError("must be an IANA timezone name") from exc
        return value

    @model_validator(mode="after")
    def _fake_ai_never_in_production(self) -> "Settings":
        # The fake provider returns canned analyses; serving it publicly misrepresents AI output.
        if self.env == "production" and self.gemini_fake:
            raise ValueError("GEMINI_FAKE cannot be enabled when ENV=production")
        return self

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.business_tz)

    @property
    def gemini_keys(self) -> list[SecretStr]:
        slots = [self.gemini_api_key, self.gemini_api_key_2, self.gemini_api_key_3]
        raw = [s.get_secret_value().strip() for s in slots if s is not None]
        if self.gemini_api_key_fallbacks is not None:
            raw += _csv(self.gemini_api_key_fallbacks.get_secret_value())
        return [SecretStr(k) for k in _dedupe([k for k in raw if k])]

    @property
    def gemini_models(self) -> list[str]:
        if self.gemini_model_chain:
            return _dedupe(_csv(self.gemini_model_chain))
        tiers = [
            self.gemini_model_heavy,
            self.gemini_model_fallback_heavy,
            self.gemini_model_fast,
            self.gemini_model_fallback_fast,
        ]
        return _dedupe([m.strip() for m in tiers if m.strip()])

    @property
    def cors_origin_list(self) -> list[str]:
        return _csv(self.cors_origins)

    @property
    def ai_configured(self) -> bool:
        return self.gemini_fake or bool(self.gemini_keys)


def load_settings(env_file: Path | None = BACKEND_ENV_FILE) -> Settings:
    try:
        return Settings(_env_file=env_file)
    except ValidationError as exc:
        # Report variable names and reasons only; pydantic's default message can echo input values.
        problems = []
        for err in exc.errors():
            name = ".".join(str(p) for p in err["loc"]).upper() or "SETTINGS"
            problems.append(f"{name}: {err['msg']}")
        raise ConfigError("Invalid configuration -> " + "; ".join(problems)) from None
