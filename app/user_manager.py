from __future__ import annotations

import hashlib
import json
import secrets
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class UserManager:
    users_file: Path

    def _normalize_username(self, username: str) -> str:
        return username.strip().lower()

    def _normalize_password_for_store(self, password: str) -> str:
        # Avoid accidental leading/trailing spaces causing hard-to-debug login issues.
        return password.strip()

    def _load(self) -> dict[str, Any]:
        if not self.users_file.exists():
            return {"generated_at": _now_iso(), "users": {}}

        with self.users_file.open("r", encoding="utf-8") as f:
            data = json.load(f)

        if "users" not in data or not isinstance(data["users"], dict):
            data["users"] = {}
        return data

    def _save(self, data: dict[str, Any]) -> None:
        self.users_file.parent.mkdir(parents=True, exist_ok=True)
        data["generated_at"] = _now_iso()
        with self.users_file.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def _hash_password(self, password: str, salt: str) -> str:
        return hashlib.sha256(f"{salt}:{password}".encode("utf-8")).hexdigest()

    def _sanitize_user(self, profile: dict[str, Any]) -> dict[str, Any]:
        return {
            "user_id": profile["user_id"],
            "username": profile["username"],
            "display_name": profile["display_name"],
            "created_at": profile["created_at"],
            "last_login_at": profile.get("last_login_at"),
        }

    def register(self, username: str, password: str, display_name: str) -> dict[str, Any]:
        data = self._load()
        users: dict[str, Any] = data["users"]

        normalized = self._normalize_username(username)
        if not normalized:
            raise ValueError("Username cannot be empty")

        cleaned_password = self._normalize_password_for_store(password)
        if len(cleaned_password) < 6:
            raise ValueError("Password must be at least 6 characters")

        if any(item.get("username") == normalized for item in users.values()):
            raise ValueError("Username already exists")

        user_id = f"user-{secrets.token_hex(6)}"
        salt = secrets.token_hex(8)
        profile = {
            "user_id": user_id,
            "username": normalized,
            "display_name": display_name.strip() or normalized,
            "password_salt": salt,
            "password_hash": self._hash_password(cleaned_password, salt),
            "created_at": _now_iso(),
            "last_login_at": _now_iso(),
        }
        users[user_id] = profile

        self._save(data)
        return self._sanitize_user(profile)

    def login(self, username: str, password: str) -> dict[str, Any]:
        data = self._load()
        users: dict[str, Any] = data["users"]

        normalized = self._normalize_username(username)
        for user_id, profile in users.items():
            if profile.get("username") != normalized:
                continue

            expected_hash = profile.get("password_hash", "")
            salt = profile.get("password_salt", "")
            candidates = [password, password.strip()]
            incoming_hashes = {self._hash_password(candidate, salt) for candidate in candidates}
            if expected_hash not in incoming_hashes:
                raise ValueError("Invalid username or password")

            profile["last_login_at"] = _now_iso()
            users[user_id] = profile
            self._save(data)
            return self._sanitize_user(profile)

        raise ValueError("Invalid username or password")

    def get_user(self, user_id: str) -> dict[str, Any] | None:
        data = self._load()
        profile = data["users"].get(user_id)
        if profile is None:
            return None
        return self._sanitize_user(profile)

    def delete_by_username(self, username: str) -> bool:
        normalized = self._normalize_username(username)
        data = self._load()
        users: dict[str, Any] = data["users"]

        matched_user_id = None
        for user_id, profile in users.items():
            if profile.get("username") == normalized:
                matched_user_id = user_id
                break

        if not matched_user_id:
            return False

        del users[matched_user_id]
        self._save(data)
        return True
