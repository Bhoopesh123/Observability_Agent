from __future__ import annotations

import re
from dataclasses import dataclass

from app.agents.grafana import GrafanaAgent
from app.models import AgentResult, ChatResponse


@dataclass(frozen=True)
class Intent:
    name: str
    metric_query: str | None = None
    log_query: str | None = None


class SupervisorAgent:
    def __init__(self, grafana_agent: GrafanaAgent):
        self.grafana_agent = grafana_agent

    async def handle_message(self, message: str) -> ChatResponse:
        intent = self._classify(message)
        results: list[AgentResult] = []

        if intent.name == "active_alerts":
            results.append(await self.grafana_agent.get_active_alerts())
        elif intent.name == "dashboards":
            results.append(await self.grafana_agent.list_dashboards())
        elif intent.name == "metric_query" and intent.metric_query:
            results.append(await self.grafana_agent.query_prometheus(intent.metric_query))
        elif intent.name == "log_query" and intent.log_query:
            results.append(await self.grafana_agent.query_loki(intent.log_query))
        elif intent.name == "health_summary":
            results.append(await self.grafana_agent.get_active_alerts())
            results.append(await self.grafana_agent.query_prometheus(self._cpu_query()))
            results.append(await self.grafana_agent.query_prometheus(self._memory_query()))
        else:
            return ChatResponse(
                answer=(
                    "I can help with active alerts, health summaries, dashboards, "
                    "Prometheus metrics, and Loki error logs. Try asking: "
                    "'Summarize system health' or 'Are there active alerts?'"
                ),
                status="unknown",
                confidence="medium",
                recommendations=["Ask a Grafana-backed observability question."],
                sources={"grafana": [], "queries": []},
                raw={"intent": intent.name},
            )

        return self._summarize(intent, results)

    def _classify(self, message: str) -> Intent:
        text = message.lower().strip()

        if any(word in text for word in ["dashboard", "dashboards", "panel"]):
            return Intent("dashboards")

        if any(word in text for word in ["log", "logs", "error log", "exceptions", "stack trace"]):
            service = self._extract_service_name(text)
            selector = f'{{service="{service}"}}' if service else "{job=~\".+\"}"
            return Intent("log_query", log_query=f'{selector} |= "error"')

        if any(word in text for word in ["alert", "alerts", "firing"]):
            return Intent("active_alerts")

        if any(word in text for word in ["health", "status", "healthy", "down", "risky", "risk"]):
            return Intent("health_summary")

        if "cpu" in text:
            return Intent("metric_query", metric_query=self._cpu_query())

        if any(word in text for word in ["memory", "ram"]):
            return Intent("metric_query", metric_query=self._memory_query())

        if any(word in text for word in ["latency", "p95", "p99", "duration"]):
            return Intent(
                "metric_query",
                metric_query='histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket[5m])) by (le))',
            )

        if any(word in text for word in ["error rate", "5xx", "errors"]):
            return Intent(
                "metric_query",
                metric_query='sum(rate(http_requests_total{status=~"5.."}[5m]))',
            )

        return Intent("unknown")

    def _summarize(self, intent: Intent, results: list[AgentResult]) -> ChatResponse:
        errors = [error for result in results for error in result.errors]
        ok_results = [result for result in results if result.ok]
        queries = [query for result in results for query in result.queries]

        if errors and not ok_results:
            return ChatResponse(
                answer=f"I could not retrieve Grafana data. {errors[0]}",
                status="unknown",
                confidence="high",
                key_findings=["Grafana data is unavailable."],
                recommendations=[
                    "Check GRAFANA_URL, GRAFANA_API_KEY, and datasource UID settings.",
                    "Verify the backend can reach Grafana.",
                ],
                sources={"grafana": self._source_actions(results), "queries": queries},
                raw={"intent": intent.name, "results": [result.model_dump() for result in results]},
            )

        if intent.name == "active_alerts":
            return self._summarize_alerts(results[0])

        if intent.name == "dashboards":
            return self._summarize_dashboards(results[0])

        if intent.name == "metric_query":
            return self._summarize_metric(intent, results[0])

        if intent.name == "log_query":
            return self._summarize_logs(results[0])

        return self._summarize_health(results, errors)

    def _summarize_alerts(self, result: AgentResult) -> ChatResponse:
        alerts = result.data.get("alerts", [])
        count = result.data.get("count", 0)
        status = "healthy" if count == 0 else "critical"
        findings = [
            f"{alert.get('severity', 'unknown').title()}: {alert.get('name')}"
            for alert in alerts[:5]
        ]
        answer = "There are no active Grafana alerts." if count == 0 else f"There are {count} active Grafana alert(s)."
        return ChatResponse(
            answer=answer,
            status=status,
            confidence="high",
            key_findings=findings,
            recommendations=self._alert_recommendations(alerts),
            sources={"grafana": ["active_alerts"], "queries": []},
            raw={"alerts": alerts},
        )

    def _summarize_dashboards(self, result: AgentResult) -> ChatResponse:
        dashboards = result.data.get("dashboards", [])
        findings = [dashboard.get("title", "Untitled dashboard") for dashboard in dashboards[:8]]
        return ChatResponse(
            answer=f"I found {result.data.get('count', 0)} Grafana dashboard(s).",
            status="unknown",
            confidence="high",
            key_findings=findings,
            recommendations=["Ask for a specific dashboard UID if you want panel-level inspection."],
            sources={"grafana": ["list_dashboards"], "queries": []},
            raw={"dashboards": dashboards},
        )

    def _summarize_metric(self, intent: Intent, result: AgentResult) -> ChatResponse:
        values = result.data.get("latest", [])
        if not values:
            return ChatResponse(
                answer="The metric query ran, but Grafana returned no time series.",
                status="unknown",
                confidence="medium",
                key_findings=["No metric samples were returned for the selected time range."],
                recommendations=["Confirm the datasource UID and metric names for this environment."],
                sources={"grafana": [result.action], "queries": result.queries},
                raw={"result": result.model_dump()},
            )

        findings = [self._format_metric_value(item) for item in values[:6]]
        return ChatResponse(
            answer=f"The metric query returned {len(values)} latest series value(s).",
            status="unknown",
            confidence="medium",
            key_findings=findings,
            recommendations=["Inspect the raw series or narrow the query by service/instance if needed."],
            sources={"grafana": [result.action], "queries": result.queries},
            raw={"metric_query": intent.metric_query, "values": values},
        )

    def _summarize_logs(self, result: AgentResult) -> ChatResponse:
        entries = result.data.get("entries", [])
        if not entries:
            return ChatResponse(
                answer="I did not find matching error logs in the selected lookback window.",
                status="healthy",
                confidence="medium",
                key_findings=[],
                recommendations=["Increase the lookback window or specify a service name if you expected errors."],
                sources={"grafana": [result.action], "queries": result.queries},
                raw={"entries": entries},
            )

        findings = [entry.get("line", "")[:240] for entry in entries[:5]]
        return ChatResponse(
            answer=f"I found {len(entries)} matching log entrie(s).",
            status="warning",
            confidence="medium",
            key_findings=findings,
            recommendations=["Review the recurring errors and correlate them with recent deploys or alerts."],
            sources={"grafana": [result.action], "queries": result.queries},
            raw={"entries": entries},
        )

    def _summarize_health(self, results: list[AgentResult], errors: list[str]) -> ChatResponse:
        alert_result = next((result for result in results if result.action == "active_alerts"), None)
        metric_results = [result for result in results if result.action == "query_prometheus" and result.ok]
        alert_count = alert_result.data.get("count", 0) if alert_result and alert_result.ok else 0
        status = "healthy" if alert_count == 0 and not errors else "warning"
        if alert_count > 0:
            status = "critical"

        findings = []
        if alert_result and alert_result.ok:
            findings.append(f"Active alerts: {alert_count}")
        for result in metric_results:
            latest = result.data.get("latest", [])
            if latest:
                findings.extend(self._format_metric_value(item) for item in latest[:3])
        findings.extend(f"Data gap: {error}" for error in errors[:3])

        answer = (
            "System health looks healthy based on available Grafana signals."
            if status == "healthy"
            else "System health needs attention based on available Grafana signals."
        )

        return ChatResponse(
            answer=answer,
            status=status,
            confidence="medium",
            key_findings=findings,
            recommendations=self._health_recommendations(alert_count, errors),
            sources={"grafana": self._source_actions(results), "queries": [query for result in results for query in result.queries]},
            raw={"results": [result.model_dump() for result in results]},
        )

    def _alert_recommendations(self, alerts: list[dict]) -> list[str]:
        if not alerts:
            return ["No immediate action is required from active alerts."]
        return [
            "Open the highest-severity alert first and inspect affected labels.",
            "Correlate alert start time with deploys, traffic changes, and infrastructure events.",
        ]

    def _health_recommendations(self, alert_count: int, errors: list[str]) -> list[str]:
        recommendations = []
        if alert_count:
            recommendations.append("Triage active alerts before deeper metric exploration.")
        if errors:
            recommendations.append("Fix Grafana datasource configuration gaps to improve confidence.")
        if not recommendations:
            recommendations.append("Continue monitoring alerts, CPU, memory, latency, and error rate.")
        return recommendations

    def _source_actions(self, results: list[AgentResult]) -> list[str]:
        return [result.action for result in results]

    def _format_metric_value(self, item: dict) -> str:
        labels = item.get("labels") or {}
        label_text = ", ".join(f"{key}={value}" for key, value in labels.items())
        value = item.get("value")
        name = item.get("name", "value")
        if isinstance(value, (int, float)):
            value_text = f"{value:.4g}"
        else:
            value_text = str(value)
        return f"{name}: {value_text}" + (f" ({label_text})" if label_text else "")

    def _extract_service_name(self, text: str) -> str | None:
        match = re.search(r"(?:service|app|application)\s+([a-z0-9_.-]+)", text)
        return match.group(1) if match else None

    def _cpu_query(self) -> str:
        return '100 - (avg by (instance) (rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)'

    def _memory_query(self) -> str:
        return "(1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)) * 100"
