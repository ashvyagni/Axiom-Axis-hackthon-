import time
import json
from groq import AsyncGroq
from axiom.ai.base import AIProvider, AIResponse
from axiom.config import get_settings
from typing import Any


class GroqProvider(AIProvider):
    def __init__(self):
        settings = get_settings()
        self.client = AsyncGroq(api_key=settings.GROQ_API_KEY)
        self.strong_model = settings.GROQ_MODEL_STRONG
        self.fast_model = settings.GROQ_MODEL_FAST
        self.vision_model = settings.GROQ_MODEL_VISION

    async def generate(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float = 0.3,
        max_tokens: int = 2048,
        response_format: dict | None = None,
    ) -> AIResponse:
        model = model or self.strong_model
        start = time.time()
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if response_format:
            kwargs["response_format"] = response_format

        response = await self.client.chat.completions.create(**kwargs)
        latency = int((time.time() - start) * 1000)
        choice = response.choices[0]
        usage = response.usage
        return AIResponse(
            content=choice.message.content or "",
            model=model,
            tokens_in=usage.prompt_tokens if usage else 0,
            tokens_out=usage.completion_tokens if usage else 0,
            latency_ms=latency,
        )

    async def generate_structured(
        self,
        messages: list[dict[str, str]],
        schema: dict,
        model: str | None = None,
    ) -> dict[str, Any]:
        response = await self.generate(
            messages=messages,
            model=model,
            response_format={"type": "json_object"},
        )
        try:
            return json.loads(response.content)
        except json.JSONDecodeError:
            return {"error": "Failed to parse structured output", "raw": response.content}

    async def analyze_image(
        self,
        image_url: str,
        prompt: str,
        model: str | None = None,
    ) -> AIResponse:
        model = model or self.vision_model
        start = time.time()
        response = await self.client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": image_url}},
                    ],
                }
            ],
            max_tokens=1024,
        )
        latency = int((time.time() - start) * 1000)
        choice = response.choices[0]
        usage = response.usage
        return AIResponse(
            content=choice.message.content or "",
            model=model,
            tokens_in=usage.prompt_tokens if usage else 0,
            tokens_out=usage.completion_tokens if usage else 0,
            latency_ms=latency,
        )
