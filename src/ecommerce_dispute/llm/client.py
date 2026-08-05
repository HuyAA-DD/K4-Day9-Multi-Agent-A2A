"""Serialized GGUF inference for the shared cached Qwen3 model."""

import asyncio
import json
from typing import Any

from ecommerce_dispute.config import MODEL_FILE, MODEL_NAME, Settings


class ModelResponseError(RuntimeError):
    """Raised when the cached model cannot be loaded or invoked."""


class LocalModelClient:
    """One local model instance shared safely by every role-specific agent."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._inference_lock = asyncio.Lock()

        try:
            from huggingface_hub import hf_hub_download
            from llama_cpp import Llama
        except ImportError as exc:
            raise ModelResponseError(
                "Local model dependencies are missing; run pip install -r requirements.txt"
            ) from exc

        try:
            model_path = hf_hub_download(
                MODEL_NAME,
                MODEL_FILE,
                local_files_only=True,
            )
            self.model = Llama(
                model_path=model_path,
                n_ctx=settings.model_context_tokens,
                n_threads=settings.model_threads,
                n_gpu_layers=settings.model_gpu_layers,
                verbose=False,
            )
        except Exception as exc:  # backend errors vary by platform
            raise ModelResponseError(
                f"Could not load {MODEL_NAME}/{MODEL_FILE} from the local cache: {exc}"
            ) from exc

    @property
    def device_name(self) -> str:
        return "llama.cpp-cpu" if self.settings.model_gpu_layers == 0 else "llama.cpp-gpu-offload"

    async def complete_json(
        self,
        system_prompt: str,
        user_payload: str,
        max_new_tokens: int | None = None,
        response_schema: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        async with self._inference_lock:
            try:
                content = await asyncio.to_thread(
                    self._generate,
                    system_prompt,
                    user_payload,
                    max_new_tokens,
                    response_schema,
                )
            except Exception as exc:  # inference errors vary by backend
                raise ModelResponseError(f"Local Qwen review failed: {exc}") from exc

        if not content.strip():
            raise ModelResponseError("Local model returned no text")
        return self._parse_json_object(content)

    def _generate(
        self,
        system_prompt: str,
        user_payload: str,
        max_new_tokens: int | None,
        response_schema: dict[str, Any] | None,
    ) -> str:
        response_format: dict[str, Any] = {"type": "json_object"}
        if response_schema is not None:
            response_format["schema"] = response_schema
        response = self.model.create_chat_completion(
            messages=[
                {"role": "system", "content": "/no_think\n" + system_prompt},
                {"role": "user", "content": user_payload},
            ],
            response_format=response_format,
            temperature=0.7,
            top_p=0.8,
            top_k=20,
            min_p=0.0,
            presence_penalty=1.5,
            seed=0,
            max_tokens=max_new_tokens or self.settings.max_output_tokens,
        )
        content = response["choices"][0]["message"]["content"]
        if not isinstance(content, str):
            raise ModelResponseError("llama.cpp returned no text content")
        return content

    @staticmethod
    def _parse_json_object(content: str) -> dict[str, Any]:
        text = content.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines).strip()
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            start = text.find("{")
            end = text.rfind("}")
            if start < 0 or end <= start:
                raise ModelResponseError("Model response does not contain a JSON object")
            parsed = json.loads(text[start : end + 1])
        if not isinstance(parsed, dict):
            raise ModelResponseError("Model response must be a JSON object")
        return parsed
