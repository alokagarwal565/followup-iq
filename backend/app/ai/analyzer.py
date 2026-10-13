from typing import Protocol

from app.ai.client import GeminiCaller
from app.ai.prompt import SYSTEM_INSTRUCTION, PromptContext, build_user_prompt
from app.ai.provider import ProviderConfig, ProviderResult, run_with_fallback
from app.ai.validation import ValidatedAnalysis, Validator
from app.config import Settings


class Analyzer(Protocol):
    async def analyze(
        self, *, context: PromptContext, validate: Validator, lead_id: str
    ) -> ProviderResult[ValidatedAnalysis]: ...


class GeminiAnalyzer:
    def __init__(self, settings: Settings) -> None:
        self._config = ProviderConfig(
            models=settings.gemini_models,
            keys=settings.gemini_keys,
            attempt_timeout_seconds=settings.gemini_request_timeout_seconds,
            deadline_seconds=settings.gemini_analysis_deadline_seconds,
            max_attempts=settings.gemini_max_attempts,
            max_transient_retries=settings.gemini_max_retries,
            backoff_base_seconds=settings.gemini_retry_backoff_base_seconds,
        )
        self._caller = GeminiCaller(settings.gemini_request_timeout_seconds)

    async def analyze(
        self, *, context: PromptContext, validate: Validator, lead_id: str
    ) -> ProviderResult[ValidatedAnalysis]:
        return await run_with_fallback(
            system=SYSTEM_INSTRUCTION,
            prompt=build_user_prompt(context),
            validate=validate,
            caller=self._caller,
            config=self._config,
            lead_id=lead_id,
        )
