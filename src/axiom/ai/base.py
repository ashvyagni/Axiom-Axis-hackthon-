from abc import ABC, abstractmethod
from pydantic import BaseModel
from typing import Any


class AIResponse(BaseModel):
    content: str
    model: str
    tokens_in: int = 0
    tokens_out: int = 0
    latency_ms: int = 0


class AIProvider(ABC):
    @abstractmethod
    async def generate(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float = 0.3,
        max_tokens: int = 2048,
        response_format: dict | None = None,
    ) -> AIResponse:
        ...

    @abstractmethod
    async def generate_structured(
        self,
        messages: list[dict[str, str]],
        schema: dict,
        model: str | None = None,
    ) -> dict[str, Any]:
        ...

    @abstractmethod
    async def analyze_image(
        self,
        image_url: str,
        prompt: str,
        model: str | None = None,
    ) -> AIResponse:
        ...
