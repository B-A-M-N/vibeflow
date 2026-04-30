#!/usr/bin/env python3
"""Shared workflow manifest loader and normalizer for VibeFlow tooling."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover - depends on runtime environment
    yaml = None


PHASE_ALIASES = {
    "name": "id",
    "entry_criteria": "entry",
    "exit_criteria": "exit",
    "retry_budget": "retryLimit",
}


def load_workflow_manifest(manifest_path: str | Path) -> tuple[dict[str, Any], list[str]]:
    """Load JSON/YAML workflow manifest and normalize canonical field names.

    Canonical phase fields are:
    - id
    - entry
    - exit
    - retryLimit, where 0 means the phase does not retry

    Legacy aliases are accepted but reported as warnings:
    - name -> id
    - entry_criteria -> entry
    - exit_criteria -> exit
    - retry_budget -> retryLimit
    """

    path = Path(manifest_path)
    data = _load_structured_file(path)
    if not isinstance(data, dict):
        raise ValueError("Workflow manifest must be a JSON/YAML object")
    return normalize_workflow_manifest(data)


def normalize_workflow_manifest(manifest: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    warnings: list[str] = []
    normalized = dict(manifest)
    phases = normalized.get("phases", [])
    if phases is None:
        phases = []
    if not isinstance(phases, list):
        raise ValueError("Workflow manifest field 'phases' must be a list")

    normalized_phases = []
    for idx, phase in enumerate(phases):
        if not isinstance(phase, dict):
            raise ValueError(f"Phase at index {idx} must be an object")
        phase = dict(phase)
        for old, new in PHASE_ALIASES.items():
            if old in phase:
                if new not in phase:
                    phase[new] = phase[old]
                    warnings.append(f"phases[{idx}].{old} normalized to phases[{idx}].{new}")
                else:
                    warnings.append(f"phases[{idx}].{old} ignored because canonical phases[{idx}].{new} is present")
        if "retryLimit" in phase:
            phase["retryLimit"] = _coerce_retry_limit(phase["retryLimit"], idx)
        normalized_phases.append(phase)

    normalized["phases"] = normalized_phases
    return normalized, warnings


def write_json(path: str | Path, data: dict[str, Any]) -> str:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(data, indent=2) + "\n")
    return str(output_path)


def _load_structured_file(path: Path) -> Any:
    text = path.read_text()
    if path.suffix.lower() in {".yaml", ".yml"}:
        if yaml is None:
            raise ImportError("PyYAML is required to parse YAML manifests. Install with: pip install pyyaml")
        return yaml.safe_load(text)
    return json.loads(text)


def _coerce_retry_limit(value: Any, phase_index: int) -> int:
    try:
        retry_limit = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"phases[{phase_index}].retryLimit must be an integer") from exc
    if retry_limit < 0:
        raise ValueError(f"phases[{phase_index}].retryLimit must be >= 0")
    return retry_limit
