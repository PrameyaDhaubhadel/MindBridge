from __future__ import annotations

import re

_FALLBACK_QUESTION = "How have you been feeling emotionally over the last few days?"


def should_offer_actionable_options(user_message: str, risk_level: str) -> bool:
    lowered = user_message.lower()

    if risk_level in {"medium", "high"}:
        return True

    advice_signals = [
        "what should i do",
        "help me",
        "any advice",
        "can you suggest",
        "give me steps",
        "how can i",
        "plan",
        "tips",
    ]

    stuck_signals = [
        "stuck",
        "overwhelmed",
        "cant cope",
        "can't cope",
        "dont know what to do",
        "don't know what to do",
    ]

    return any(token in lowered for token in advice_signals + stuck_signals)


def soften_direct_phrasing(reply: str) -> str:
    text = reply
    substitutions = [
        (r"\bthis is bad\b", "this sounds really heavy"),
        (r"\bthat is bad\b", "that sounds really tough"),
        (r"\bthis is dangerous\b", "this may be a sign you need extra support right now"),
        (r"\byou are doing it wrong\b", "you are doing your best under stress"),
        (r"\byou should\b", "you might consider"),
        (r"\byou must\b", "it may help to"),
        (r"\bserious problem\b", "important concern"),
    ]

    for pattern, replacement in substitutions:
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

    return text


def enforce_follow_up_question(reply: str) -> str:
    text = reply.strip()
    if not text:
        return (
            "Thank you for sharing that with me. "
            "I am here with you, and we can take this one step at a time.\n\n"
            + _FALLBACK_QUESTION
        )

    # Keep conversational output focused while guaranteeing one reflective question.
    question_count = len(re.findall(r"\?", text))
    if question_count == 0:
        return f"{text}\n\n{_FALLBACK_QUESTION}"

    if question_count > 1:
        last_question_idx = text.rfind("?")
        prefix = text[:last_question_idx]
        suffix = text[last_question_idx:]
        prefix = prefix.replace("?", ".")
        text = prefix + suffix

    return text
