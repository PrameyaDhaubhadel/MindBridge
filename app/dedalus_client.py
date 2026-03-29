from __future__ import annotations

import os
from typing import List, Dict

import httpx


def _clean_env(value: str) -> str:
    # Remove invisible control chars/newlines that break HTTP header validation.
    return value.replace("\r", "").replace("\n", "").strip()


class DedalusClient:
    def __init__(self) -> None:
        self.api_key = _clean_env(os.getenv("DEDALUS_API_KEY", ""))
        self.base_url = _clean_env(os.getenv("DEDALUS_API_URL", "https://api.dedaluslabs.ai")).rstrip("/")
        self.model = _clean_env(os.getenv("DEDALUS_MODEL", "openai/gpt-5.4"))

        if not self.api_key:
            raise RuntimeError("DEDALUS_API_KEY is missing. Add it to your environment.")
        if any(ch in self.api_key for ch in ("\r", "\n")):
            raise RuntimeError("DEDALUS_API_KEY contains invalid newline characters.")

    async def complete_chat(self, messages: List[Dict[str, str]]) -> str:
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.4,
        }

        async with httpx.AsyncClient(timeout=30) as client:
            candidates = [
                (f"{self.base_url}/chat/completions", {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}),
                (f"{self.base_url}/v1/chat/completions", {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}),
                (f"{self.base_url}/chat/completions", {"X-API-Key": self.api_key, "Content-Type": "application/json"}),
                (f"{self.base_url}/v1/chat/completions", {"X-API-Key": self.api_key, "Content-Type": "application/json"}),
            ]

            data = None
            last_error = None
            for url, headers in candidates:
                try:
                    response = await client.post(url, json=payload, headers=headers)
                    response.raise_for_status()
                    data = response.json()
                    break
                except httpx.HTTPError as exc:
                    last_error = exc

            if data is None:
                raise RuntimeError(f"Dedalus API request failed for all endpoint variants: {last_error}")

        try:
            return data["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError(f"Unexpected DedalusLabs response format: {data}") from exc
