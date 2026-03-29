from __future__ import annotations

import os
from shutil import copyfile
from pathlib import Path

from fastapi import FastAPI, HTTPException
from dotenv import load_dotenv
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.dedalus_client import DedalusClient
from app.prompts import CRISIS_REPLY, SYSTEM_PROMPT
from app.mental_health_report_agent import MentalHealthReportAgent
from app.reporting import ReportStore
from app.response_rules import (
    enforce_follow_up_question,
    should_offer_actionable_options,
    soften_direct_phrasing,
)
from app.safety import assess_risk, strip_unsafe_content
from app.schemas import ChatRequest, ChatResponse
from app.user_manager import UserManager

load_dotenv()

app = FastAPI(title="MindBridge API", version="0.1.0")

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"


def _resolve_runtime_file(source: Path, runtime_relative: str) -> Path:
    # Vercel serverless file system is read-only except /tmp.
    if os.getenv("VERCEL"):
        runtime_base = Path("/tmp") / "mindbridge"
        target = runtime_base / runtime_relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists() and source.exists():
            copyfile(source, target)
        return target
    return source


REPORT_FILE = _resolve_runtime_file(
    BASE_DIR / "reports" / "user_findings_report.json",
    "reports/user_findings_report.json",
)
USERS_FILE = _resolve_runtime_file(
    BASE_DIR / "data" / "users.json",
    "data/users.json",
)
REPORT_STORE = ReportStore(REPORT_FILE)
USER_MANAGER = UserManager(USERS_FILE)
REPORT_AGENT = MentalHealthReportAgent()
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


class EndConversationRequest(BaseModel):
    user_id: str = Field(min_length=1, max_length=100)


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=6, max_length=120)
    display_name: str = Field(min_length=1, max_length=80)


class LoginRequest(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=6, max_length=120)


@app.get("/")
def home() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/backend")
def backend_page() -> FileResponse:
    return FileResponse(STATIC_DIR / "backend.html")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/auth/register")
def auth_register(payload: RegisterRequest) -> dict:
    try:
        user = USER_MANAGER.register(payload.username, payload.password, payload.display_name)
        return {"ok": True, "user": user}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/auth/login")
def auth_login(payload: LoginRequest) -> dict:
    try:
        user = USER_MANAGER.login(payload.username, payload.password)
        return {"ok": True, "user": user}
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


