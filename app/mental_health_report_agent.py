from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass
class MentalHealthReportAgent:
    """Analyzes a user's full conversation history and produces a clinical support report."""

    def generate_detailed_report(self, report: dict[str, Any]) -> dict[str, Any]:
        turns = report.get("turns", [])
        user_messages = [item.get("user", "") for item in turns if item.get("user")]

        distress_scores = [self._distress_score(text) for text in user_messages]
        first_avg, last_avg = self._split_trend(distress_scores)
        trend_label = self._trend_label(first_avg, last_avg)

        top_emotions = report.get("observed_emotions", [])
        top_concerns = report.get("observed_concerns", [])
        risk_counts = report.get("risk_counts", {"low": 0, "medium": 0, "high": 0})

        summary = {
            "patient_identity": {
                "username": report.get("username"),
                "display_name": report.get("display_name"),
                "user_id": report.get("user_id"),
            },
            "observation_window": {
                "first_seen": report.get("first_seen"),
                "last_seen": report.get("last_seen"),
                "status": report.get("status"),
                "total_turns": report.get("turn_count", 0),
            },
            "clinical_snapshot": {
                "risk_distribution": risk_counts,
                "dominant_emotional_signals": top_emotions,
                "dominant_concern_areas": top_concerns,
                "overall_trajectory": trend_label,
            },
            "progress_indicators": {
                "early_distress_average": round(first_avg, 2),
                "recent_distress_average": round(last_avg, 2),
                "change_direction": self._change_direction(first_avg, last_avg),
                "engagement_pattern": self._engagement_pattern(turns),
            },
            "key_quotes_for_context": self._extract_context_quotes(user_messages),
            "clinical_follow_up_suggestions": self._follow_up_suggestions(top_emotions, top_concerns, trend_label),
            "care_team_notes": [
                "This report is supportive decision aid and not a diagnostic document.",
                "Use alongside direct clinical assessment, risk screening, and local protocols.",
            ],
            "generated_at": datetime.utcnow().isoformat() + "Z",
        }

        return summary

    def _distress_score(self, text: str) -> int:
        lowered = text.lower()
        weighted_terms = {
            "hopeless": 4,
            "panic": 3,
            "anxious": 2,
            "anxiety": 2,
            "overwhelmed": 2,
            "sad": 2,
            "lonely": 2,
            "stressed": 1,
            "tired": 1,
            "cant cope": 3,
            "can't cope": 3,
            "worthless": 4,
            "empty": 2,
        }
        score = 0
        for term, weight in weighted_terms.items():
            if term in lowered:
                score += weight
        return score

    def _split_trend(self, values: list[int]) -> tuple[float, float]:
        if not values:
            return 0.0, 0.0
        midpoint = max(1, len(values) // 2)
        first = values[:midpoint]
        last = values[midpoint:]
        first_avg = sum(first) / len(first)
        last_avg = sum(last) / len(last) if last else first_avg
        return first_avg, last_avg

    def _trend_label(self, first_avg: float, last_avg: float) -> str:
        delta = last_avg - first_avg
        if delta <= -0.75:
            return "improving distress trend"
        if delta >= 0.75:
            return "worsening distress trend"
        return "mixed or stable trend"

    def _change_direction(self, first_avg: float, last_avg: float) -> str:
        if last_avg < first_avg:
            return "decreasing distress markers"
        if last_avg > first_avg:
            return "increasing distress markers"
        return "no clear directional change"

    def _engagement_pattern(self, turns: list[dict[str, Any]]) -> str:
        total = len(turns)
        if total >= 20:
            return "high engagement"
        if total >= 8:
            return "moderate engagement"
        return "early-stage engagement"

    def _extract_context_quotes(self, user_messages: list[str]) -> list[str]:
        if not user_messages:
            return []

        # Keep up to 5 distinct short quotes for clinician context.
        cleaned = [item.strip() for item in user_messages if item.strip()]
        unique = list(dict.fromkeys(cleaned))
        return unique[-5:]

    def _follow_up_suggestions(self, emotions: list[str], concerns: list[str], trend: str) -> list[str]:
        suggestions: list[str] = []

        if "anxious" in emotions or "overwhelmed" in emotions:
            suggestions.append("Assess autonomic anxiety symptoms, triggers, and current coping efficacy.")
        if "sad" in emotions or "lonely" in emotions:
            suggestions.append("Assess depressive symptoms, social support quality, and behavioral activation barriers.")
        if "sleep" in concerns:
            suggestions.append("Screen sleep quality and sleep hygiene contributors to mood/anxiety burden.")
        if "work" in concerns or "school" in concerns:
            suggestions.append("Review role-functioning stressors and collaborative workload coping plan.")
        if trend == "worsening distress trend":
            suggestions.append("Consider closer follow-up cadence and formal risk reassessment.")

        if not suggestions:
            suggestions.append("Continue supportive monitoring and periodic symptom/risk check-ins.")

        return suggestions
