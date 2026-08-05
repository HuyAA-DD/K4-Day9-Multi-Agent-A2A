"""OpenAI-compatible client for the shared Qwen3.5-9B endpoint."""

from openai import AsyncOpenAI

from ecommerce_dispute.config import MODEL_NAME, Settings


class SharedModelClient:
    """One logical client shared by all role-specific agents."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client = AsyncOpenAI(base_url=settings.base_url, api_key=settings.api_key)

    async def complete_json(self, system_prompt: str, user_payload: str) -> str:
        """Return JSON text; callers must validate it against their Pydantic schema."""
        response = await self.client.chat.completions.create(
            model=MODEL_NAME,
            temperature=self.settings.temperature,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_payload},
            ],
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content
        if not content:
            raise RuntimeError("Model returned an empty response")
        return content

