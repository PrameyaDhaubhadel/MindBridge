from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value)


@dataclass
class ReportStore:
    report_file: Path
    inactivity_minutes: int = 30

    def _default_profile(self) -> dict[str, Any]:
        now = _now_iso()
        return {
            "username": None,
            "display_name": None,
            "first_seen": now,
            "last_seen": now,
            "turn_count": 0,
            "risk_counts": {"low": 0, "medium": 0, "high": 0},
            "observed_emotions": [],
            "observed_concerns": [],
            "latest_summary": "",
            "status": "active",
            "ended_at": None,
            "turns": [],
        }

    def _load(self) -> dict[str, Any]:
        if not self.report_file.exists():
            return {
                "generated_at": _now_iso(),
                "users": {},
            }

        with self.report_file.open("r", encoding="utf-8") as f:
            raw = f.read().strip()

        if not raw:
            data = {"generated_at": _now_iso(), "users": {}}
        else:
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                # Recover gracefully if the report file is temporarily malformed.
                data = {"generated_at": _now_iso(), "users": {}}

        if "users" not in data or not isinstance(data["users"], dict):
            data["users"] = {}
        return data

    def _save(self, data: dict[str, Any]) -> None:
        self.report_file.parent.mkdir(parents=True, exist_ok=True)
        data["generated_at"] = _now_iso()
        with self.report_file.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def _apply_inactivity_status(self, profile: dict[str, Any]) -> dict[str, Any]:
        last_seen = profile.get("last_seen")
        if not last_seen:
            return profile

        if profile.get("status") == "ended":
            return profile

        cutoff = datetime.now(timezone.utc) - timedelta(minutes=self.inactivity_minutes)
        if _parse_iso(last_seen) < cutoff:
            profile["status"] = "ended"
            profile["ended_at"] = profile.get("ended_at") or _now_iso()

        return profile

    def _public_profile(self, user_id: str, profile: dict[str, Any]) -> dict[str, Any]:
        self._apply_inactivity_status(profile)
        return {
            "user_id": user_id,
            "username": profile.get("username"),
            "display_name": profile.get("display_name"),
            "first_seen": profile.get("first_seen"),
            "last_seen": profile.get("last_seen"),
            "ended_at": profile.get("ended_at"),
            "status": profile.get("status", "active"),
            "turn_count": profile.get("turn_count", 0),
            "risk_counts": profile.get("risk_counts", {"low": 0, "medium": 0, "high": 0}),
            "observed_emotions": profile.get("observed_emotions", []),
            "observed_concerns": profile.get("observed_concerns", []),
            "latest_summary": profile.get("latest_summary", ""),
            "turns": profile.get("turns", []),
        }

    def update_user_turn(
        self,
        user_id: str,
        username: str | None,
        display_name: str | None,
        user_message: str,
        assistant_reply: str,
        risk_level: str,
    ) -> None:
        data = self._load()
        users: dict[str, Any] = data["users"]

        profile = users.get(user_id)
        if profile is None:
            profile = self._default_profile()
            users[user_id] = profile

        profile["last_seen"] = _now_iso()
        profile["username"] = username or profile.get("username")
        profile["display_name"] = display_name or profile.get("display_name")
        profile["status"] = "active"
        profile["ended_at"] = None
        profile["turn_count"] = int(profile.get("turn_count", 0)) + 1

        risk_counts = profile.get("risk_counts", {"low": 0, "medium": 0, "high": 0})
        risk_counts[risk_level] = int(risk_counts.get(risk_level, 0)) + 1
        profile["risk_counts"] = risk_counts

        emotions = self._extract_emotions(user_message)
        concerns = self._extract_concerns(user_message)
        profile["observed_emotions"] = self._merge_unique(profile.get("observed_emotions", []), emotions)
        profile["observed_concerns"] = self._merge_unique(profile.get("observed_concerns", []), concerns)

        profile["latest_summary"] = self._build_summary(profile)

        turns = profile.get("turns", [])
        turns.append(
            {
                "timestamp": _now_iso(),
                "risk": risk_level,
                "user": user_message,
                "assistant": assistant_reply,
            }
        )
        profile["turns"] = turns[-40:]

        self._save(data)

    def end_conversation(self, user_id: str) -> dict[str, Any] | None:
        data = self._load()
        users: dict[str, Any] = data["users"]
        profile = users.get(user_id)
        if profile is None:
            return None

        profile["status"] = "ended"
        profile["ended_at"] = _now_iso()
        profile["last_seen"] = profile.get("last_seen") or _now_iso()
        self._save(data)
        return self._public_profile(user_id, profile)

    def get_user_report(self, user_id: str) -> dict[str, Any] | None:
        data = self._load()
        users: dict[str, Any] = data["users"]
        profile = users.get(user_id)
        if profile is None:
            return None

        self._apply_inactivity_status(profile)
        self._save(data)
        return self._public_profile(user_id, profile)

    def get_user_report_by_username(self, username: str) -> dict[str, Any] | None:
        normalized = username.strip().lower()
        data = self._load()
        users: dict[str, Any] = data["users"]

        for user_id, profile in users.items():
            if (profile.get("username") or "").lower() != normalized:
                continue
            self._apply_inactivity_status(profile)
            self._save(data)
            return self._public_profile(user_id, profile)

        return None

    def get_all_reports(self) -> dict[str, Any]:
        data = self._load()
        users: dict[str, Any] = data["users"]

        reports = []
        for user_id, profile in users.items():
            self._apply_inactivity_status(profile)
            reports.append(self._public_profile(user_id, profile))

        self._save(data)
        reports.sort(key=lambda item: item.get("last_seen") or "", reverse=True)
        return {
            "generated_at": data.get("generated_at"),
            "inactivity_minutes": self.inactivity_minutes,
            "count": len(reports),
            "reports": reports,
        }

    def delete_user_report(self, user_id: str) -> bool:
        data = self._load()
        users: dict[str, Any] = data["users"]
        if user_id not in users:
            return False

        del users[user_id]
        self._save(data)
        return True

    def delete_user_report_by_username(self, username: str) -> bool:
        normalized = username.strip().lower()
        data = self._load()
        users: dict[str, Any] = data["users"]

        matched_user_id = None
        for user_id, profile in users.items():
            if (profile.get("username") or "").lower() == normalized:
                matched_user_id = user_id
                break

        if not matched_user_id:
            return False

        del users[matched_user_id]
        self._save(data)
        return True

    def _merge_unique(self, original: list[str], incoming: list[str]) -> list[str]:
        seen = {item.lower() for item in original}
        result = list(original)
        for item in incoming:
            if item.lower() not in seen:
                result.append(item)
                seen.add(item.lower())
        return result

    def _extract_emotions(self, text: str) -> list[str]:
        lowered = text.lower()
        labels = {
            "anxious": ["anxious", "anxiety", "panic", "nervous"],
            "sad": ["sad", "down", "depressed", "hopeless"],
            "overwhelmed": ["overwhelmed", "burned out", "too much"],
            "angry": ["angry", "frustrated", "irritated"],
            "lonely": ["lonely", "alone", "isolated"],
            "stressed": ["stress", "stressed", "pressure"],
        }
        found = []
        for label, keys in labels.items():
            if any(key in lowered for key in keys):
                found.append(label)
        return found

    def _extract_concerns(self, text: str) -> list[str]:
        lowered = text.lower()
        labels = {
            "sleep": ["sleep", "insomnia", "cannot sleep"],
            "school": ["exam", "school", "study", "class"],
            "work": ["work", "job", "boss", "office"],
            "relationships": ["partner", "relationship", "friend", "family"],
            "health": ["health", "sick", "pain"],
            "motivation": ["motivation", "procrast", "focus"],
        }
        found = []
        for label, keys in labels.items():
            if any(key in lowered for key in keys):
                found.append(label)
        return found

    def _build_summary(self, profile: dict[str, Any]) -> str:
        emotions = profile.get("observed_emotions", [])
        concerns = profile.get("observed_concerns", [])
        risk_counts = profile.get("risk_counts", {})
        top_risk = max(risk_counts, key=risk_counts.get) if risk_counts else "low"

        emotion_text = ", ".join(emotions) if emotions else "not enough data"
        concern_text = ", ".join(concerns) if concerns else "not enough data"

        return (
            f"Common emotional signals: {emotion_text}. "
            f"Common concern areas: {concern_text}. "
            f"Most frequent risk level so far: {top_risk}."
        )
