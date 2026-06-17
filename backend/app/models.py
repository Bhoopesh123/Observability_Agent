from typing import Any, Literal

from pydantic import BaseModel, Field


SystemStatus = Literal["healthy", "warning", "critical", "unknown"]
Confidence = Literal["low", "medium", "high"]


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    conversation_id: str = Field(default="default", max_length=100)


class ChatResponse(BaseModel):
    answer: str
    status: SystemStatus
    confidence: Confidence
    key_findings: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    sources: dict[str, Any] = Field(default_factory=dict)
    raw: dict[str, Any] = Field(default_factory=dict)


class AgentResult(BaseModel):
    ok: bool
    source: str
    action: str
    data: dict[str, Any] = Field(default_factory=dict)
    errors: list[str] = Field(default_factory=list)
    queries: list[dict[str, Any]] = Field(default_factory=list)
