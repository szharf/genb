import argparse

from scripts.check_phase1_release_gate import evaluate


def _args(**overrides):
    values = {
        "mode": "technical",
        "provider_evidence": None,
        "compliance_evidence": None,
        "sbom": None,
        "vulnerability_report": None,
        "capacity_report": None,
        "recovery_report": None,
    }
    values.update(overrides)
    return argparse.Namespace(**values)


def test_technical_gate_passes_only_repository_verifiable_checks() -> None:
    results, passed = evaluate(_args())
    assert passed
    assert results
    assert all(result.status == "PASS" for result in results)


def test_production_gate_fails_closed_when_external_evidence_is_absent() -> None:
    results, passed = evaluate(_args(mode="production"))
    assert not passed
    external = [result for result in results if result.gate_id.startswith("EXTERNAL_")]
    assert len(external) == 6
    assert all(result.status == "BLOCKED_EXTERNAL" for result in external)

