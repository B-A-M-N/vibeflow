#!/usr/bin/env python3
"""Validate VibeFlow design candidates before selecting an architecture."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


REQUIRED_EDGE_FIELDS = ("requirement", "surface", "mechanism", "proof", "failureMode")
REQUIRED_SCORE_FIELDS = (
    "effectiveness",
    "groundedness",
    "cost",
    "maintainability",
    "observability",
    "convergence",
)


def lint_strategy_candidates(path: str | Path) -> dict[str, Any]:
    with Path(path).open() as f:
        data = json.load(f)

    findings: list[dict[str, Any]] = []
    candidates = data.get("candidates")
    winner = data.get("winner")

    if not isinstance(candidates, list) or not candidates:
        findings.append(_finding(
            "candidates-missing",
            "error",
            "DESIGN_CANDIDATES.json must contain a non-empty candidates array.",
        ))
        return _result(findings, winner=None, candidate_count=0)

    if len(candidates) < 3:
        findings.append(_finding(
            "candidate-set-too-small",
            "warning",
            "Strategy search should normally compare 3-5 candidates unless the design space is genuinely narrow.",
        ))
    if len(candidates) > 5:
        findings.append(_finding(
            "candidate-set-too-large",
            "warning",
            "Strategy search should keep candidate count to 3-5 so evaluation stays cheap and focused.",
        ))

    ids: set[str] = set()
    scored_candidates: list[tuple[str, float]] = []
    winner_candidate: dict[str, Any] | None = None

    for idx, candidate in enumerate(candidates):
        if not isinstance(candidate, dict):
            findings.append(_finding("candidate-invalid", "error", f"Candidate at index {idx} must be an object."))
            continue
        candidate_id = candidate.get("id")
        if not _nonempty_text(candidate_id):
            findings.append(_finding("candidate-missing-id", "error", f"Candidate at index {idx} must have an id."))
            candidate_id = f"<index:{idx}>"
        elif candidate_id in ids:
            findings.append(_finding("candidate-duplicate-id", "error", f"Candidate id '{candidate_id}' is duplicated.", str(candidate_id)))
        else:
            ids.add(candidate_id)

        if candidate_id == winner:
            winner_candidate = candidate

        _check_candidate(candidate, str(candidate_id), findings)
        score = _weighted_score(candidate.get("scores", {}))
        if score is not None:
            scored_candidates.append((str(candidate_id), score))

    if not _nonempty_text(winner):
        findings.append(_finding("winner-missing", "error", "DESIGN_CANDIDATES.json must name a winner candidate id."))
    elif winner not in ids:
        findings.append(_finding("winner-not-found", "error", f"Winner '{winner}' does not match any candidate id.", str(winner)))
    elif winner_candidate is not None:
        rejected = winner_candidate.get("rejectedBecause", [])
        if isinstance(rejected, list) and any(_nonempty_text(item) for item in rejected):
            findings.append(_finding("winner-is-rejected", "error", "The selected winner has rejection reasons recorded.", str(winner)))
        if not _nonempty_text(data.get("winnerRationale")):
            findings.append(_finding("winner-rationale-missing", "error", "The selected winner needs a rationale.", str(winner)))

    if scored_candidates and winner in ids:
        top_id, top_score = max(scored_candidates, key=lambda item: item[1])
        winner_score = dict(scored_candidates).get(str(winner))
        if winner_score is not None and top_id != winner and top_score - winner_score >= 1.0:
            findings.append(_finding(
                "winner-not-highest-scoring",
                "warning",
                f"Winner '{winner}' is materially lower scoring than '{top_id}'. Document the override in winnerRationale.",
                str(winner),
            ))

    return _result(findings, winner=winner, candidate_count=len(candidates))


def _check_candidate(candidate: dict[str, Any], candidate_id: str, findings: list[dict[str, Any]]) -> None:
    if not _nonempty_text(candidate.get("intent")):
        findings.append(_finding("candidate-missing-intent", "error", "Candidate must state its design intent.", candidate_id))

    requirements = _string_set(candidate.get("requirementsCovered"))
    if not requirements:
        findings.append(_finding("candidate-missing-requirements", "error", "Candidate must list requirementsCovered.", candidate_id))

    surfaces = {
        surface
        for raw in candidate.get("selectedSurfaces", [])
        for surface in (_canonical_surface(raw),)
        if surface is not None
    }
    if not surfaces:
        findings.append(_finding("candidate-missing-surfaces", "error", "Candidate must select at least one known runtime surface.", candidate_id))

    for raw in candidate.get("selectedSurfaces", []):
        if _canonical_surface(raw) is None:
            findings.append(_finding("unknown-surface", "error", f"Unknown selected surface '{raw}'.", candidate_id))

    edges = candidate.get("capabilityGraph")
    if not isinstance(edges, list) or not edges:
        findings.append(_finding("capability-graph-missing", "error", "Candidate must include a non-empty capabilityGraph.", candidate_id))
        edges = []

    edge_requirements: set[str] = set()
    edge_surfaces: set[str] = set()
    for edge_idx, edge in enumerate(edges):
        if not isinstance(edge, dict):
            findings.append(_finding("capability-edge-invalid", "error", f"capabilityGraph[{edge_idx}] must be an object.", candidate_id))
            continue
        for field in REQUIRED_EDGE_FIELDS:
            if not _nonempty_text(edge.get(field)):
                findings.append(_finding(
                    "capability-edge-missing-field",
                    "error",
                    f"capabilityGraph[{edge_idx}] is missing required field '{field}'.",
                    candidate_id,
                ))
        req = edge.get("requirement")
        if _nonempty_text(req):
            edge_requirements.add(str(req))
        surface = _canonical_surface(edge.get("surface"))
        if surface is None:
            findings.append(_finding("capability-edge-unknown-surface", "error", f"capabilityGraph[{edge_idx}] has unknown surface '{edge.get('surface')}'.", candidate_id))
        else:
            edge_surfaces.add(surface)
            if surface not in surfaces and surface != "not-feasible":
                findings.append(_finding(
                    "capability-edge-surface-not-selected",
                    "error",
                    f"capabilityGraph[{edge_idx}] uses surface '{surface}' that is not in selectedSurfaces.",
                    candidate_id,
                ))
        _check_edge_pattern(edge, surface, edge_idx, candidate_id, findings)

    for requirement in sorted(requirements - edge_requirements):
        findings.append(_finding(
            "requirement-without-capability-edge",
            "error",
            f"Requirement '{requirement}' is listed but has no capabilityGraph edge.",
            candidate_id,
        ))

    for surface in sorted(surfaces - edge_surfaces):
        findings.append(_finding(
            "selected-surface-without-capability-edge",
            "error",
            f"Selected surface '{surface}' has no capabilityGraph edge proving why it is needed.",
            candidate_id,
        ))

    _check_scores(candidate.get("scores"), candidate_id, findings)
    _check_source_surface(candidate, surfaces, candidate_id, findings)


def _check_edge_pattern(edge: dict[str, Any], surface: str | None, edge_idx: int, candidate_id: str, findings: list[dict[str, Any]]) -> None:
    text = _flatten_text(edge).lower()
    if surface == "middleware":
        if any(term in text for term in ("after_tool", "post_tool", "pre_tool", "after turn", "after_turn", "during tool")):
            findings.append(_finding(
                "middleware-invalid-candidate-mechanism",
                "error",
                f"capabilityGraph[{edge_idx}] uses unsupported middleware timing.",
                candidate_id,
            ))
        if any(term in text for term in ("phase transition", "advance phase", "phase_complete", "phase complete")):
            findings.append(_finding(
                "middleware-as-phase-orchestrator",
                "error",
                f"capabilityGraph[{edge_idx}] uses middleware as a phase orchestrator.",
                candidate_id,
            ))
    if surface == "subagent" and any(term in text for term in ("write file", "edit file", "create file", "patch file")):
        findings.append(_finding(
            "subagent-assigned-file-writing",
            "error",
            f"capabilityGraph[{edge_idx}] assigns file-writing ownership to a subagent.",
            candidate_id,
        ))
    if "text signal" in text or "phase_complete:" in text or "verdict: pass" in text:
        findings.append(_finding(
            "text-signal-control-flow",
            "warning",
            f"capabilityGraph[{edge_idx}] appears to use LLM text as a control-flow signal.",
            candidate_id,
        ))


def _check_scores(scores: Any, candidate_id: str, findings: list[dict[str, Any]]) -> None:
    if not isinstance(scores, dict):
        findings.append(_finding("scores-missing", "error", "Candidate must include scores.", candidate_id))
        return
    for field in REQUIRED_SCORE_FIELDS:
        value = scores.get(field)
        if not isinstance(value, int) or value < 0 or value > 10:
            findings.append(_finding(
                "score-invalid",
                "error",
                f"Score '{field}' must be an integer from 0 to 10.",
                candidate_id,
            ))
    if (
        isinstance(scores.get("effectiveness"), int)
        and isinstance(scores.get("groundedness"), int)
        and scores["effectiveness"] >= 9
        and scores["groundedness"] < 7
    ):
        findings.append(_finding(
            "high-effectiveness-low-grounding",
            "warning",
            "High effectiveness with weak groundedness is usually a plausible-but-unproven workflow.",
            candidate_id,
        ))


def _check_source_surface(candidate: dict[str, Any], surfaces: set[str], candidate_id: str, findings: list[dict[str, Any]]) -> None:
    if "source" not in surfaces:
        return
    text = _flatten_text(candidate).lower()
    if not any(term in text for term in ("lower tier", "tier a", "tier b", "tier c", "cannot satisfy", "ruled out")):
        findings.append(_finding(
            "source-change-without-lower-tier-rejection",
            "error",
            "Source-level candidates must explain why lower-tier surfaces cannot satisfy the requirement.",
            candidate_id,
        ))
    scores = candidate.get("scores", {})
    if isinstance(scores, dict) and (scores.get("cost", 0) >= 8 or scores.get("maintainability", 0) >= 8):
        findings.append(_finding(
            "source-change-overconfident-cost",
            "warning",
            "Source-level candidates should not score cost or maintainability as easy without strong justification.",
            candidate_id,
        ))


def _weighted_score(scores: Any) -> float | None:
    if not isinstance(scores, dict):
        return None
    values = []
    for field in REQUIRED_SCORE_FIELDS:
        value = scores.get(field)
        if not isinstance(value, int):
            return None
        values.append(value)
    effectiveness, groundedness, cost, maintainability, observability, convergence = values
    return (
        effectiveness * 1.5
        + groundedness * 2.0
        + cost
        + maintainability
        + observability * 0.8
        + convergence * 1.2
    ) / 7.5


def _string_set(value: Any) -> set[str]:
    if not isinstance(value, list):
        return set()
    return {str(item) for item in value if _nonempty_text(item)}


def _nonempty_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _flatten_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return " ".join(_flatten_text(v) for v in value.values())
    if isinstance(value, list):
        return " ".join(_flatten_text(v) for v in value)
    return str(value)


def _canonical_surface(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip().lower().replace("_", "-")
    aliases = {
        "custom-tool": "tool",
        "tools": "tool",
        "tooling": "tool",
        "skills": "skill",
        "mcp-server": "mcp",
        "mcp-servers": "mcp",
        "mistral-connector": "connector",
        "mistral-connectors": "connector",
        "connectors": "connector",
        "agents": "agent-profile",
        "profiles": "agent-profile",
        "agent": "agent-profile",
        "subagents": "subagent",
        "task": "subagent",
        "task-tool": "subagent",
        "hooks": "hook",
        "post-agent-turn": "hook",
        "post_agent_turn": "hook",
        "programmatic-mode": "programmatic",
        "streaming-output": "programmatic",
        "json-output": "programmatic",
        "scratch": "scratchpad",
        "agents.md": "agents-md",
        ".vibe/agents.md": "agents-md",
        "ask-user-question": "user-question",
        "ask-user-question-tool": "user-question",
        "ask_user_question": "user-question",
        "exit-plan-mode": "plan-mode",
        "exit_plan_mode": "plan-mode",
        "events": "event",
        "sessions": "session",
        "source-changes": "source",
    }
    value = aliases.get(value, value)
    known = {
        "config",
        "skill",
        "tool",
        "mcp",
        "connector",
        "middleware",
        "agent-profile",
        "subagent",
        "hook",
        "programmatic",
        "scratchpad",
        "agents-md",
        "todo",
        "user-question",
        "plan-mode",
        "event",
        "session",
        "state",
        "source",
        "backend-boundary",
        "not-feasible",
    }
    return value if value in known else None


def _finding(rule: str, severity: str, message: str, candidate: str | None = None) -> dict[str, str]:
    finding = {"rule": rule, "severity": severity, "message": message}
    if candidate:
        finding["candidate"] = candidate
    return finding


def _result(findings: list[dict[str, Any]], winner: Any, candidate_count: int) -> dict[str, Any]:
    errors = [finding for finding in findings if finding["severity"] == "error"]
    return {
        "pass": len(errors) == 0,
        "findings": findings,
        "count": len(findings),
        "candidate_count": candidate_count,
        "winner": winner,
    }


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: strategy-fit-linter.py <DESIGN_CANDIDATES.json>")
        sys.exit(2)

    try:
        result = lint_strategy_candidates(sys.argv[1])
    except Exception as exc:
        result = {
            "pass": False,
            "findings": [{"rule": "strategy-fit-parse-error", "severity": "error", "message": str(exc)}],
            "count": 1,
            "candidate_count": 0,
            "winner": None,
        }
    print(json.dumps(result, indent=2))
    sys.exit(0 if result["pass"] else 1)
