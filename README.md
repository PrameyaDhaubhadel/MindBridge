# MindBridge: Mental Health Chatbot Agent (DedalusLabs)

A friendly, evidence-informed mental health chatbot API with safety guardrails.

## What this does
- Uses DedalusLabs chat completions as the model backend.
- Uses a strict system prompt for tone and scientific grounding.
- Detects high-risk crisis language and escalates safely.
- Returns structured responses with risk metadata.
- Keeps a rolling per-user findings report in one file and updates it every turn.
- Includes a separate backend dashboard to inspect reports.
- Marks conversations as ended when user clicks End Conversation or after inactivity.
- Supports multi-user accounts (register/login) with personal conversations per user.
- Starts each new user conversation with a personalized check-in question.

## Important safety note
This project is for supportive conversation and psychoeducation only.
It is **not** a substitute for licensed mental healthcare, diagnosis, or emergency services.

## Project structure
- `app/main.py`: FastAPI app and `/chat` endpoint
- `app/dedalus_client.py`: DedalusLabs integration
- `app/safety.py`: risk detection and basic output sanitization
- `app/reporting.py`: persistent findings report updater
- `app/user_manager.py`: user account manager (register/login/profile)
- `app/prompts.py`: system prompt and crisis message
- `app/schemas.py`: API request and response models
- `reports/user_findings_report.json`: live report file updated as conversations continue
- `static/backend.html`: backend report dashboard UI
- `data/users.json`: user account store

## Setup
1. Create a virtual environment:
   - Windows PowerShell:
     ```powershell
     python -m venv .venv
     .\.venv\Scripts\Activate.ps1
     ```
2. Install dependencies:
   ```powershell
   .\.venv\Scripts\python.exe -m pip install -r requirements.txt
   ```
3. Configure environment:
   ```powershell
   Copy-Item .env.example .env
   ```
   Then set `DEDALUS_API_KEY` in `.env`.
4. Run server:
   ```powershell
   .\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
   ```
5. Open API docs:
   - `http://127.0.0.1:8000/docs`
6. Open web chat:
   - `http://127.0.0.1:8000/`
7. Open backend dashboard:
   - `http://127.0.0.1:8000/backend`

## Multi-user API endpoints
- `POST /auth/register`
- `POST /auth/login`
- `GET /auth/user/{user_id}`
- `GET /conversation/history/{user_id}`

## Example request
```bash
curl -X POST http://127.0.0.1:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user-1",
    "message": "I feel overwhelmed and cannot sleep.",
    "history": []
  }'
```

## Recommended improvements
- Replace keyword-based risk detection with a dedicated moderation or classifier model.
- Add geolocation-aware crisis hotline lookup.
- Add user consent and privacy retention settings.
- Add observability and audit logs with PII redaction.
- Add tests for safety and prompt behavior.

## Deploy on Vercel
This repository is configured for Vercel with:
- `api/index.py` as the serverless Python entrypoint
- `vercel.json` routing all paths to the FastAPI app

### 1) Push code to GitHub
Commit and push your latest changes to your GitHub repository.

### 2) Create a Vercel project
1. Go to Vercel dashboard and click Add New Project.
2. Import this GitHub repository.
3. Keep defaults (Framework Preset can stay as Other).

### 3) Set environment variables in Vercel
Add this required environment variable in Project Settings -> Environment Variables:
- `DEDALUS_API_KEY` = your Dedalus API key

### 4) Deploy
Click Deploy. Vercel will build and publish your app.

### 5) Verify
After deployment, open:
- `/health`
- `/docs`
- `/`
- `/backend`

One Vercel app serves both frontends:
- MindBridge chat UI at `/`
- Backend dashboard UI at `/backend`
