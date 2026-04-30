#!/usr/bin/env python3
"""VibeFlow Failure Classifier - classifies why validation failed."""

import json
import sys

FAILURE_TYPES = {
    "bad workflow topology": [
        "missing-manifest-section",
        "phase-missing-id",
        "phase-missing-entry",
        "no-phase-without-exit",
        "duplicate-phase-id",
        "no-unreachable-phase",
    ],
    "missing Vibe extension point": ["middleware-unknown", "tool-unavailable"],
    "invalid middleware hook": ["middleware-invalid-hook", "middleware-missing-hook", "invalid-middleware-contract"],
    "agent prompt too vague": ["no-final-without-evidence"],
    "tool unavailable": [
        "missing-tooling-contract",
        "tooling-contract-missing-field",
        "tooling-contract-no-required-tools",
        "tooling-contract-invalid-tool",
        "phase-tool-not-declared",
        "tooling-contract-missing-failure-semantics",
        "tool-unavailable",
    ],
    "state not persisted": ["missing-manifest-section"],
    "loop has no convergence": ["no-retry-without-max", "invalid-retry-limit"],
    "test command missing": ["missing-commands-contract", "commands-contract-missing-field", "missing-validation-contract", "invalid-validation-contract"],
    "sandbox unsafe": ["sandbox-safety"],
    "target unclear": ["relevance"],
}

REWORK_TEMPLATES = {
    "bad workflow topology": "Re-work manifest: add missing phases, fix exit criteria",
    "missing Vibe extension point": "Check source-map.json and update middleware interfaces",
    "invalid middleware hook": "Verify middleware hooks match real Vibe interfaces",
    "agent prompt too vague": "Add evidence requirements to workflow manifest",
    "tool unavailable": "Update tool list or install missing dependencies",
    "state not persisted": "Set state.persist: true in manifest",
    "loop has no convergence": "Add retryLimit to all phases",
    "test command missing": "Add validation handling for all tool calls",
    "sandbox unsafe": "Set sandbox.isolation to container or tempdir",
    "target unclear": "Clarify workflow goal and add relevance gate",
}

def classify_failure(lint_results):
    failures = []

    for violation in lint_results.get("violations", []):
        rule_id = violation.get("rule", "")
        if rule_id in {"parse-error", "import-error"}:
            failures.append({
                "type": "validation harness bug",
                "rule": rule_id,
                "failure_domain": "plugin_tooling",
                "is_design_flaw": False,
                "is_validation_harness_bug": True,
                "safe_next_action": "fix harness before redesign"
            })
            continue
        for failure_type, rules in FAILURE_TYPES.items():
            if rule_id in rules:
                failures.append({
                    "type": failure_type,
                    "rule": rule_id,
                    "failure_domain": "generated_workflow",
                    "is_design_flaw": failure_type in {"bad workflow topology", "missing Vibe extension point"},
                    "is_validation_harness_bug": False,
                    "safe_next_action": REWORK_TEMPLATES.get(failure_type, "Review workflow manifest"),
                    "rework": REWORK_TEMPLATES.get(failure_type, "Review workflow manifest")
                })

    return failures

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: failure-classifier.py <lint-results.json>")
        sys.exit(1)

    with open(sys.argv[1]) as f:
        lint_data = json.load(f)

    failures = classify_failure(lint_data)
    print(json.dumps(failures, indent=2))