@app.get("/auth/user/{user_id}")
def auth_user(user_id: str) -> dict:
    user = USER_MANAGER.get_user(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return {"ok": True, "user": user}


@app.get("/conversation/history/{user_id}")
def conversation_history(user_id: str) -> dict:
    report = REPORT_STORE.get_user_report(user_id)
    if report is None:
        return {"ok": True, "history": []}

    turns = report.get("turns", [])
    history = []
    for turn in turns:
        user_text = turn.get("user")
        assistant_text = turn.get("assistant")
        if user_text:
            history.append({"role": "user", "content": user_text})
        if assistant_text:
            history.append({"role": "assistant", "content": assistant_text})

    return {"ok": True, "history": history[-20:]}


@app.get("/backend/api/reports")
def backend_reports() -> dict:
    return REPORT_STORE.get_all_reports()


@app.get("/backend/api/reports/{user_id}")
def backend_user_report(user_id: str) -> dict:
    report = REPORT_STORE.get_user_report(user_id)
    if report is None:
        raise HTTPException(status_code=404, detail="User report not found")
    return report


@app.get("/backend/api/reports/{user_id}/detailed")
def backend_user_detailed_report(user_id: str) -> dict:
    report = REPORT_STORE.get_user_report(user_id)
    if report is None:
        raise HTTPException(status_code=404, detail="User report not found")

    detailed = REPORT_AGENT.generate_detailed_report(report)
    return {
        "user_id": user_id,
        "detailed_report": detailed,
    }


@app.get("/backend/api/reports/username/{username}")
def backend_user_report_by_username(username: str) -> dict:
    report = REPORT_STORE.get_user_report_by_username(username)
    if report is None:
        raise HTTPException(status_code=404, detail="Username report not found")
    return report


@app.get("/backend/api/reports/username/{username}/detailed")
def backend_user_detailed_report_by_username(username: str) -> dict:
    report = REPORT_STORE.get_user_report_by_username(username)
    if report is None:
        raise HTTPException(status_code=404, detail="Username report not found")

    detailed = REPORT_AGENT.generate_detailed_report(report)
    return {
        "username": username,
        "detailed_report": detailed,
    }


@app.post("/backend/api/reports/username/{username}/detailed/dedalus")
async def backend_user_detailed_report_by_username_dedalus(username: str) -> dict:
    report = REPORT_STORE.get_user_report_by_username(username)
    if report is None:
        raise HTTPException(status_code=404, detail="Username report not found")

    system_prompt = (
        "You are a clinical documentation assistant for mental-health progress review. "
        "Create a human-readable, structured report for medical personnel based only on provided conversation history. "
        "Do not diagnose; describe observed patterns, trajectory, and follow-up considerations. "
        "Be neutral, respectful, and evidence-informed."
    )

    user_prompt = (
        "Generate a detailed but concise report with headings:\n"
        "1) Individual Overview\n"
        "2) Presenting Emotional Themes\n"
        "3) Functional Impact Signals\n"
        "4) Risk and Safety Signals\n"
        "5) Progress Trajectory Over Time\n"
        "6) Suggested Clinical Follow-up Topics\n"
        "7) Important Caveats\n\n"
        "Use plain human-readable text (not JSON).\n\n"
        f"Username: {username}\n"
        f"Display name: {report.get('display_name')}\n"
        f"Report snapshot: {report}\n"
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    try:
        client = DedalusClient()
        report_text = await client.complete_chat(messages)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Model provider error: {exc}") from exc

    return {
        "username": username,
        "provider": "dedalus",
        "human_readable_report": report_text,
    }


@app.delete("/backend/api/reports/username/{username}")
def backend_delete_user_report_by_username(username: str) -> dict:
    deleted_report = REPORT_STORE.delete_user_report_by_username(username)
    deleted_user = USER_MANAGER.delete_by_username(username)
    if not deleted_report and not deleted_user:
        raise HTTPException(status_code=404, detail="Username not found")

    return {
        "ok": True,
        "deleted_username": username,
        "deleted_report": deleted_report,
        "deleted_user_account": deleted_user,
    }


@app.post("/conversation/end")
def end_conversation(payload: EndConversationRequest) -> dict:
    report = REPORT_STORE.end_conversation(payload.user_id)
    if report is None:
        raise HTTPException(status_code=404, detail="User report not found")
    return {"ok": True, "report": report}


@app.post("/chat", response_model=ChatResponse)
async def chat(payload: ChatRequest) -> ChatResponse:
    user_id = payload.user_id or "anonymous"
    user = USER_MANAGER.get_user(user_id)
    username = (user or {}).get("username")
    display_name = (user or {}).get("display_name", "there")
    risk = assess_risk(payload.message)

    if risk == "high":
        reply = enforce_follow_up_question(CRISIS_REPLY)
        REPORT_STORE.update_user_turn(user_id, username, display_name, payload.message, reply, risk)
        return ChatResponse(reply=reply, risk_level=risk, escalated=True)

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.append(
        {
            "role": "system",
            "content": (
                f"The user display name is {display_name}. "
                "Use their name naturally sometimes to make the conversation personal, "
                "while staying warm and respectful."
            ),
        }
    )
    messages.extend(
        {"role": item.role, "content": item.content}
        for item in payload.history
        if item.role in {"user", "assistant"}
    )

    offer_options = should_offer_actionable_options(payload.message, risk)
    if offer_options:
        turn_policy = (
            "This user turn is likely to benefit from practical direction. "
            "After validation, include 2-4 concrete low-effort options."
        )
    else:
        turn_policy = (
            "This user turn is likely to benefit more from caring emotional presence. "
            "Do not force action steps. Use reflective support and one gentle follow-up question."
        )
    messages.append({"role": "system", "content": turn_policy})

    messages.append({"role": "user", "content": payload.message})

    try:
        client = DedalusClient()
        raw_reply = await client.complete_chat(messages)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Model provider error: {exc}") from exc

    safe_reply = strip_unsafe_content(raw_reply)
    safe_reply = soften_direct_phrasing(safe_reply)
    safe_reply = enforce_follow_up_question(safe_reply)
    REPORT_STORE.update_user_turn(user_id, username, display_name, payload.message, safe_reply, risk)
    return ChatResponse(reply=safe_reply, risk_level=risk, escalated=(risk == "medium"))
