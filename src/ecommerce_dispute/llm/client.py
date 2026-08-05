"""Async structured-output client shared by model-backed policy roles."""

import json
import re
from dataclasses import dataclass, field
from typing import Any, Protocol

from openai import AsyncOpenAI

from ecommerce_dispute.config import Settings


class ModelResponseError(RuntimeError):
    """Raised when a hosted model request cannot produce a JSON object."""


@dataclass(frozen=True, slots=True)
class ModelCompletion:
    content: dict[str, Any]
    model_id: str
    request_id: str | None = None
    usage: dict[str, int] = field(default_factory=dict)


class StructuredModelClient(Protocol):
    settings: Settings

    @property
    def device_name(self) -> str: ...

    async def complete_json(
        self,
        system_prompt: str,
        user_payload: str,
        *,
        model: str,
        response_schema: dict[str, Any],
        max_output_tokens: int | None = None,
    ) -> ModelCompletion: ...


class OpenAIModelClient:
    """OpenAI Chat Completions adapter with strict JSON Schema decoding."""

    def __init__(self, settings: Settings) -> None:
        if not settings.api_key:
            raise ModelResponseError("OPENAI_API_KEY is missing from the environment")
        self.settings = settings
        self.client = AsyncOpenAI(
            api_key=settings.api_key,
            base_url=settings.base_url,
            timeout=settings.request_timeout_seconds,
        )

    @property
    def device_name(self) -> str:
        return "openai-hosted-api"

    async def complete_json(
        self,
        system_prompt: str,
        user_payload: str,
        *,
        model: str,
        response_schema: dict[str, Any],
        max_output_tokens: int | None = None,
    ) -> ModelCompletion:
        raw_name = str(response_schema.get("title", "agent_response"))
        schema_name = re.sub(r"[^a-zA-Z0-9_-]", "_", raw_name)[:64]
        try:
            response = await self.client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_payload},
                ],
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": schema_name,
                        "strict": True,
                        "schema": response_schema,
                    },
                },  # type: ignore[arg-type]
                temperature=self.settings.temperature,
                max_tokens=max_output_tokens or self.settings.max_output_tokens,
            )
        except Exception as exc:  # SDK exception hierarchy varies by release
            raise ModelResponseError(f"OpenAI model request failed: {exc}") from exc

        choice = response.choices[0].message
        if not choice.content:
            refusal = getattr(choice, "refusal", None)
            detail = f": {refusal}" if refusal else ""
            raise ModelResponseError(f"OpenAI model returned no JSON content{detail}")
        try:
            parsed = json.loads(choice.content)
        except json.JSONDecodeError as exc:
            raise ModelResponseError("OpenAI model returned invalid JSON") from exc
        if not isinstance(parsed, dict):
            raise ModelResponseError("OpenAI model response must be a JSON object")
        usage: dict[str, int] = {}
        if response.usage is not None:
            usage = {
                "input_tokens": response.usage.prompt_tokens,
                "output_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            }
        return ModelCompletion(
            content=parsed,
            model_id=response.model,
            request_id=response.id,
            usage=usage,
        )
