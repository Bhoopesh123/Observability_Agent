from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.agents.grafana import GrafanaAgent
from app.agents.supervisor import SupervisorAgent
from app.config import get_settings
from app.models import ChatRequest, ChatResponse


settings = get_settings()
grafana_agent = GrafanaAgent(settings)
supervisor_agent = SupervisorAgent(grafana_agent)

app = FastAPI(
    title="Observability Agent",
    description="ChatGPT-style observability assistant backed by Grafana.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    return await supervisor_agent.handle_message(request.message)
