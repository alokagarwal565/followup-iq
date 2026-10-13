"""Business errors raised by services; the API layer maps them to the error envelope."""

from typing import Any


class AppError(Exception):
    status_code = 400
    code = "bad_request"

    def __init__(
        self, message: str, *, code: str | None = None, details: dict[str, Any] | None = None
    ) -> None:
        super().__init__(message)
        self.message = message
        if code is not None:
            self.code = code
        self.details = details or {}


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"


class ConflictError(AppError):
    status_code = 409
    code = "conflict"


class UnprocessableError(AppError):
    status_code = 422
    code = "unprocessable"


class RateLimitedError(AppError):
    status_code = 429
    code = "rate_limited"


def lead_not_found() -> NotFoundError:
    return NotFoundError("Lead not found", code="lead_not_found")
