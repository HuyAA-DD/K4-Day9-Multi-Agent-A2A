"""Structured model client protocol and OpenAI adapter."""

from .client import (
    ModelCompletion,
    ModelResponseError,
    OpenAIModelClient,
    StructuredModelClient,
)

__all__ = [
    "ModelCompletion",
    "ModelResponseError",
    "OpenAIModelClient",
    "StructuredModelClient",
]
