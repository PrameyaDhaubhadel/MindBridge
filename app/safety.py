from __future__ import annotations

import re
from typing import Literal

RiskLevel = Literal["low", "medium", "high"]

_HIGH_RISK_PATTERNS = [
    r"\bkill myself\b",
    r"\bsuicid(e|al)\b",
    r"\bend my life\b",
    r"\bself[- ]harm\b",
    r"\bhurt myself\b",
    r"\bhurt someone\b",
    r"\bwant to die\b",
]

_MEDIUM_RISK_PATTERNS = [
    r"\bhopeless\b",
    r"\bcan't go on\b",
    r"\bpanic attack\b",
    r"\bsevere anxiety\b",
    r"\bdepressed\b",
]


def assess_risk(text: str) -> RiskLevel:
    lowered = text.lower()

    for pattern in _HIGH_RISK_PATTERNS:
        if re.search(pattern, lowered):
            return "high"

    for pattern in _MEDIUM_RISK_PATTERNS:
        if re.search(pattern, lowered):
            return "medium"

    return "low"


def strip_unsafe_content(text: str) -> str:
    """Simple output sanitization to avoid accidentally returning harmful procedural content."""
    blocked_markers = [
        "here is how to kill",
        "steps to self-harm",
        "painless way to die",
    ]
    safe_text = text
    for marker in blocked_markers:
        safe_text = safe_text.replace(marker, "[removed unsafe content]")
    return safe_text
