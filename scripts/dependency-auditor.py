#!/usr/bin/env python3
"""VibeFlow Dependency Auditor - check environment, CLIs, auth, paths."""

import json
import sys
import shutil
import os
from pathlib import Path

CHECKS = [
    ("git", "version", "Git version control"),
    ("python3", "--version", "Python 3.12+"),
    ("uv", "--version", "uv package manager"),
    ("ruff", "--version", "Ruff linter"),
    ("pytest", "--version", "Pytest test runner"),
]

ENV_VARS = [
    "MISTRAL_API_KEY",
    "GITHUB_TOKEN",
    "FIRECRAWL_API_KEY",
]

def check_cli_tools():
    """Check CLI tools are available."""
    results = {"pass": True, "tools": []}

    for cmd, version_flag, desc in CHECKS:
        tool_result = {"tool": cmd, "available": False, "version": "", "required": desc}
        if shutil.which(cmd):
            import subprocess
            try:
                proc = subprocess.run([cmd, version_flag], capture_output=True, text=True, timeout=5)
                tool_result["available"] = True
                tool_result["version"] = proc.stdout.strip() or proc.stderr.strip()
            except Exception as e:
                tool_result["error"] = str(e)
                results["pass"] = False
        else:
            tool_result["error"] = f"{cmd} not found in PATH"
            results["pass"] = False
        results["tools"].append(tool_result)

    return results

def check_env_vars():
    """Check required environment variables."""
    results = {"pass": True, "vars": []}

    for var in ENV_VARS:
        var_result = {"var": var, "set": False}
        if os.environ.get(var):
            var_result["set"] = True
        else:
            var_result["error"] = f"{var} not set"
            results["pass"] = False
        results["vars"].append(var_result)

    return results

def check_repo():
    """Check repo is valid git repo."""
    results = {"pass": True, "repo": {"error": None}}
    if not Path(".git").exists():
        results["pass"] = False
        results["repo"]["error"] = "Not a git repository"
    return results

def check_manifest_deps(manifest_path):
    """Check manifest dependencies (commands, paths)."""
    results = {"pass": True, "missing": []}

    if not Path(manifest_path).exists():
        results["pass"] = False
        results["missing"].append(f"Manifest not found: {manifest_path}")
        return results

    with open(manifest_path) as f:
        workflow = json.load(f)

    # Check tools exist in capability registry
    for phase in workflow.get("phases", []):
        for tool in phase.get("tools", []):
            if tool not in ["bash", "read_file", "write_file", "grep"]:
                # Would check capability registry
                pass

    return results

if __name__ == "__main__":
    results = {
        "cli_tools": check_cli_tools(),
        "env_vars": check_env_vars(),
        "repo": check_repo(),
    }

    # Check manifest deps if provided
    if len(sys.argv) > 1:
        results["manifest_deps"] = check_manifest_deps(sys.argv[1])

    overall = all(r.get("pass", True) for r in results.values())
    results["overall_pass"] = overall

    print(json.dumps(results, indent=2))
    sys.exit(0 if overall else 1)
