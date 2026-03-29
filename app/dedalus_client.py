from __future__ import annotations

import os
from typing import List, Dict

import httpx


class DedalusClient:
    def __init__(self) -> None:
        self.api_key = os.getenv("DEDALUS_API_KEY", "")
        self.base_url = os.getenv("DEDALUS_API_URL", "https://api.dedaluslabs.ai").rstrip("/")
        self.model = os.getenv("DEDALUS_MODEL", "openai/gpt-5.4")

        if not self.api_key:
            raise RuntimeError("DEDALUS_API_KEY is missing. Add it to your environment.")

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
