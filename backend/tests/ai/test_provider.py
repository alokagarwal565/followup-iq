import asyncio
import logging
from collections.abc import Sequence
from dataclasses import dataclass, field

import httpx
import pytest
from google.genai import errors as genai_errors
from pydantic import SecretStr

from app.ai.client import RawResponse, Turn
from app.ai.provider import (
    AnalysisFailed,
    Invalid,
    ProviderConfig,
    Valid,
    run_with_fallback,
)

KEYS = [SecretStr("AIzaKEYONE-secret-1111"), SecretStr("AIzaKEYTWO-secret-2222")]
MODELS = ["model-a", "model-b"]


def api_error(code: int, status: str, details: list[dict] | None = None) -> genai_errors.APIError:
    body = {"error": {"code": code, "status": status, "message": "boom", "details": details or []}}
    cls = genai_errors.ClientError if code < 500 else genai_errors.ServerError
    return cls(code, body)


def retry_info(seconds: str) -> dict:
    return {"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": seconds}


GOOD = RawResponse(text='{"ok": true}', finish_reason="STOP")
BAD = RawResponse(text='{"ok": false}', finish_reason="STOP")
BLOCKED = RawResponse(text="", finish_reason="SAFETY")


class Hang:
    """Outcome that never completes, so only the attempt timeout can end it."""


@dataclass
class ScriptedCaller:
    script: dict[tuple[str, int], list[object]]
    calls: list[tuple[str, int, int]] = field(default_factory=list)

    async def generate(
        self, *, model: str, key_slot: int, api_key: SecretStr, system: str, turns: Sequence[Turn]
    ) -> RawResponse:
        self.calls.append((model, key_slot, len(turns)))
        queue = self.script.get((model, key_slot), [])
        outcome = queue.pop(0) if queue else api_error(500, "INTERNAL")
        if isinstance(outcome, Hang):
            await asyncio.sleep(3600)
        if isinstance(outcome, BaseException):
            raise outcome
        assert isinstance(outcome, RawResponse)
        return outcome


def validate(text: str, finish_reason: str | None):
    if finish_reason == "SAFETY":
        return Invalid("safety_blocked", "blocked")
    return Valid(text) if '"ok": true' in text else Invalid("malformed_output", "ok must be true")


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0
        self.sleeps: list[float] = []

    def __call__(self) -> float:
        return self.now

    async def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


def config(**overrides: object) -> ProviderConfig:
    base: dict[str, object] = {
        "models": MODELS,
        "keys": KEYS,
        "attempt_timeout_seconds": 5.0,
        "deadline_seconds": 60.0,
        "max_attempts": 8,
        "max_transient_retries": 1,
        "backoff_base_seconds": 0.5,
    }
    base.update(overrides)
    return ProviderConfig(**base)  # type: ignore[arg-type]


async def run(caller: ScriptedCaller, clock: FakeClock | None = None, **overrides: object):
    clock = clock or FakeClock()
    return await run_with_fallback(
        system="sys",
        prompt="prompt",
        validate=validate,
        caller=caller,
        config=config(**overrides),
        clock=clock,
        sleep=clock.sleep,
        lead_id="lead-1",
    )


async def test_primary_model_and_key_succeed_first_time():
    caller = ScriptedCaller({("model-a", 1): [GOOD]})
    result = await run(caller)
    assert (result.model, result.key_slot, result.attempts) == ("model-a", 1, 1)
    assert result.value == GOOD.text


async def test_auth_failure_moves_to_next_key_and_never_retries_the_dead_key():
    caller = ScriptedCaller(
        {
            ("model-a", 1): [api_error(401, "UNAUTHENTICATED")],
            ("model-a", 2): [api_error(503, "UNAVAILABLE")],
            ("model-b", 2): [GOOD],
        }
    )
    result = await run(caller)
    assert (result.model, result.key_slot) == ("model-b", 2)
    assert ("model-b", 1, 1) not in caller.calls


async def test_short_retry_delay_is_honoured_on_the_same_key():
    clock = FakeClock()
    caller = ScriptedCaller(
        {("model-a", 1): [api_error(429, "RESOURCE_EXHAUSTED", [retry_info("2s")]), GOOD]}
    )
    result = await run(caller, clock)
    assert (result.model, result.key_slot) == ("model-a", 1)
    assert clock.sleeps == [2.0]


async def test_long_retry_delay_moves_to_next_key_without_waiting():
    clock = FakeClock()
    caller = ScriptedCaller(
        {
            ("model-a", 1): [api_error(429, "RESOURCE_EXHAUSTED", [retry_info("40s")])],
            ("model-a", 2): [GOOD],
        }
    )
    result = await run(caller, clock)
    assert result.key_slot == 2
    assert clock.sleeps == []


async def test_rate_limit_on_every_key_moves_to_next_model():
    limited = api_error(429, "RESOURCE_EXHAUSTED", [retry_info("30s")])
    caller = ScriptedCaller(
        {("model-a", 1): [limited], ("model-a", 2): [limited], ("model-b", 1): [GOOD]}
    )
    result = await run(caller)
    assert (result.model, result.key_slot) == ("model-b", 1)


