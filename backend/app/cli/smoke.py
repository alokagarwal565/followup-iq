"""Live check of every configured model x key slot with one tiny request each.

    python -m app.cli.smoke

Prints only model, key slot, outcome and latency; key values are never printed. Costs one
minimal request per pair, so it is a manual command, never part of the test suite.
"""

import asyncio
import time

from google import genai
from google.genai import types

from app.ai.client import thinking_level_for
from app.ai.errors import classify_exception
from app.config import load_settings
from app.runtime import run


async def _probe(model: str, key: str, limit_seconds: float) -> tuple[str, int]:
    client = genai.Client(api_key=key)
    level = thinking_level_for(model)
    config = types.GenerateContentConfig(
        response_mime_type="application/json",
        response_json_schema={
            "type": "object",
            "properties": {"ok": {"type": "boolean"}},
            "required": ["ok"],
        },
        thinking_config=types.ThinkingConfig(thinking_level=level) if level else None,
    )
    started = time.monotonic()
    try:
        async with asyncio.timeout(limit_seconds):
            response = await client.aio.models.generate_content(
                model=model, contents='Return {"ok": true}.', config=config
            )
        outcome = "ok" if '"ok"' in (response.text or "") else "unexpected_output"
    except TimeoutError:
        outcome = "timeout"
    except Exception as exc:
        outcome = classify_exception(exc).category
    return outcome, int((time.monotonic() - started) * 1000)


async def main() -> None:
    settings = load_settings()
    keys = settings.gemini_keys
    if not keys:
        print("No Gemini keys configured.")
        return
    print(f"{'model':<26} {'slot':>4}  {'outcome':<18} {'ms':>6}")
    for model in settings.gemini_models:
        for slot, key in enumerate(keys, start=1):
            outcome, ms = await _probe(
                model, key.get_secret_value(), settings.gemini_request_timeout_seconds
            )
            print(f"{model:<26} {slot:>4}  {outcome:<18} {ms:>6}")


if __name__ == "__main__":
    run(main())
