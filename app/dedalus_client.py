from __future__ import annotations

import os
from typing import List, Dict

import httpx


def _clean_env(value: str) -> str:
    # Remove ASCII control chars that can invalidate HTTP headers.
    cleaned = "".join(ch for ch in value if ord(ch) >= 32 and ord(ch) != 127)
    return cleaned.strip()


def _clean_header_value(value: str) -> str:
    # Header values cannot contain CR/LF or other control characters.
    return _clean_env(value)


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
                    safe_headers = {k: _clean_header_value(v) for k, v in headers.items()}
                    response = await client.post(url, json=payload, headers=safe_headers)
                    response.raise_for_status()
                    data = response.json()
                    break
                except httpx.HTTPError as exc:
                    last_error = exc

            if data is None:
                key_meta = f"key_len={len(self.api_key)} has_cr={'\\r' in self.api_key} has_lf={'\\n' in self.api_key}"
                raise RuntimeError(f"Dedalus API request failed for all endpoint variants: {last_error}; {key_meta}")

        try:
            return data["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError(f"Unexpected DedalusLabs response format: {data}") from exc
