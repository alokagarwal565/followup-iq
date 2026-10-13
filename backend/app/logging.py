import contextvars
import logging
import sys
from typing import Any

request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")


class _KeyValueFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        fields: dict[str, Any] = getattr(record, "fields", {})
        parts = [
            f"level={record.levelname.lower()}",
            f"logger={record.name}",
            f"request_id={request_id_var.get()}",
            f"msg={record.getMessage()!r}",
        ]
        parts += [f"{key}={value}" for key, value in fields.items()]
        if record.exc_info:
            # Exception class only: messages from DB drivers and SDKs can embed credentials or URLs.
            parts.append(f"exc_type={record.exc_info[0].__name__ if record.exc_info[0] else '-'}")
        return " ".join(parts)


def configure_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(_KeyValueFormatter())
    root = logging.getLogger("followupiq")
    root.handlers[:] = [handler]
    root.setLevel(level.upper())
    root.propagate = False


class EventLogger:
    """Structured `event=name key=value` lines are the only telemetry; keep event names stable."""

    def __init__(self, name: str) -> None:
        self._logger = logging.getLogger(f"followupiq.{name}")

    def info(self, event: str, **fields: Any) -> None:
        self._logger.info(event, extra={"fields": {"event": event, **fields}})

    def warning(self, event: str, **fields: Any) -> None:
        self._logger.warning(event, extra={"fields": {"event": event, **fields}})

    def error(self, event: str, *, exc_info: bool = False, **fields: Any) -> None:
        self._logger.error(event, exc_info=exc_info, extra={"fields": {"event": event, **fields}})


def get_logger(name: str) -> EventLogger:
    return EventLogger(name)
