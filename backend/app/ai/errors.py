import re
from dataclasses import dataclass
from typing import Any, Literal

import httpx
from google.genai import errors as genai_errors

Category = Literal[
    "auth",
    "rate_limited",
    "model_unavailable",
    "transient",
    "timeout",
    "invalid_request",
    "safety_blocked",
    "malformed_output",
    "exhausted",
    "unconfigured",
]

_RETRY_INFO = "type.googleapis.com/google.rpc.RetryInfo"
_QUOTA_FAILURE = "type.googleapis.com/google.rpc.QuotaFailure"
_DURATION = re.compile(r"^\s*(\d+(?:\.\d+)?)s\s*$")


@dataclass(frozen=True)
class ProviderError:
    category: Category
    retry_after: float | None = None
    # A quota of zero means this key's project has no access to this model at all.
    quota_zero: bool = False


def _error_details(exc: genai_errors.APIError) -> list[dict[str, Any]]:
    body = exc.details if isinstance(exc.details, dict) else {}
    error = body.get("error", body)
    details = error.get("details", []) if isinstance(error, dict) else []
    return [d for d in details if isinstance(d, dict)]


def _retry_after(details: list[dict[str, Any]]) -> float | None:
    for detail in details:
        if detail.get("@type") == _RETRY_INFO:
            match = _DURATION.match(str(detail.get("retryDelay", "")))
            if match:
                return float(match.group(1))
    return None


def _quota_is_zero(details: list[dict[str, Any]]) -> bool:
    for detail in details:
        if detail.get("@type") == _QUOTA_FAILURE:
            for violation in detail.get("violations", []):
                if str(violation.get("quotaValue", "")).strip() == "0":
                    return True
    return False


def classify_exception(exc: BaseException) -> ProviderError:
    """Maps SDK and transport failures to categories using status codes, not message text."""
    if isinstance(exc, genai_errors.APIError):
        code, status = exc.code, (exc.status or "").upper()
        details = _error_details(exc)
        if code in (401, 403):
            return ProviderError("auth")
        if code == 429:
            return ProviderError(
                "rate_limited",
                retry_after=_retry_after(details),
                quota_zero=_quota_is_zero(details),
            )
        # 503 means the model is temporarily overloaded: retry briefly before abandoning it.
        if code == 404 or (code == 400 and status == "FAILED_PRECONDITION"):
            return ProviderError("model_unavailable")
        if code == 400:
            return ProviderError("invalid_request")
        return ProviderError("transient")
    if isinstance(exc, httpx.TransportError | ConnectionError | OSError):
        return ProviderError("transient")
    # Unknown failures get the bounded transient path rather than an immediate hard stop.
    return ProviderError("transient")


_KEY_PARAM = re.compile(r"(key=)[^&\s'\"]+", re.IGNORECASE)


def redact(text: str, secrets: list[str]) -> str:
    """Strips API keys from text that may be logged; SDK errors can echo request URLs."""
    for secret in secrets:
        if secret:
            text = text.replace(secret, "[redacted]")
    return _KEY_PARAM.sub(r"\1[redacted]", text)
