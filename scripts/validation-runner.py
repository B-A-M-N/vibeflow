#!/usr/bin/env python3
"""Serial VibeFlow validator that always emits evidence."""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from workflow_manifest import load_workflow_manifest, write_json


ROOT = Path(__file__).resolve().parent
DEFAULT_EVIDENCE = ".vibe-workflow/evidence/latest.json"
DEFAULT_REPORT_DIR = ".vibe-workflow/reports"


def run_validation(manifest_path: str, evidence_path: str | None = None, report_dir: str = DEFAULT_REPORT_DIR) -> dict[str, Any]:
    manifest_file = Path(manifest_path)
    evidence_out = evidence_path or _declared_evidence_path(manifest_file)
    checks: list[dict[str, Any]] = []

    lint = _run_check("workflow-linter", [sys.executable, str(ROOT / "workflow-linter.py"), str(manifest_file)])
    checks.append(lint)

    simulator = _run_check(
        "dry-run-simulator",
        [sys.executable, str(ROOT / "dry-run-simulator.py"), str(manifest_file), "validation", evidence_out],
    )
    checks.append(simulator)

    gate = _run_check("gate-engine", [sys.executable, str(ROOT / "gate-engine.py"), str(manifest_file)])
    checks.append(gate)

    convergence = None
    if Path(evidence_out).exists():
        convergence = _run_check(
            "convergence-scorer",
            [sys.executable, str(ROOT / "convergence-scorer.py"), evidence_out, str(manifest_file)],
        )
        checks.append(convergence)
    else:
        checks.append({
            "name": "convergence-scorer",
            "passed": False,
            "skipped": True,
            "failure_domain": "generated_workflow",
            "blocking_reason": "evidence_missing",
            "safe_next_action": "repair dry-run or schema failure before convergence scoring",
        })

    evidence = _build_evidence(manifest_file, checks, evidence_out)
    write_json(evidence_out, evidence)

    reporter = _run_check("evidence-reporter", [sys.executable, str(ROOT / "evidence-reporter.py"), evidence_out, report_dir])
    checks.append(reporter)

    evidence = _build_evidence(manifest_file, checks, evidence_out)
    evidence["report_generated"] = reporter.get("passed", False)
    evidence["report_output"] = reporter.get("stdout", "").strip()
    write_json(evidence_out, evidence)
    return evidence


def _declared_evidence_path(manifest_file: Path) -> str:
    try:
        manifest, _warnings = load_workflow_manifest(manifest_file)
    except Exception:
        return DEFAULT_EVIDENCE
    return manifest.get("tooling", {}).get("evidenceOutput", DEFAULT_EVIDENCE)


def _run_check(name: str, command: list[str]) -> dict[str, Any]:
    proc = subprocess.run(command, capture_output=True, text=True)
    parsed = _parse_json(proc.stdout)
    check = {
        "name": name,
        "command": command,
        "exit_code": proc.returncode,
        "passed": proc.returncode == 0,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "parsed": parsed,
    }
    check.update(_classify_check(name, check))
    return check


def _parse_json(text: str) -> Any:
    stripped = text.strip()
    if not stripped or not stripped.startswith(("{", "[")):
        return None
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        return None


