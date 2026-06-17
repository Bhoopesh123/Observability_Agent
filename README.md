# Observability Agent

A ChatGPT-style observability assistant with three components:

- `frontend/`: React chat UI 
- `backend/`: FastAPI API server and agent runtime
- `backend/app/agents/supervisor.py`: Supervisor/Orchestrator agent
- `backend/app/agents/grafana.py`: Grafana sub-agent

The MVP supports active alerts, health summaries, dashboard listing, Prometheus queries through Grafana, and Loki log queries when a datasource UID is configured.

## Architecture

```text
User
  -> React chat UI
  -> FastAPI /api/chat
  -> Supervisor Agent
  -> Grafana Agent
  -> Grafana HTTP APIs
  -> summarized response
```

## Setup

1. Copy environment values:

```powershell
Copy-Item .env.example .env
```

2. Install backend dependencies:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

3. Install frontend dependencies:

```powershell
cd ..\frontend
npm.cmd install
```

4. Configure `.env` with your Grafana URL and API key.

## Run

Backend:

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Or from PowerShell:

```powershell
.\backend\run_backend.ps1
```

Frontend:

```powershell
cd frontend
npm.cmd run dev -- --host 0.0.0.0 --port 3005
```

Or from PowerShell:

```powershell
.\frontend\run_frontend.ps1
```

Open the UI at `http://localhost:3005`.

## Example Questions

- Are there any active alerts?
- Summarize system health.
- What is CPU usage in the last 30 minutes?
- What is memory usage in the last 30 minutes?
- Show error logs for service checkout.
- List Grafana dashboards.

## API

`POST /api/chat`

```json
{
  "message": "Are there any active alerts?",
  "conversation_id": "default"
}
```

Response:

```json
{
  "answer": "There are no active alerts.",
  "status": "healthy",
  "confidence": "high",
  "key_findings": [],
  "recommendations": [],
  "sources": {
    "grafana": [],
    "queries": []
  },
  "raw": {}
}
```

## Tests

```powershell
cd backend
pytest
```

## Notes

- Secrets are read from environment variables only.
- If `OPENAI_API_KEY` is unset, responses are summarized locally.
- If Grafana is not configured or unreachable, the UI receives a clear `unknown` status response instead of a crash.
