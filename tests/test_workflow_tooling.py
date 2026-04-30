import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


CANONICAL = """\
name: Tooling Smoke
goal: Verify runnable workflow tooling.
middleware:
  - no_user_deferral_guard
phases:
  - id: intake
    entry: User request exists.
    exit: Intent captured.
    retryLimit: 0
    tools: ["read_file"]
tooling:
  requiredTools:
    - name: read_file
      purpose: Read workflow inputs.
      required: true
  entrypoint: "python3 scripts/dry-run-simulator.py .vibe-workflow/workflow.yaml"
  inputs:
    - name: workflow_manifest
      source: ".vibe-workflow/workflow.yaml"
      type: yaml
  outputs:
    - name: evidence
      path: ".vibe-workflow/evidence/latest.json"
      type: json
  evidenceOutput: "{evidence}"
  failureSemantics:
    onSchemaError: Return NEEDS_REWORK and repair schema.
    onToolError: Return NEEDS_REWORK and repair tooling.
    onValidationError: Return FAILED with exact failing gate.
evidence:
  require:
    - latest.json
"""


LEGACY = """\
name: Legacy Smoke
goal: Verify alias compatibility warnings.
middleware:
  - no_user_deferral_guard
phases:
  - name: STOP
    entry: Terminal phase reached.
    exit_criteria: Stop complete.
    retry_budget: 0
    tools: []
tooling:
  requiredTools:
    - name: read_file
      purpose: Compatibility placeholder.
      required: true
  entrypoint: "python3 scripts/dry-run-simulator.py .vibe-workflow/workflow.yaml"
  inputs:
    - name: workflow_manifest
      source: ".vibe-workflow/workflow.yaml"
      type: yaml
  outputs:
    - name: evidence
      path: ".vibe-workflow/evidence/latest.json"
      type: json
  evidenceOutput: "{evidence}"
  failureSemantics:
    onSchemaError: Return NEEDS_REWORK and repair schema.
    onToolError: Return NEEDS_REWORK and repair tooling.
    onValidationError: Return FAILED with exact failing gate.
evidence:
  require:
    - latest.json
"""


BROKEN = """\
name: Broken Smoke
goal: Verify failed validation still writes evidence.
phases:
  - id: broken
    entry: Missing required sections.
    exit: Broken.
    retryLimit: 0
"""


def run_script(*args, cwd=ROOT):
    return subprocess.run([sys.executable, *map(str, args)], cwd=cwd, capture_output=True, text=True)


class WorkflowToolingTests(unittest.TestCase):
    def test_linter_accepts_retry_limit_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "workflow.yaml"
            evidence = Path(tmp) / "latest.json"
            path.write_text(CANONICAL.format(evidence=evidence))
            proc = run_script(ROOT / "scripts/workflow-linter.py", path)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

    def test_legacy_aliases_warn_but_parse(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "workflow.yaml"
            evidence = Path(tmp) / "latest.json"
            path.write_text(LEGACY.format(evidence=evidence))
            proc = run_script(ROOT / "scripts/workflow-linter.py", path)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            data = json.loads(proc.stdout)
            self.assertIn("retry_budget normalized", "\n".join(data["warnings"]))

    def test_dry_run_emits_declared_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "workflow.yaml"
            evidence = Path(tmp) / "latest.json"
            path.write_text(CANONICAL.format(evidence=evidence))
            proc = run_script(ROOT / "scripts/dry-run-simulator.py", path)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            self.assertTrue(evidence.exists())

    def test_validation_runner_is_serial_and_writes_failure_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "workflow.yaml"
            evidence = Path(tmp) / "latest.json"
            report_dir = Path(tmp) / "reports"
            path.write_text(BROKEN)
            before = path.read_text()
            proc = run_script(ROOT / "scripts/validation-runner.py", path, evidence, report_dir)
            self.assertNotEqual(proc.returncode, 0)
            self.assertEqual(path.read_text(), before)
            self.assertTrue(evidence.exists())
            data = json.loads(evidence.read_text())
            self.assertTrue(data["validation_started"])
            self.assertIn("workflow-linter", [check["name"] for check in data["checks_run"]])
            self.assertIn("dry-run-simulator", [check["name"] for check in data["checks_run"]])
            self.assertEqual(data["verdict"], "NEEDS_REWORK")


if __name__ == "__main__":
    unittest.main()