def _classify_check(name: str, check: dict[str, Any]) -> dict[str, Any]:
    if check["passed"]:
        return {
            "failure_domain": None,
            "is_design_flaw": False,
            "is_validation_harness_bug": False,
            "safe_next_action": "continue",
        }

    parsed = check.get("parsed")
    violations = parsed.get("violations", []) if isinstance(parsed, dict) else []
    rules = {v.get("rule") for v in violations if isinstance(v, dict)}
    stderr = check.get("stderr", "")

    if "parse-error" in rules or "import-error" in rules or "Traceback" in stderr:
        return {
            "failure_domain": "plugin_tooling",
            "is_design_flaw": False,
            "is_validation_harness_bug": True,
            "blocking_reason": "validator_or_parser_failed",
            "safe_next_action": "fix validation harness before redesigning workflow",
        }
    if name in {"workflow-linter", "gate-engine", "convergence-scorer"}:
        return {
            "failure_domain": "generated_workflow",
            "is_design_flaw": False,
            "is_validation_harness_bug": False,
            "blocking_reason": "generated_workflow_failed_contract",
            "safe_next_action": "repair generated manifest/tooling contract",
        }
    if name == "dry-run-simulator":
        return {
            "failure_domain": "generated_workflow",
            "is_design_flaw": False,
            "is_validation_harness_bug": False,
            "blocking_reason": "dry_run_failed",
            "safe_next_action": "repair executable workflow inputs or required tools",
        }
    return {
        "failure_domain": "environment",
        "is_design_flaw": False,
        "is_validation_harness_bug": False,
        "blocking_reason": "external_check_failed",
        "safe_next_action": "inspect command output",
    }


def _build_evidence(manifest_file: Path, checks: list[dict[str, Any]], evidence_out: str) -> dict[str, Any]:
    failures = [check for check in checks if not check.get("passed")]
    blocking = failures[0] if failures else None
    return {
        "validation_started": True,
        "timestamp": datetime.now().isoformat(),
        "workflow_id": manifest_file.stem,
        "manifest_path": str(manifest_file),
        "evidence_path": evidence_out,
        "checks_run": checks,
        "checks_failed": failures,
        "dry_run_executed": _check_passed(checks, "dry-run-simulator"),
        "blocking_reason": blocking.get("blocking_reason") if blocking else None,
        "failure_domain": blocking.get("failure_domain") if blocking else None,
        "is_design_flaw": blocking.get("is_design_flaw", False) if blocking else False,
        "is_validation_harness_bug": blocking.get("is_validation_harness_bug", False) if blocking else False,
        "safe_next_action": blocking.get("safe_next_action", "continue") if blocking else "continue",
        "verdict": "READY" if not failures else "NEEDS_REWORK",
        "status": "completed" if not failures else "failed",
        "timeline": _simulator_timeline(checks),
        "tools_called": _simulator_tools(checks),
        "files_read": [],
        "files_changed": [],
        "commands": [{"cmd": " ".join(check["command"]), "status": "pass" if check["passed"] else "fail"} for check in checks],
        "tests_passed": [check["name"] for check in checks if check.get("passed")],
        "tests_failed": [check["name"] for check in failures],
        "gates": _gate_results(checks),
        "gates_passed": not failures,
        "retry_count": 0,
        "recommendations": [] if not failures else [blocking.get("safe_next_action", "repair failing check")],
    }


def _check_passed(checks: list[dict[str, Any]], name: str) -> bool:
    return any(check.get("name") == name and check.get("passed") for check in checks)


def _parsed_for(checks: list[dict[str, Any]], name: str) -> Any:
    for check in checks:
        if check.get("name") == name:
            return check.get("parsed")
    return None


def _simulator_timeline(checks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    parsed = _parsed_for(checks, "dry-run-simulator")
    return parsed.get("timeline", []) if isinstance(parsed, dict) else []


def _simulator_tools(checks: list[dict[str, Any]]) -> dict[str, int]:
    parsed = _parsed_for(checks, "dry-run-simulator")
    return parsed.get("tools_called", {}) if isinstance(parsed, dict) else {}


def _gate_results(checks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    parsed = _parsed_for(checks, "gate-engine")
    return parsed.get("gates", []) if isinstance(parsed, dict) else []


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: validation-runner.py <manifest.json|manifest.yaml> [evidence_out] [report_dir]")
        sys.exit(1)
    evidence = run_validation(
        sys.argv[1],
        sys.argv[2] if len(sys.argv) > 2 else None,
        sys.argv[3] if len(sys.argv) > 3 else DEFAULT_REPORT_DIR,
    )
    print(json.dumps(evidence, indent=2))
    sys.exit(0 if evidence["verdict"] == "READY" else 1)
