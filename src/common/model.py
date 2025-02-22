from dataclasses import dataclass
from enum import Enum

import httpx
import requests
from dataclasses_json import dataclass_json

from common.config import OPENROUTER_API_KEY, OPENROUTER_URL


class Model(Enum):
    OpenAI_4o = "openai/gpt-4o"
    OpenAI_o1 = "openai/o1-mini"
    GeminiFlash = "google/gemini-2.0-flash-001"
    GeminiFlashThinking = "google/gemini-2.0-flash-thinking-exp:free"
    DeepSeekR1 = "deepseek/deepseek-r1"


class Role(Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


@dataclass_json
@dataclass
class Message:
    role: Role
    content: str


@dataclass_json
@dataclass
class Request:
    model: Model
    messages: list[Message]


async def call(request: Request):
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{OPENROUTER_URL}/chat/completions",
            headers=headers,
            data=request.to_json(),
        )
        if response.status_code != 200:
            raise httpx.HTTPStatusError(
                f"Request failed with status {response.status_code}: {response.text}",
                request=response.request,
                response=response,
            )

        return response.json()
