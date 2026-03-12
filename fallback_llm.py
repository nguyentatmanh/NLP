from __future__ import annotations

import os
from dataclasses import dataclass
from typing import List

import requests


SYSTEM_PROMPT = """Ban la mot tro ly hoi dap tieng Viet.
Chi duoc tra loi dua tren kho ngữ cảnh da cung cap.
Neu kho ngữ cảnh khong du hoac khong co cau tra loi ro rang, hay tra loi dung mot cau:
Khong tim thay thong tin du tin cay trong kho du lieu.
Tra loi ngan gon, ro rang, khong bịa them chi tiet.
"""


@dataclass
class FallbackResponse:
    answer: str
    provider: str
    model: str


class BaseFallback:
    provider_name = "base"

    def __init__(self, model: str) -> None:
        self.model = model

    def generate(self, question: str, contexts: List[str]) -> FallbackResponse:
        raise NotImplementedError


class OpenAICompatibleFallback(BaseFallback):
    provider_name = "openai_compatible"

    def __init__(self, base_url: str, api_key: str, model: str, timeout: int = 60) -> None:
        super().__init__(model=model)
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout

    def generate(self, question: str, contexts: List[str]) -> FallbackResponse:
        context_blob = "\n\n".join(f"[Doan {idx}]\n{text}" for idx, text in enumerate(contexts, start=1))
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": f"Cau hoi:\n{question}\n\nKho ngữ cảnh:\n{context_blob}",
                },
            ],
            "temperature": 0.2,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        response = requests.post(
            f"{self.base_url}/chat/completions",
            json=payload,
            headers=headers,
            timeout=self.timeout,
        )
        response.raise_for_status()
        data = response.json()
        content = data["choices"][0]["message"]["content"].strip()
        return FallbackResponse(answer=content, provider=self.provider_name, model=self.model)


class OllamaFallback(BaseFallback):
    provider_name = "ollama"

    def __init__(self, base_url: str, model: str, timeout: int = 60) -> None:
        super().__init__(model=model)
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def generate(self, question: str, contexts: List[str]) -> FallbackResponse:
        context_blob = "\n\n".join(f"[Doan {idx}]\n{text}" for idx, text in enumerate(contexts, start=1))
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": f"Cau hoi:\n{question}\n\nKho ngữ cảnh:\n{context_blob}",
                },
            ],
            "stream": False,
        }
        response = requests.post(f"{self.base_url}/api/chat", json=payload, timeout=self.timeout)
        response.raise_for_status()
        data = response.json()
        content = data["message"]["content"].strip()
        return FallbackResponse(answer=content, provider=self.provider_name, model=self.model)


def build_fallback(provider: str) -> BaseFallback | None:
    provider = (provider or os.getenv("FALLBACK_PROVIDER", "disabled")).strip().lower()
    if provider in {"", "disabled", "none"}:
        return None
    if provider == "openai_compatible":
        base_url = os.getenv("OPENAI_COMPAT_BASE_URL", "").strip()
        api_key = os.getenv("OPENAI_COMPAT_API_KEY", "").strip()
        model = os.getenv("OPENAI_COMPAT_MODEL", "gpt-4.1-mini").strip()
        if not base_url or not api_key:
            raise RuntimeError("Thieu OPENAI_COMPAT_BASE_URL hoac OPENAI_COMPAT_API_KEY")
        return OpenAICompatibleFallback(base_url=base_url, api_key=api_key, model=model)
    if provider == "ollama":
        base_url = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").strip()
        model = os.getenv("OLLAMA_MODEL", "qwen2.5:7b-instruct").strip()
        return OllamaFallback(base_url=base_url, model=model)
    raise ValueError(f"Khong ho tro fallback provider: {provider}")
