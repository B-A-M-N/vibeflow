#!/usr/bin/env python3
"""
VibeFlow Evidence Reporter
Generates evidence reports from workflow runs.
"""

import json
import sys
from datetime import datetime
from pathlib import Path

EVIDENCE_TEMPLATE = """# VibeFlow Evidence Report

**Workflow**: {workflow_id}
**Timestamp**: {timestamp}
**Verdict**: {verdict}

## Phase Timeline

{timeline}

## Tools Called

{tools}

## Files

### Read

{files_read}

### Changed

{files_changed}

## Commands Run

{commands}

## Tests

### Passed

{tests_passed}

### Failed

{tests_failed}

## Gates

{gates}

## Retry Count

{retries}

## Recommendations

{recommendations}
"""

def generate_report(evidence_data, output_dir=".vibe-workflow/reports"):
    """Generate evidence report from workflow run data."""
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    report = EVIDENCE_TEMPLATE.format(
        workflow_id=evidence_data.get("workflow_id", "unknown"),
        timestamp=datetime.now().isoformat(),
        verdict=evidence_data.get("verdict", "UNKNOWN"),
        timeline=_format_timeline(evidence_data.get("timeline", [])),
        tools=_format_tools(evidence_data.get("tools_called", {})),
        files_read="\n".join(evidence_data.get("files_read", [])) or "None",
        files_changed="\n".join(evidence_data.get("files_changed", [])) or "None",
        commands=_format_commands(evidence_data.get("commands", [])),
        tests_passed="\n".join(evidence_data.get("tests_passed", [])) or "None",
        tests_failed="\n".join(evidence_data.get("tests_failed", [])) or "None",
        gates=_format_gates(evidence_data.get("gates", [])),
        retries=evidence_data.get("retry_count", 0),
        recommendations="\n".join(evidence_data.get("recommendations", ["None"]))
    )

    output_path = Path(output_dir) / f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    with open(output_path, "w") as f:
        f.write(report)

    return str(output_path)

def _format_timeline(timeline):
    lines = []
    for entry in timeline:
        lines.append(f"- [{entry.get('phase', '?')}] {entry.get('event')}: {entry.get('details', '')}")
    return "\n".join(lines) or "No timeline data"

def _format_tools(tools):
    return "\n".join(f"- {k}: {v} calls" for k, v in tools.items()) or "No tools called"

def _format_commands(commands):
    return "\n".join(f"- `{c.get('cmd')}` → {c.get('status', '?')}" for c in commands) or "No commands"

def _format_gates(gates):
    return "\n".join(f"- {g.get('id')}: {g.get('result')}" for g in gates) or "No gates"

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: evidence-reporter.py <evidence.json> [output_dir]")
        sys.exit(1)

    with open(sys.argv[1]) as f:
        data = json.load(f)

    output_dir = sys.argv[2] if len(sys.argv) > 2 else ".vibe-workflow/reports"
    report_path = generate_report(data, output_dir)
    print(f"Report generated: {report_path}")
