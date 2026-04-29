#!/usr/bin/env python3
"""VibeFlow Prompt Contract Tests - verify LLM follows required behavior."""

import json
import sys

CONTRACT_TESTS = [
    {
        "input": "ambiguous task with missing files",
        "expected_behavior": "agent continues, does NOT ask user",
        "check": lambda trace: "ask_user" not in str(trace)
    },
    {
        "input": "failure after 3 retries",
        "expected_behavior": "agent produces failure report with evidence",
        "check": lambda trace: "failure" in str(trace).lower() and "evidence" in str(trace).lower()
    },
    {
        "input": "missing file requested",
        "expected_behavior": "agent attempts discovery, not immediate failure",
        "check": lambda trace: "discover" in str(trace).lower() or "search" in str(trace).lower()
    },
    {
        "input": "task with clear success criteria",
        "expected_behavior": "agent produces evidence report with commands run",
        "check": lambda trace: "evidence" in str(trace).lower() and "commands" in str(trace).lower()
    }
]

def run_contract_tests(workflow_path, simulator_script):
    """Run contract tests against workflow."""
    results = {"pass": True, "tests": []}

    for test in CONTRACT_TESTS:
        test_result = {
            "input": test["input"],
            "expected": test["expected_behavior"],
            "passed": False,
            "details": ""
        }

        # Run simulator with test scenario
        import subprocess
        try:
            proc = subprocess.run(
                ["python3", simulator_script, workflow_path, test["input"]],
                capture_output=True, text=True, timeout=30
            )
            trace = proc.stdout + proc.stderr

            # Check contract
            test_result["passed"] = test["check"](trace)
            if not test_result["passed"]:
                test_result["details"] = f"Contract violated: {test['expected_behavior']}"

        except Exception as e:
            test_result["passed"] = False
            test_result["details"] = str(e)

        results["tests"].append(test_result)
        if not test_result["passed"]:
            results["pass"] = False

    return results

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: prompt-contract-tests.py <manifest.json> <simulator.py>")
        sys.exit(1)

    results = run_contract_tests(sys.argv[1], sys.argv[2])
    print(json.dumps(results, indent=2))
    sys.exit(0 if results["pass"] else 1)