async def test_unknown_model_falls_back_to_next_model():
    caller = ScriptedCaller({("model-a", 1): [api_error(404, "NOT_FOUND")], ("model-b", 1): [GOOD]})
    result = await run(caller)
    assert result.model == "model-b"
    assert all(model != "model-a" or slot == 1 for model, slot, _ in caller.calls)


async def test_overloaded_model_is_retried_before_falling_back():
    # 503 means temporarily overloaded; jumping straight to a slower model wastes the request.
    caller = ScriptedCaller({("model-a", 1): [api_error(503, "UNAVAILABLE"), GOOD]})
    result = await run(caller)
    assert (result.model, result.key_slot, result.attempts) == ("model-a", 1, 2)


async def test_timeout_skips_to_next_model_without_rotating_keys():
    caller = ScriptedCaller({("model-a", 1): [Hang()], ("model-b", 1): [GOOD]})
    result = await run(caller, attempt_timeout_seconds=0.05)
    assert (result.model, result.key_slot) == ("model-b", 1)
    assert ("model-a", 2, 1) not in caller.calls


async def test_transient_error_is_retried_once_with_backoff_then_moves_on():
    clock = FakeClock()
    caller = ScriptedCaller(
        {
            ("model-a", 1): [api_error(500, "INTERNAL"), api_error(500, "INTERNAL")],
            ("model-b", 1): [GOOD],
        }
    )
    result = await run(caller, clock)
    assert result.model == "model-b"
    assert len(clock.sleeps) == 1 and 0.25 <= clock.sleeps[0] <= 0.75


async def test_network_error_is_treated_as_transient():
    caller = ScriptedCaller(
        {("model-a", 1): [httpx.ConnectError("reset"), GOOD]},
    )
    result = await run(caller)
    assert (result.model, result.attempts) == ("model-a", 2)


async def test_malformed_output_gets_one_repair_turn_then_next_model():
    caller = ScriptedCaller({("model-a", 1): [BAD, BAD], ("model-b", 1): [GOOD]})
    result = await run(caller)
    assert result.model == "model-b"
    # The repair attempt carries the original prompt, the rejected answer and the correction.
    assert caller.calls[:2] == [("model-a", 1, 1), ("model-a", 1, 3)]


async def test_repair_turn_can_succeed():
    caller = ScriptedCaller({("model-a", 1): [BAD, GOOD]})
    result = await run(caller)
    assert (result.model, result.attempts) == ("model-a", 2)


async def test_safety_block_is_repaired_without_echoing_an_empty_model_turn():
    caller = ScriptedCaller({("model-a", 1): [BLOCKED, GOOD]})
    result = await run(caller)
    assert result.attempts == 2
    assert caller.calls[1] == ("model-a", 1, 2)


async def test_invalid_request_stops_immediately():
    caller = ScriptedCaller({("model-a", 1): [api_error(400, "INVALID_ARGUMENT")]})
    with pytest.raises(AnalysisFailed) as exc:
        await run(caller)
    assert exc.value.category == "invalid_request"
    assert len(caller.calls) == 1


async def test_everything_failing_stops_within_the_attempt_budget():
    caller = ScriptedCaller({})  # every call returns a 500
    # The chain alone would make 4 calls (retry once per model); the budget must cut it at 3.
    with pytest.raises(AnalysisFailed) as exc:
        await run(caller, max_attempts=3)
    assert exc.value.category == "exhausted"
    assert len(caller.calls) == 3


async def test_exhausting_the_chain_reports_exhausted():
    caller = ScriptedCaller({})
    with pytest.raises(AnalysisFailed) as exc:
        await run(caller, max_attempts=20)
    assert exc.value.category == "exhausted"
    assert len(caller.calls) == 4


async def test_overall_deadline_bounds_the_whole_analysis():
    clock = FakeClock()
    caller = ScriptedCaller(
        {("model-a", 1): [api_error(429, "RESOURCE_EXHAUSTED", [retry_info("5s")])] * 10}
    )
    with pytest.raises(AnalysisFailed):
        await run(caller, clock, deadline_seconds=4.0, models=["model-a"], keys=KEYS[:1])
    assert clock.now <= 9.0


async def test_no_keys_means_ai_is_unconfigured():
    with pytest.raises(AnalysisFailed) as exc:
        await run(ScriptedCaller({}), keys=[])
    assert exc.value.category == "unconfigured"


async def test_logs_never_contain_api_keys(caplog):
    leaky = api_error(401, "UNAUTHENTICATED")
    leaky.args = (f"401 bad key {KEYS[0].get_secret_value()} at ?key={KEYS[0].get_secret_value()}",)
    caller = ScriptedCaller(
        {
            ("model-a", 1): [leaky],
            ("model-a", 2): [RuntimeError(f"weird {KEYS[1].get_secret_value()}"), GOOD],
        }
    )
    logging.getLogger("followupiq").propagate = True
    with caplog.at_level(logging.DEBUG, logger="followupiq"):
        await run(caller)
    text = caplog.text + " ".join(str(getattr(r, "fields", "")) for r in caplog.records)
    for key in KEYS:
        assert key.get_secret_value() not in text
        assert "secret" not in text
    assert "key_slot=1" in text or "'key_slot': 1" in text
