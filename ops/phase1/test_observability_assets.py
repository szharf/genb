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


def test_python_sboms_are_resolved_cyclonedx_without_known_vulnerabilities() -> None:
    for name, minimum_components in (
        ("runtime-sbom.cdx.json", 15),
        ("control-sbom.cdx.json", 20),
    ):
        sbom = json.loads((ROOT / name).read_text(encoding="utf-8"))
        assert sbom["bomFormat"] == "CycloneDX"
        assert len(sbom["components"]) >= minimum_components
        assert "vulnerabilities" not in sbom
        components = {item["name"]: item["version"] for item in sbom["components"]}
        assert components["starlette"] == "1.3.1"
        if name.startswith("control"):
            assert components["cryptography"] == "48.0.1"
