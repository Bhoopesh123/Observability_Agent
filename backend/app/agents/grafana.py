from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

from app.config import Settings
from app.models import AgentResult


class GrafanaAgent:
    """Small Grafana API client that returns normalized agent results."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.base_url = (settings.grafana_url or "").rstrip("/")

    @property
    def configured(self) -> bool:
        return bool(self.base_url and self.settings.grafana_api_key)

    def _headers(self) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self.settings.grafana_api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if self.settings.grafana_org_id is not None:
            headers["X-Grafana-Org-Id"] = str(self.settings.grafana_org_id)
        return headers

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> Any:
        if not self.configured:
            raise RuntimeError("Grafana is not configured. Set GRAFANA_URL and GRAFANA_API_KEY.")

        async with httpx.AsyncClient(timeout=self.settings.request_timeout_seconds) as client:
            response = await client.request(
                method,
                f"{self.base_url}{path}",
                headers=self._headers(),
                params=params,
                json=json,
            )
            response.raise_for_status()
            return response.json()

    async def get_active_alerts(self) -> AgentResult:
        try:
            payload = await self._request("GET", "/api/alertmanager/grafana/api/v2/alerts")
            alerts = payload if isinstance(payload, list) else payload.get("alerts", [])
            active_alerts = [alert for alert in alerts if alert.get("status", {}).get("state") != "suppressed"]
            return AgentResult(
                ok=True,
                source="grafana",
                action="active_alerts",
                data={
                    "count": len(active_alerts),
                    "alerts": [self._normalize_alert(alert) for alert in active_alerts],
                },
            )
        except Exception as exc:
            return self._error_result("active_alerts", exc)

    async def list_dashboards(self, limit: int = 25) -> AgentResult:
        try:
            payload = await self._request(
                "GET",
                "/api/search",
                params={"type": "dash-db", "limit": limit},
            )
            dashboards = payload if isinstance(payload, list) else []
            return AgentResult(
                ok=True,
                source="grafana",
                action="list_dashboards",
                data={
                    "count": len(dashboards),
                    "dashboards": [
                        {
                            "uid": item.get("uid"),
                            "title": item.get("title"),
                            "url": item.get("url"),
                            "folder": item.get("folderTitle"),
                        }
                        for item in dashboards
                    ],
                },
            )
        except Exception as exc:
            return self._error_result("list_dashboards", exc)

    async def query_prometheus(
        self,
        query: str,
        *,
        lookback_minutes: int | None = None,
        step_seconds: int = 60,
    ) -> AgentResult:
        datasource_uid = self.settings.default_datasource_uid
        if not datasource_uid:
            return AgentResult(
                ok=False,
                source="grafana",
                action="query_prometheus",
                errors=["DEFAULT_DATASOURCE_UID is not configured."],
                queries=[{"expr": query}],
            )

        lookback = lookback_minutes or self.settings.default_lookback_minutes
        end = datetime.now(UTC)
        start = end - timedelta(minutes=lookback)
        request_body = {
            "queries": [
                {
                    "refId": "A",
                    "datasource": {"uid": datasource_uid},
                    "expr": query,
                    "queryType": "timeSeriesQuery",
                    "intervalMs": step_seconds * 1000,
                    "maxDataPoints": 600,
                }
            ],
            "from": str(int(start.timestamp() * 1000)),
            "to": str(int(end.timestamp() * 1000)),
        }

        try:
            payload = await self._request("POST", "/api/ds/query", json=request_body)
            frames = payload.get("results", {}).get("A", {}).get("frames", [])
            return AgentResult(
                ok=True,
                source="grafana",
                action="query_prometheus",
                data={
                    "datasource_uid": datasource_uid,
                    "lookback_minutes": lookback,
                    "series_count": len(frames),
                    "latest": self._latest_values(frames),
                },
                queries=[{"expr": query, "datasource_uid": datasource_uid}],
            )
        except Exception as exc:
            return self._error_result("query_prometheus", exc, queries=[{"expr": query}])

    async def query_loki(
        self,
        query: str,
        *,
        lookback_minutes: int | None = None,
        limit: int = 50,
    ) -> AgentResult:
        datasource_uid = self.settings.default_loki_datasource_uid
        if not datasource_uid:
            return AgentResult(
                ok=False,
                source="grafana",
                action="query_loki",
                errors=["DEFAULT_LOKI_DATASOURCE_UID is not configured."],
                queries=[{"expr": query}],
            )

        lookback = lookback_minutes or self.settings.default_lookback_minutes
        end = datetime.now(UTC)
        start = end - timedelta(minutes=lookback)
        request_body = {
            "queries": [
                {
                    "refId": "A",
                    "datasource": {"uid": datasource_uid},
                    "expr": query,
                    "queryType": "range",
                    "maxLines": limit,
                }
            ],
            "from": str(int(start.timestamp() * 1000)),
            "to": str(int(end.timestamp() * 1000)),
        }

        try:
            payload = await self._request("POST", "/api/ds/query", json=request_body)
            frames = payload.get("results", {}).get("A", {}).get("frames", [])
            return AgentResult(
                ok=True,
                source="grafana",
                action="query_loki",
                data={
                    "datasource_uid": datasource_uid,
                    "lookback_minutes": lookback,
                    "entries": self._log_entries(frames),
                },
                queries=[{"expr": query, "datasource_uid": datasource_uid}],
            )
        except Exception as exc:
            return self._error_result("query_loki", exc, queries=[{"expr": query}])

    def _error_result(
        self,
        action: str,
        exc: Exception,
        *,
        queries: list[dict[str, Any]] | None = None,
    ) -> AgentResult:
        message = str(exc)
        if isinstance(exc, httpx.HTTPStatusError):
            message = f"Grafana returned HTTP {exc.response.status_code} for {exc.request.method} {exc.request.url.path}."
        return AgentResult(
            ok=False,
            source="grafana",
            action=action,
            errors=[message],
            queries=queries or [],
        )

    def _normalize_alert(self, alert: dict[str, Any]) -> dict[str, Any]:
        labels = alert.get("labels", {})
        annotations = alert.get("annotations", {})
        return {
            "name": labels.get("alertname") or labels.get("rule_uid") or "Unnamed alert",
            "state": alert.get("status", {}).get("state", "active"),
            "severity": labels.get("severity", "unknown"),
            "summary": annotations.get("summary") or annotations.get("description"),
            "starts_at": alert.get("startsAt"),
            "labels": labels,
        }

    def _latest_values(self, frames: list[dict[str, Any]]) -> list[dict[str, Any]]:
        latest = []
        for frame in frames:
            schema_fields = frame.get("schema", {}).get("fields", [])
            values = frame.get("data", {}).get("values", [])
            if len(values) < 2:
                continue

            time_values = values[0]
            metric_values = values[1]
            if not metric_values:
                continue

            latest.append(
                {
                    "name": schema_fields[1].get("name", "value") if len(schema_fields) > 1 else "value",
                    "labels": schema_fields[1].get("labels", {}) if len(schema_fields) > 1 else {},
                    "timestamp": time_values[-1] if time_values else None,
                    "value": metric_values[-1],
                }
            )
        return latest

    def _log_entries(self, frames: list[dict[str, Any]]) -> list[dict[str, Any]]:
        entries = []
        for frame in frames:
            values = frame.get("data", {}).get("values", [])
            if len(values) < 2:
                continue
            timestamps = values[0]
            lines = values[1]
            for timestamp, line in zip(timestamps, lines):
                entries.append({"timestamp": timestamp, "line": line})
        return entries[:50]
