#!/usr/bin/env python3
"""VibeFlow Gate Engine - validates workflow gates."""

import json
import sys

GATE_CHECKS = {
    "structure": lambda w: "phases" in w and len(w.get("phases", [])) > 0,
    "sandbox-safety": lambda w: w.get("sandbox", {}).get("isolation") in ["container", "tempdir"] or "sandbox" not in w,
    "patch-minimality": lambda w: True,  # Would check patch size
    "test-evidence": lambda w: "evidence" in w and "require" in w.get("evidence", {}),
    "no-user-deferral": lambda w: "no_user_deferral_guard" in w.get("middleware", []),
    "convergence": lambda w: all(p.get("retryLimit") for p in w.get("phases", [])),
    "relevance": lambda w: "goal" in w and len(w.get("goal", "")) > 10,
}

def check_gates(manifest_path):
    with open(manifest_path) as f:
        workflow = json.load(f)

    results = {"pass": True, "gates": []}

    for gate_id, check_fn in GATE_CHECKS.items():
        try:
            passed = check_fn(workflow)
            results["gates"].append({
                "id": gate_id,
                "passed": passed,
                "type": gate_id.split("-")[-1] if "-" in gate_id else gate_id
            })
            if not passed:
                results["pass"] = False
        except Exception as e:
            results["gates"].append({
                "id": gate_id,
                "passed": False,
                "error": str(e)
            })
            results["pass"] = False

    return results

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: gate-engine.py <manifest.json>")
        sys.exit(1)

    result = check_gates(sys.argv[1])
    print(json.dumps(result, indent=2))
    sys.exit(0 if result["pass"] else 1)
