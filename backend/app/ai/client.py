from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Literal, Protocol

from google import genai
from google.genai import types
from pydantic import SecretStr

from app.ai.schema import model_facing_schema


@dataclass(frozen=True)
class Turn:
    role: Literal["user", "model"]
    text: str


@dataclass(frozen=True)
class RawResponse:
    text: str
    finish_reason: str | None


class Caller(Protocol):
    async def generate(
        self, *, model: str, key_slot: int, api_key: SecretStr, system: str, turns: Sequence[Turn]
    ) -> RawResponse: ...


def thinking_level_for(model: str) -> types.ThinkingLevel | None:
    """Lowest useful thinking level per model family, per the Gemini thinking docs (Oct 2026).

    Classification plus a short draft needs little reasoning, and each level adds latency.
    Unknown or older families get no thinking config rather than a level they may reject.
    """
    if "flash-lite" in model and model.startswith(("gemini-3.5", "gemini-3.6", "gemini-3.8")):
        return types.ThinkingLevel.MINIMAL
    if model.startswith(("gemini-3.6-flash", "gemini-3.8-flash")):
        return types.ThinkingLevel.LOW
    return None


def build_config(model: str, system: str, timeout_seconds: float) -> types.GenerateContentConfig:
    level = thinking_level_for(model)
    kwargs: dict[str, Any] = {
        "system_instruction": system,
        "response_mime_type": "application/json",
        "response_json_schema": model_facing_schema(),
        # The SDK timeout is a socket-level backstop; the provider's asyncio.timeout is the real
        # per-attempt deadline because this one is not enforced as a total wall-clock limit.
        "http_options": types.HttpOptions(timeout=int(timeout_seconds * 1000)),
    }
    if level is not None:
        kwargs["thinking_config"] = types.ThinkingConfig(thinking_level=level)
    return types.GenerateContentConfig(**kwargs)


class GeminiCaller:
    """Thin adapter over google-genai; one client per key slot, reused across requests."""

    def __init__(self, timeout_seconds: float) -> None:
        self._timeout = timeout_seconds
        self._clients: dict[int, genai.Client] = {}

    def _client(self, key_slot: int, api_key: SecretStr) -> genai.Client:
        if key_slot not in self._clients:
            self._clients[key_slot] = genai.Client(api_key=api_key.get_secret_value())
        return self._clients[key_slot]

    async def generate(
        self, *, model: str, key_slot: int, api_key: SecretStr, system: str, turns: Sequence[Turn]
    ) -> RawResponse:
        contents = [
            types.Content(role=turn.role, parts=[types.Part(text=turn.text)]) for turn in turns
        ]
        response = await self._client(key_slot, api_key).aio.models.generate_content(
            model=model, contents=contents, config=build_config(model, system, self._timeout)
        )
        candidate = response.candidates[0] if response.candidates else None
        finish = candidate.finish_reason.name if candidate and candidate.finish_reason else None
        return RawResponse(text=response.text or "", finish_reason=finish)
