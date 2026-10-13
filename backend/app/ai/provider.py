"""Bounded model-and-key fallback for one analysis.

Order: models are the outer loop, keys the inner loop. Each failure category decides whether to
retry the same pair, try the next key, try the next model, or stop. A global attempt budget and
an overall deadline bound the whole call, and known-bad keys and models are never retried within
the same request.
"""

import asyncio
import random
import time
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass

from pydantic import SecretStr

from app.ai.client import Caller, RawResponse, Turn
from app.ai.errors import Category, ProviderError, classify_exception, redact
from app.ai.prompt import build_repair_prompt
from app.logging import get_logger

log = get_logger("ai.provider")

# Waiting longer than this for a rate limit is pointless inside an interactive request; a long
# RetryInfo usually means a daily quota, so moving to another key or model is the better bet.
MAX_HONOURED_RETRY_SECONDS = 5.0


@dataclass(frozen=True)
class Valid[T]:
    value: T


@dataclass(frozen=True)
class Invalid:
    category: Category
    problem: str


@dataclass(frozen=True)
class ProviderConfig:
    models: Sequence[str]
    keys: Sequence[SecretStr]
    attempt_timeout_seconds: float
    deadline_seconds: float
    max_attempts: int
    max_transient_retries: int
    backoff_base_seconds: float


@dataclass(frozen=True)
class ProviderResult[T]:
    value: T
    model: str
    key_slot: int
    attempts: int


class AnalysisFailed(Exception):
    def __init__(self, category: Category, attempts: int) -> None:
        super().__init__(category)
        self.category = category
        self.attempts = attempts


class _NextModel(Exception):
    pass


async def run_with_fallback[T](
    *,
    system: str,
    prompt: str,
    validate: Callable[[str, str | None], Valid[T] | Invalid],
    caller: Caller,
    config: ProviderConfig,
    lead_id: str,
    clock: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> ProviderResult[T]:
    if not config.keys or not config.models:
        log.warning("ai_unconfigured", lead_id=lead_id)
        raise AnalysisFailed("unconfigured", attempts=0)

    secrets = [k.get_secret_value() for k in config.keys]
    deadline = clock() + config.deadline_seconds
    attempts = 0
    dead_keys: set[int] = set()
    dead_pairs: set[tuple[str, int]] = set()

    for model in config.models:
        try:
            for slot, key in enumerate(config.keys, start=1):
                if slot in dead_keys or (model, slot) in dead_pairs:
                    continue
                turns = [Turn("user", prompt)]
                transient_retries = 0
                repaired = False
                waited_for_rate_limit = False
                while True:
                    remaining = deadline - clock()
                    if attempts >= config.max_attempts or remaining <= 0:
                        log.warning("ai_exhausted", lead_id=lead_id, attempts=attempts)
                        raise AnalysisFailed("exhausted", attempts)
                    attempts += 1
                    started = clock()
                    error, raw = await _attempt(
                        caller, model, slot, key, system, turns, config, remaining
                    )
                    if raw is not None:
                        outcome = validate(raw.text, raw.finish_reason)
                        if isinstance(outcome, Valid):
                            _log_attempt(lead_id, model, slot, attempts, started, clock, "success")
                            return ProviderResult(outcome.value, model, slot, attempts)
                        error = ProviderError(outcome.category)
                        problem = outcome.problem
                    else:
                        problem = ""
                    assert error is not None
                    _log_attempt(
                        lead_id, model, slot, attempts, started, clock, error.category, secrets
                    )

                    match error.category:
                        case "auth":
                            dead_keys.add(slot)
                            break
                        case "rate_limited":
                            if error.quota_zero:
                                dead_pairs.add((model, slot))
                                break
                            delay = error.retry_after
                            if (
                                delay is not None
                                and not waited_for_rate_limit
                                and delay <= MAX_HONOURED_RETRY_SECONDS
                                and delay < deadline - clock()
                            ):
                                waited_for_rate_limit = True
                                await sleep(delay)
                                continue
                            break
                        case "model_unavailable" | "timeout":
                            # Neither is key-specific, so rotating keys on this model wastes budget.
                            raise _NextModel
                        case "transient":
                            if transient_retries < config.max_transient_retries:
                                transient_retries += 1
                                backoff = config.backoff_base_seconds * 2 ** (transient_retries - 1)
                                await sleep(backoff * random.uniform(0.5, 1.5))  # noqa: S311 (jitter, not crypto)
                                continue
                            raise _NextModel
                        case "invalid_request":
                            raise AnalysisFailed("invalid_request", attempts)
                        case "safety_blocked" | "malformed_output":
                            if repaired:
                                raise _NextModel
                            repaired = True
                            turns = _repair_turns(prompt, raw, problem)
                            continue
                        case _:
                            raise AnalysisFailed(error.category, attempts)
        except _NextModel:
            continue

    log.warning("ai_exhausted", lead_id=lead_id, attempts=attempts)
    raise AnalysisFailed("exhausted", attempts)


async def _attempt(
    caller: Caller,
    model: str,
    slot: int,
    key: SecretStr,
    system: str,
    turns: list[Turn],
    config: ProviderConfig,
    remaining: float,
) -> tuple[ProviderError | None, RawResponse | None]:
    budget = min(config.attempt_timeout_seconds, remaining)
    try:
        async with asyncio.timeout(budget) as scope:
            raw = await caller.generate(
                model=model, key_slot=slot, api_key=key, system=system, turns=turns
            )
        return None, raw
    except TimeoutError:
        # Only our own deadline counts as a timeout; a TimeoutError raised inside the SDK is
        # a transport failure and goes through the transient path instead.
        return (ProviderError("timeout") if scope.expired() else ProviderError("transient")), None
    except Exception as exc:
        return classify_exception(exc), None


def _repair_turns(prompt: str, raw: RawResponse | None, problem: str) -> list[Turn]:
    turns = [Turn("user", prompt)]
    if raw is not None and raw.text.strip():
        turns.append(Turn("model", raw.text))
    # Gemini 3 rejects requests whose last turn is the model's, so the correction is a user turn.
    turns.append(Turn("user", build_repair_prompt(problem or "The answer was blocked or empty.")))
    return turns


def _log_attempt(
    lead_id: str,
    model: str,
    slot: int,
    attempt: int,
    started: float,
    clock: Callable[[], float],
    outcome: str,
    secrets: list[str] | None = None,
) -> None:
    fields = {
        "lead_id": lead_id,
        "model": redact(model, secrets or []),
        "key_slot": slot,
        "attempt": attempt,
        "duration_ms": int((clock() - started) * 1000),
        "outcome": outcome,
    }
    if outcome == "success":
        log.info("ai_attempt", **fields)
    else:
        log.warning("ai_attempt", **fields)
