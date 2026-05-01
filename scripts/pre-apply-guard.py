#!/usr/bin/env python3
"""Pre-apply surface guard.

Reads a proposed_changes.json file describing what apply intends to create or modify,
then verifies every proposed surface is in the contract's selected_surfaces and no
rejected surface is being implemented.

Exit codes:
  0 — pass, proceed with apply
  1 — violations found, revise proposed_changes.json and retry
  2 — bad input (missing file, malformed JSON, contract unreadable)

Proposed changes file format:
  {
    "proposed_changes": [
      {
        "file": "skills/my-skill/SKILL.md",
        "operation": "create|edit|delete",
        "surface": "skill",
        "implements": "what this change does"
      }
    ]
  }

Surface names accepted (all aliases resolve to the canonical form shown):
  skill              — skills, skill-file, vibe-skill
  custom-tool        — tool, tools, basetool, base-tool, custom_tool
  mcp-server         — mcp, connector, mistral-connector, mcp_server
  middleware         — conversationmiddleware, conversation-middleware
  config             — config-key, toml-config, vibe-config, config_key
  hook               — hooks, hooks-toml, post-agent-turn-hook
  agent-profile      — profile, profiles, agent_profile
  source-modification — source, tier-d, agentloop, agent-loop, source_modification
  workflow-manifest  — manifest, workflow.yaml, workflow.json, workflow_manifest
  agents-md          — agents.md, .vibe/agents.md, agents_md
  scratchpad         — scratch, scratch-dir
  programmatic-output — programmatic, ci-output, --output-json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


SURFACE_ALIASES: dict[str, list[str]] = {
    "skill": ["skill", "skills", "skill-file", "vibe-skill", "skill_file"],
    "custom-tool": ["custom-tool", "tool", "tools", "basetool", "base-tool", "custom_tool"],
    "mcp-server": ["mcp", "mcp-server", "mcp_server", "connector", "mistral-connector"],
    "middleware": ["middleware", "conversationmiddleware", "conversation-middleware", "conversation_middleware"],
    "config": ["config", "config-key", "config_key", "toml-config", "vibe-config"],
    "hook": ["hook", "hooks", "hooks-toml", "post-agent-turn-hook", "hooks_toml"],
    "agent-profile": ["agent-profile", "agent_profile", "profile", "profiles"],
    "source-modification": ["source", "source-modification", "source_modification", "tier-d", "agentloop", "agent-loop"],
    "workflow-manifest": ["workflow-manifest", "workflow_manifest", "manifest", "workflow.yaml", "workflow.json"],
    "agents-md": ["agents.md", "agents-md", "agents_md", ".vibe/agents.md"],
    "scratchpad": ["scratchpad", "scratch", "scratch-dir"],
    "programmatic-output": ["programmatic", "programmatic-output", "ci-output", "--output-json"],
}

_ALIAS_TO_CANONICAL: dict[str, str] = {
    alias: canonical
    for canonical, aliases in SURFACE_ALIASES.items()
    for alias in aliases
}


def _canonical(surface: str) -> str | None:
    return _ALIAS_TO_CANONICAL.get(surface.strip().lower())


def _load_contract(search_dir: Path) -> tuple[dict[str, Any], Path]:
    """Find WORKFLOW_CONTRACT.json and follow contract_source if present."""
    candidates = [
        search_dir / "WORKFLOW_CONTRACT.json",
        search_dir.parent / "WORKFLOW_CONTRACT.json",
        Path.cwd() / "WORKFLOW_CONTRACT.json",
    ]
    wf_contract: Path | None = next((c for c in candidates if c.exists()), None)

    if wf_contract is None:
        # Fallback: standalone REALIZATION_CONTRACT.json
        rc_candidates = [
            search_dir / "REALIZATION_CONTRACT.json",
            search_dir.parent / "REALIZATION_CONTRACT.json",
            Path.cwd() / "REALIZATION_CONTRACT.json",
        ]
        rc = next((c for c in rc_candidates if c.exists()), None)
        if rc:
            return json.loads(rc.read_text()), rc
        raise FileNotFoundError("No WORKFLOW_CONTRACT.json or REALIZATION_CONTRACT.json found")

    contract = json.loads(wf_contract.read_text())

    # Follow contract_source pointer (realize mode)
    source_ref = contract.get("contract_source")
    if source_ref:
        source_path = wf_contract.parent / source_ref
        if source_path.exists():
            return json.loads(source_path.read_text()), source_path

    return contract, wf_contract


def _extract_surfaces(contract: dict[str, Any], status: str) -> set[str]:
    """Extract canonical surface names matching a given status."""
    surfaces: set[str] = set()

    # Standard design-phase contract: contract.design.surfaceDecisions[]
    design = contract.get("design", {})
    decisions = design.get("surfaceDecisions", [])

    # Also accept flat surfaceDecisions at root (some phases write it flat)
    if not decisions:
        decisions = contract.get("surfaceDecisions", [])

    for d in decisions:
        if isinstance(d, dict) and d.get("status") == status:
            c = _canonical(d.get("surface", ""))
            if c:
                surfaces.add(c)

    if status == "selected":
        # REALIZATION_CONTRACT.json: required_runtime_surfaces[]
        for item in contract.get("required_runtime_surfaces", []):
            s = item if isinstance(item, str) else item.get("surface", "")
            c = _canonical(s)
            if c:
                surfaces.add(c)
        # approved_fix_plan[].surface
        for item in contract.get("approved_fix_plan", []):
            if isinstance(item, dict):
                c = _canonical(item.get("surface", ""))
                if c:
                    surfaces.add(c)
        # Flat selected_surfaces[]
        for item in contract.get("selected_surfaces", []):
            s = item if isinstance(item, str) else item.get("surface", "")
            c = _canonical(s)
            if c:
                surfaces.add(c)

    if status in ("rejected", "not_applicable"):
        for item in contract.get("rejected_surfaces", []):
            s = item if isinstance(item, str) else item.get("surface", "")
            c = _canonical(s)
            if c:
                surfaces.add(c)

    return surfaces


def run_guard(proposed_path: str, cwd: str | None = None) -> dict[str, Any]:
    pf = Path(proposed_path)
    if not pf.exists():
        return {"pass": False, "exit_code": 2, "error": f"File not found: {proposed_path}"}

    try:
        proposed = json.loads(pf.read_text())
    except json.JSONDecodeError as e:
        return {"pass": False, "exit_code": 2, "error": f"JSON parse error in {proposed_path}: {e}"}

    changes = proposed.get("proposed_changes", [])
    if not isinstance(changes, list) or not changes:
        return {"pass": False, "exit_code": 2, "error": "proposed_changes must be a non-empty list"}

    search_dir = Path(cwd) if cwd else pf.parent
    try:
        contract, contract_path = _load_contract(search_dir)
    except FileNotFoundError as e:
        return {
            "pass": True,
            "exit_code": 0,
            "violations": [],
            "warnings": [
                f"No contract found ({e}). Surface guard skipped. "
                "Create WORKFLOW_CONTRACT.json to enable enforcement."
            ],
            "contract_path": None,
        }

    selected = _extract_surfaces(contract, "selected")
    rejected = _extract_surfaces(contract, "rejected") | _extract_surfaces(contract, "not_applicable")

    violations: list[dict[str, Any]] = []
    warnings: list[str] = []
    covered: set[str] = set()

    for i, change in enumerate(changes):
        if not isinstance(change, dict):
            violations.append({
                "index": i,
                "rule": "invalid-entry",
                "message": "Each proposed change must be a dict with file, operation, and surface keys.",
            })
            continue

        file_label = change.get("file", f"change[{i}]")
        op = change.get("operation", "unknown")

        if op == "delete":
            # Deletes remove existing files — not a new surface introduction; skip surface check.
            continue

        surface_raw = change.get("surface", "")
        if not surface_raw:
            warnings.append(
                f"{file_label}: no surface declared — cannot verify against contract. "
                "Add a surface field to enable enforcement."
            )
            continue

        canonical = _canonical(surface_raw)
        if canonical is None:
            warnings.append(
                f"{file_label}: surface '{surface_raw}' is not a recognized surface name. "
                f"Known surfaces: {', '.join(sorted(SURFACE_ALIASES))}."
            )
            continue

        if canonical in rejected:
            violations.append({
                "file": file_label,
                "rule": "rejected-surface",
                "surface": canonical,
                "message": (
                    f"Surface '{canonical}' was rejected in the contract. "
                    "Remove this change, or record a contract amendment via /vibe-workflow-update before proceeding."
                ),
            })
            continue

        if selected and canonical not in selected:
            violations.append({
                "file": file_label,
                "rule": "unauthorized-surface",
                "surface": canonical,
                "message": (
                    f"Surface '{canonical}' is not in the contract's selected surfaces "
                    f"({', '.join(sorted(selected))}). "
                    "Either this surface was not approved at design time, or the contract needs an amendment."
                ),
            })
        else:
            covered.add(canonical)

    # Every selected surface must have at least one proposed change covering it.
    for surface in sorted(selected - covered):
        violations.append({
            "rule": "missing-selected-surface",
            "surface": surface,
            "message": (
                f"Selected surface '{surface}' has no proposed implementation. "
                "Add the missing change to proposed_changes.json, or record a scoped deviation "
                "in the contract explaining why it is deferred."
            ),
        })

    result: dict[str, Any] = {
        "pass": len(violations) == 0,
        "exit_code": 0 if len(violations) == 0 else 1,
        "violations": violations,
        "warnings": warnings,
        "selected_surfaces": sorted(selected),
        "rejected_surfaces": sorted(rejected),
        "covered_surfaces": sorted(covered),
        "uncovered_surfaces": sorted(selected - covered),
        "contract_path": str(contract_path),
    }

    if violations:
        result["retry_guidance"] = (
            f"Found {len(violations)} violation(s). "
            "Revise proposed_changes.json to address each violation, then re-run pre-apply-guard.py. "
            "Do not write implementation files until this guard exits 0."
        )

    return result


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({
            "pass": False,
            "exit_code": 2,
            "error": "Usage: pre-apply-guard.py <proposed_changes.json> [cwd]",
        }, indent=2))
        sys.exit(2)

    result = run_guard(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
    print(json.dumps(result, indent=2))
    sys.exit(result.get("exit_code", 2))
