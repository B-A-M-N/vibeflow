#!/usr/bin/env python3
"""VibeFlow Failure Classifier - classifies why validation failed."""

import json
import sys

FAILURE_TYPES = {
    "bad workflow topology": ["no-phase-without-exit", "no-unreachable-phase"],
    "missing Vibe extension point": ["no-middleware-missing-interface"],
    "invalid middleware hook": ["no-middleware-missing-interface"],
    "agent prompt too vague": ["no-final-without-evidence"],
    "tool unavailable": ["no-unavailable-tool"],
    "state not persisted": ["state-missing-persist"],
    "loop has no convergence": ["no-retry-without-max"],
    "test command missing": ["no-tool-without-validation"],
    "sandbox unsafe": ["no-sandbox-unsafe"],
    "target unclear": ["no-relevance-gate"],
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
        for failure_type, rules in FAILURE_TYPES.items():
            if rule_id in rules:
                failures.append({
                    "type": failure_type,
                    "rule": rule_id,
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
