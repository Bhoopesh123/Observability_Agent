import pytest

from app.agents.supervisor import SupervisorAgent
from app.models import AgentResult


class FakeGrafanaAgent:
    async def get_active_alerts(self):
        return AgentResult(
            ok=True,
            source="grafana",
            action="active_alerts",
            data={"count": 1, "alerts": [{"name": "HighCPU", "severity": "critical"}]},
        )

    async def list_dashboards(self, limit=25):
        return AgentResult(
            ok=True,
            source="grafana",
            action="list_dashboards",
            data={"count": 1, "dashboards": [{"title": "Node Overview", "uid": "node"}]},
        )

    async def query_prometheus(self, query, lookback_minutes=None, step_seconds=60):
        return AgentResult(
            ok=True,
            source="grafana",
            action="query_prometheus",
            data={"latest": [{"name": "value", "value": 42.0, "labels": {"instance": "local"}}]},
            queries=[{"expr": query}],
        )

    async def query_loki(self, query, lookback_minutes=None, limit=50):
        return AgentResult(
            ok=True,
            source="grafana",
            action="query_loki",
            data={"entries": []},
            queries=[{"expr": query}],
        )


@pytest.mark.asyncio
async def test_alert_question_returns_critical_status():
    supervisor = SupervisorAgent(FakeGrafanaAgent())

    response = await supervisor.handle_message("Are there active alerts?")

    assert response.status == "critical"
    assert "1 active" in response.answer
    assert response.key_findings == ["Critical: HighCPU"]


@pytest.mark.asyncio
async def test_health_summary_combines_alerts_and_metrics():
    supervisor = SupervisorAgent(FakeGrafanaAgent())

    response = await supervisor.handle_message("Summarize system health")

    assert response.status == "critical"
    assert "Active alerts: 1" in response.key_findings
    assert response.sources["grafana"] == ["active_alerts", "query_prometheus", "query_prometheus"]


@pytest.mark.asyncio
async def test_unknown_question_returns_guidance():
    supervisor = SupervisorAgent(FakeGrafanaAgent())

    response = await supervisor.handle_message("Tell me a joke")

    assert response.status == "unknown"
    assert "I can help" in response.answer
