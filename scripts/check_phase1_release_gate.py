from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class GateResult:
    gate_id: str
    status: str
    evidence: str
    sha256: str | None = None


def _hash(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(65_536), b""):
            digest.update(block)
    return digest.hexdigest()


def _technical_results() -> list[GateResult]:
    required = {
        "TECH_OPENAPI_RUNTIME": ROOT / "runtime-system-service/openapi/runtime-inference-v1.json",
        "TECH_OPENAPI_CONTROL": ROOT / "control-system-service/openapi/control-system-v1.json",
        "TECH_MIGRATION": ROOT / "control-system-service/migrations/001_long_term_memory.sql",
        "TECH_ALERTS": ROOT / "ops/phase1/prometheus-alerts.yml",
        "TECH_DASHBOARD": ROOT / "ops/phase1/grafana-dashboard.json",
        "TECH_RUNBOOK": ROOT / "docs/operation/CORE_COMPONENT_PHASE1_RUNBOOK.md",
    }
    results: list[GateResult] = []
    for gate_id, path in required.items():
        status = "PASS" if path.is_file() and path.stat().st_size > 0 else "FAIL"
        results.append(
            GateResult(
                gate_id,
                status,
                str(path.relative_to(ROOT)),
                _hash(path) if status == "PASS" else None,
            )
        )
    migration = required["TECH_MIGRATION"].read_text(encoding="utf-8").lower()
    results.append(
        GateResult(
            "TECH_NO_PHYSICAL_FOREIGN_KEYS",
            "PASS" if "foreign key" not in migration and " references " not in migration else "FAIL",
            "control-system-service/migrations/001_long_term_memory.sql",
        )
    )
    source = "\n".join(
        path.read_text(encoding="utf-8", errors="replace")
        for base in ("runtime-system-service/src", "control-system-service/src")
        for path in (ROOT / base).rglob("*.py")
    ).lower()
    results.append(
        GateResult(
            "TECH_NO_LEGACY_RUNTIME_SDK",
            "PASS" if "bank_agent_runtime" not in source and "bank-agent-runtime" not in source else "FAIL",
            "runtime-system-service/src + control-system-service/src",
        )
    )
    return results


def _external_result(gate_id: str, path_value: str | None) -> GateResult:
    if not path_value:
        return GateResult(gate_id, "BLOCKED_EXTERNAL", "not supplied")
    path = Path(path_value).resolve()
    if not path.is_file() or path.stat().st_size == 0:
        return GateResult(gate_id, "FAIL", str(path))
    return GateResult(gate_id, "PRESENT_REQUIRES_OWNER_REVIEW", str(path), _hash(path))


def evaluate(args: argparse.Namespace) -> tuple[list[GateResult], bool]:
    results = _technical_results()
    if args.mode == "production":
        results.extend(
            [
                _external_result("EXTERNAL_PROVIDER_ACCEPTANCE", args.provider_evidence),
                _external_result("EXTERNAL_DATA_COMPLIANCE", args.compliance_evidence),
                _external_result("EXTERNAL_RESOLVED_SBOM", args.sbom),
                _external_result("EXTERNAL_VULNERABILITY_SCAN", args.vulnerability_report),
                _external_result("EXTERNAL_CAPACITY_STABILITY", args.capacity_report),
                _external_result("EXTERNAL_BACKUP_RECOVERY", args.recovery_report),
            ]
        )
    passed = all(result.status == "PASS" for result in results)
    return results, passed


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("technical", "production"), default="technical")
    parser.add_argument("--output", required=True)
    parser.add_argument("--provider-evidence")
    parser.add_argument("--compliance-evidence")
    parser.add_argument("--sbom")
    parser.add_argument("--vulnerability-report")
    parser.add_argument("--capacity-report")
    parser.add_argument("--recovery-report")
    args = parser.parse_args()
    results, passed = evaluate(args)
    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(
            {
                "mode": args.mode,
                "passed": passed,
                "results": [asdict(result) for result in results],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return 0 if passed else 2


if __name__ == "__main__":
    raise SystemExit(main())

