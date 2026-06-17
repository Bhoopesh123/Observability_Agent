import pytest

from app.agents.grafana import GrafanaAgent
from app.config import Settings


@pytest.mark.asyncio
async def test_prometheus_query_reports_missing_datasource_uid():
    settings = Settings(GRAFANA_URL="http://grafana.local", GRAFANA_API_KEY="token", DEFAULT_DATASOURCE_UID="")
    agent = GrafanaAgent(settings)

    result = await agent.query_prometheus("up")

    assert result.ok is False
    assert "DEFAULT_DATASOURCE_UID" in result.errors[0]


@pytest.mark.asyncio
async def test_alerts_report_missing_grafana_configuration():
    settings = Settings(GRAFANA_URL="", GRAFANA_API_KEY="")
    agent = GrafanaAgent(settings)

    result = await agent.get_active_alerts()

    assert result.ok is False
    assert "Grafana is not configured" in result.errors[0]
