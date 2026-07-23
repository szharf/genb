import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def test_dashboard_is_valid_json_and_uses_bounded_metric_dimensions() -> None:
    dashboard = json.loads((ROOT / "grafana-dashboard.json").read_text(encoding="utf-8"))
    expressions = "\n".join(
        target["expr"]
        for panel in dashboard["panels"]
        for target in panel["targets"]
    )
    assert len(dashboard["panels"]) >= 6
    assert "runtime_http_duration_seconds_bucket" in expressions
    assert "control_system_http_duration_seconds_bucket" in expressions
    for forbidden in ("tenantId", "userId", "agentId", "sessionId", "token"):
        assert forbidden not in expressions


def test_every_alert_has_severity_summary_and_runbook() -> None:
    content = (ROOT / "prometheus-alerts.yml").read_text(encoding="utf-8")
    alert_count = content.count("      - alert:")
    assert alert_count >= 7
    assert content.count("          severity:") == alert_count
    assert content.count("          summary:") == alert_count
    assert content.count("          runbook:") == alert_count
    for metric in (
        "runtime_http_requests_total",
        "runtime_http_duration_seconds_bucket",
        "control_system_http_requests_total",
        "control_system_http_duration_seconds_bucket",
        "long_term_extraction_queue_depth",
    ):
        assert metric in content

