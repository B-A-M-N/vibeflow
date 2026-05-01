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
state:
  path: "{state}"
  persist: false
sandbox:
  isolation: tempdir
approval_gates:
  - id: apply-complete
    type: automated
    requires: schema validation passes
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
failure_policy:
  classification:
    - plugin_tooling
    - generated_workflow
    - user_spec
    - environment
    - external_dependency
  onFailure: Classify the failure domain before redesigning the workflow.
commands:
  lint: "python3 scripts/workflow-linter.py .vibe-workflow/workflow.yaml"
  dryRun: "python3 scripts/dry-run-simulator.py .vibe-workflow/workflow.yaml validation {evidence}"
  validate: "python3 scripts/validation-runner.py .vibe-workflow/workflow.yaml {evidence}"
validation:
  serial: true
  evidenceRequired: true
  mutatesWorkflow: false
"""


LEGACY = """\
name: Legacy Smoke
goal: Verify alias compatibility warnings.
middleware:
  - no_user_deferral_guard
state:
  path: "{state}"
  persist: false
sandbox:
  isolation: tempdir
approval_gates:
  - id: apply-complete
    type: automated
    requires: schema validation passes
phases:
  - name: STOP
    entry_criteria: Terminal phase reached.
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
failure_policy:
  classification:
    - plugin_tooling
    - generated_workflow
    - user_spec
    - environment
    - external_dependency
  onFailure: Classify the failure domain before redesigning the workflow.
commands:
  lint: "python3 scripts/workflow-linter.py .vibe-workflow/workflow.yaml"
  dryRun: "python3 scripts/dry-run-simulator.py .vibe-workflow/workflow.yaml validation {evidence}"
  validate: "python3 scripts/validation-runner.py .vibe-workflow/workflow.yaml {evidence}"
validation:
  serial: true
  evidenceRequired: true
  mutatesWorkflow: false
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


BROKEN_YAML = """\
name: Broken Parser
phases:
  - id: intake
    entry: starts
    exit: stops
    retryLimit: [not: valid
"""


INVALID_MIDDLEWARE = CANONICAL.replace(
    "middleware:\n  - no_user_deferral_guard",
    "middleware:\n  - name: no_user_deferral_guard\n    hooks: [pre_tool]",
)


UNDECLARED_TOOL = CANONICAL.replace(
    "tools: [\"read_file\"]",
    "tools: [\"read_file\", \"bash\"]",
)


SELECTED_TOOL_CONTRACT = {
    "name": "Tooling Smoke",
    "phase": "applied",
    "intent": {
        "goal": "Verify runnable workflow tooling.",
        "scope": {"in_scope": ["tooling"], "out_of_scope": []},
        "success_criteria": ["dry run passes"],
    },
    "artifacts": {
        "vision": "VISION.md",
        "plan": "PLAN.md",
        "contract": "WORKFLOW_CONTRACT.json",
    },
    "design": {
        "approved": True,
        "runtime_surfaces": ["tool"],
        "requirements": [
            {
                "id": "read_inputs",
                "description": "Read workflow inputs deterministically.",
                "status": "runtime",
                "selected_surfaces": ["tool"],
                "success_proof": "dry run calls read_file",
            }
        ],
        "surfaceDecisions": [
            {
                "surface": "tool",
                "status": "selected",
                "reason": "The workflow needs deterministic file reads.",
                "requiredCapabilities": ["read workflow inputs"],
                "contracts": ["tooling.requiredTools declares read_file"],
                "implementationEvidence": ["tooling.requiredTools.read_file"],
            },
            {
                "surface": "middleware",
                "status": "rejected",
                "reason": "No behavior must run before every LLM turn.",
                "riskIfWrong": "Global guardrails would be missing.",
                "reconsiderIf": "Cross-turn injection becomes required.",
            },
        ],
    },
}


SELECTED_TOOL_WITHOUT_EVIDENCE = {
    **SELECTED_TOOL_CONTRACT,
    "design": {
        **SELECTED_TOOL_CONTRACT["design"],
        "surfaceDecisions": [
            {
                "surface": "tool",
                "status": "selected",
                "reason": "The workflow needs deterministic file reads.",
                "requiredCapabilities": ["read workflow inputs"],
                "contracts": ["tooling.requiredTools declares read_file"],
            }
        ],
    },
}


def run_script(*args, cwd=ROOT):
    return subprocess.run([sys.executable, *map(str, args)], cwd=cwd, capture_output=True, text=True)


class WorkflowToolingTests(unittest.TestCase):
    def test_linter_accepts_retry_limit_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "workflow.yaml"
            evidence = Path(tmp) / "latest.json"
            state = Path(tmp) / "state.json"
            path.write_text(CANONICAL.format(evidence=evidence, state=state))
            proc = run_script(ROOT / "scripts/workflow-linter.py", path)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

    def test_legacy_aliases_warn_but_parse(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "workflow.yaml"
            evidence = Path(tmp) / "latest.json"
            state = Path(tmp) / "state.json"
            path.write_text(LEGACY.format(evidence=evidence, state=state))
            proc = run_script(ROOT / "scripts/workflow-linter.py", path)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            data = json.loads(proc.stdout)
            self.assertIn("retry_budget normalized", "\n".join(data["warnings"]))
            self.assertIn("entry_criteria normalized", "\n".join(data["warnings"]))

    def test_dry_run_emits_declared_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "workflow.yaml"
            evidence = Path(tmp) / "latest.json"
            state = Path(tmp) / "state.json"
            path.write_text(CANONICAL.format(evidence=evidence, state=state))
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
            self.assertIn("failure-classifier", [check["name"] for check in data["checks_run"]])
            self.assertIn("state-invariant-checker", [check["name"] for check in data["checks_run"]])
            self.assertIn("drift-detector", [check["name"] for check in data["checks_run"]])
            self.assertEqual(data["verdict"], "NEEDS_REWORK")

    def test_validation_runner_does_not_use_stale_evidence_after_dry_run_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "workflow.yaml"
            evidence = Path(tmp) / "latest.json"
            report_dir = Path(tmp) / "reports"
            path.write_text(BROKEN_YAML)
            evidence.write_text(json.dumps({"workflow_id": "stale", "verdict": "READY"}))

            proc = run_script(ROOT / "scripts/validation-runner.py", path, evidence, report_dir)

            self.assertNotEqual(proc.returncode, 0)
            data = json.loads(evidence.read_text())
            convergence = [check for check in data["checks_run"] if check["name"] == "convergence-scorer"]
            self.assertEqual(len(convergence), 1)
            self.assertTrue(convergence[0]["skipped"])
            self.assertEqual(data["workflow_id"], "workflow")
            self.assertEqual(data["verdict"], "NEEDS_REWORK")

    def test_linter_rejects_invalid_middleware_hook(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "workflow.yaml"
            evidence = Path(tmp) / "latest.json"
            state = Path(tmp) / "state.json"
            path.write_text(INVALID_MIDDLEWARE.format(evidence=evidence, state=state))
            proc = run_script(ROOT / "scripts/workflow-linter.py", path)
            self.assertNotEqual(proc.returncode, 0)
            data = json.loads(proc.stdout)
            self.assertIn("middleware-invalid-hook", {v["rule"] for v in data["violations"]})

    def test_dry_run_fails_for_undeclared_phase_tool(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "workflow.yaml"
            evidence = Path(tmp) / "latest.json"
            state = Path(tmp) / "state.json"
            path.write_text(UNDECLARED_TOOL.format(evidence=evidence, state=state))
            proc = run_script(ROOT / "scripts/dry-run-simulator.py", path)
            self.assertNotEqual(proc.returncode, 0)
            data = json.loads(proc.stdout)
            self.assertEqual(data["verdict"], "NEEDS_REWORK")
            self.assertFalse(data["gates_passed"])

    def test_design_contract_accepts_selected_tool_and_rejected_middleware(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "workflow.yaml"
            evidence = Path(tmp) / "latest.json"
            state = Path(tmp) / "state.json"
            contract = Path(tmp) / "WORKFLOW_CONTRACT.json"
            path.write_text(CANONICAL.format(evidence=evidence, state=state))
            contract.write_text(json.dumps(SELECTED_TOOL_CONTRACT))

            proc = run_script(ROOT / "scripts/design-contract-linter.py", path, contract)

            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

    def test_design_contract_rejects_selected_surface_without_apply_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "workflow.yaml"
            evidence = Path(tmp) / "latest.json"
            state = Path(tmp) / "state.json"
            contract = Path(tmp) / "WORKFLOW_CONTRACT.json"
            path.write_text(CANONICAL.format(evidence=evidence, state=state))
            contract.write_text(json.dumps(SELECTED_TOOL_WITHOUT_EVIDENCE))

            proc = run_script(ROOT / "scripts/design-contract-linter.py", path, contract)

            self.assertNotEqual(proc.returncode, 0)
            data = json.loads(proc.stdout)
            self.assertIn(
                "selected-surface-missing-implementation-evidence",
                {v["rule"] for v in data["violations"]},
            )

    def test_validation_runner_includes_design_contract_linter(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "workflow.yaml"
            evidence = Path(tmp) / "latest.json"
            state = Path(tmp) / "state.json"
            report_dir = Path(tmp) / "reports"
            contract = Path(tmp) / "WORKFLOW_CONTRACT.json"
            path.write_text(CANONICAL.format(evidence=evidence, state=state))
            contract.write_text(json.dumps(SELECTED_TOOL_CONTRACT))

            proc = run_script(ROOT / "scripts/validation-runner.py", path, evidence, report_dir)

            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            data = json.loads(evidence.read_text())
            self.assertIn("design-contract-linter", [check["name"] for check in data["checks_run"]])
            self.assertIn("pattern-fit-linter", [check["name"] for check in data["checks_run"]])

    def test_validation_runner_resolves_declared_paths_relative_to_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "workflow-project"
            project.mkdir()
            path = project / "workflow.yaml"
            state = project / "state.json"
            report_dir = project / ".vibe-workflow/reports"
            contract = project / "WORKFLOW_CONTRACT.json"
            manifest = CANONICAL.format(
                evidence=".vibe-workflow/evidence/latest.json",
                state="state.json",
            )
            path.write_text(manifest)
            state.write_text(json.dumps({
                "currentPhase": "intake",
                "retryCounts": {"intake": 0},
                "evidence": [],
                "gateDecisions": [],
            }))
            contract.write_text(json.dumps(SELECTED_TOOL_CONTRACT))

            proc = run_script(ROOT / "scripts/validation-runner.py", path, cwd=ROOT)

            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            evidence = project / ".vibe-workflow/evidence/latest.json"
            self.assertTrue(evidence.exists())
            data = json.loads(evidence.read_text())
            self.assertEqual(data["evidence_path"], str(evidence.resolve()))
            self.assertTrue((report_dir / "lint-results.json").exists())

    def test_update_skill_and_registry_are_discoverable(self):
        skill = ROOT / "skills/vibe-workflow-update/SKILL.md"
        command = ROOT / "commands/vibe-workflow-update.md"
        self.assertTrue(skill.exists())
        self.assertTrue(command.exists())
        skill_text = skill.read_text()
        self.assertIn("name: vibe-workflow-update", skill_text)
        self.assertIn("allowed-tools:", skill_text)
        self.assertIn("user-invocable: true", skill_text)

        proc = run_script(ROOT / "scripts/capability-registry.py")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        registry = json.loads(proc.stdout)
        self.assertIn("vibe-workflow-update", registry["skills"])
        for tool in ["ask_user_question", "exit_plan_mode", "todo", "task", "webfetch", "websearch"]:
            self.assertIn(tool, registry["tools"])

    def test_pattern_fit_rejects_post_tool_middleware(self):
        with tempfile.TemporaryDirectory() as tmp:
            contract = Path(tmp) / "WORKFLOW_CONTRACT.json"
            bad_contract = {
                **SELECTED_TOOL_CONTRACT,
                "design": {
                    **SELECTED_TOOL_CONTRACT["design"],
                    "surfaceDecisions": [
                        {
                            "surface": "middleware",
                            "status": "selected",
                            "reason": "Run after_tool to inspect every tool result.",
                            "requiredCapabilities": ["post tool inspection"],
                            "contracts": ["after_tool hook"],
                            "implementationEvidence": ["middleware.py"],
                        }
                    ],
                },
            }
            contract.write_text(json.dumps(bad_contract))

            proc = run_script(ROOT / "scripts/pattern-fit-linter.py", contract)

            self.assertNotEqual(proc.returncode, 0)
            data = json.loads(proc.stdout)
            self.assertIn("middleware-invalid-hook", {f["rule"] for f in data["findings"]})

    def test_pattern_fit_warns_skill_tool_allowed_tools_unchecked(self):
        with tempfile.TemporaryDirectory() as tmp:
            contract = Path(tmp) / "WORKFLOW_CONTRACT.json"
            contract_data = {
                **SELECTED_TOOL_CONTRACT,
                "design": {
                    **SELECTED_TOOL_CONTRACT["design"],
                    "surfaceDecisions": [
                        {
                            "surface": "skill",
                            "status": "selected",
                            "reason": "Guide the user through repo review.",
                            "requiredCapabilities": ["guided review"],
                            "contracts": ["SKILL.md"],
                            "implementationEvidence": ["skills/review/SKILL.md"],
                        },
                        SELECTED_TOOL_CONTRACT["design"]["surfaceDecisions"][0],
                    ],
                },
            }
            contract.write_text(json.dumps(contract_data))

            proc = run_script(ROOT / "scripts/pattern-fit-linter.py", contract)

            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            data = json.loads(proc.stdout)
            self.assertIn("skill-tool-allowed-tools-unchecked", {f["rule"] for f in data["findings"]})

    def test_pattern_fit_rejects_invalid_hook_boundary(self):
        with tempfile.TemporaryDirectory() as tmp:
            contract = Path(tmp) / "WORKFLOW_CONTRACT.json"
            contract_data = {
                **SELECTED_TOOL_CONTRACT,
                "design": {
                    **SELECTED_TOOL_CONTRACT["design"],
                    "surfaceDecisions": [
                        {
                            "surface": "hook",
                            "status": "selected",
                            "reason": "Use a pre-turn hook to block bad output.",
                            "requiredCapabilities": ["pre-turn validation"],
                            "contracts": ["pre-turn hook"],
                            "implementationEvidence": ["hook.sh"],
                        }
                    ],
                },
            }
            contract.write_text(json.dumps(contract_data))

            proc = run_script(ROOT / "scripts/pattern-fit-linter.py", contract)

            self.assertNotEqual(proc.returncode, 0)
            data = json.loads(proc.stdout)
            rules = {f["rule"] for f in data["findings"]}
            self.assertIn("hook-type-unverified", rules)
            self.assertIn("hook-invalid-boundary", rules)

    def test_pattern_fit_rejects_subagent_file_writing(self):
        with tempfile.TemporaryDirectory() as tmp:
            contract = Path(tmp) / "WORKFLOW_CONTRACT.json"
            contract_data = {
                **SELECTED_TOOL_CONTRACT,
                "design": {
                    **SELECTED_TOOL_CONTRACT["design"],
                    "surfaceDecisions": [
                        {
                            "surface": "subagent",
                            "status": "selected",
                            "reason": "A validator subagent will edit files and write reports.",
                            "requiredCapabilities": ["delegated artifact generation"],
                            "contracts": ["task tool"],
                            "implementationEvidence": ["agents/validator.md"],
                        }
                    ],
                },
            }
            contract.write_text(json.dumps(contract_data))

            proc = run_script(ROOT / "scripts/pattern-fit-linter.py", contract)

            self.assertNotEqual(proc.returncode, 0)
            data = json.loads(proc.stdout)
            self.assertIn("subagent-assigned-file-writing", {f["rule"] for f in data["findings"]})


    # ── pre-apply-guard tests ────────────────────────────────────────────────

    def _write_contract(self, tmp: str, surface_decisions: list) -> Path:
        contract = Path(tmp) / "WORKFLOW_CONTRACT.json"
        contract.write_text(json.dumps({
            "phase": "plan-approved",
            "design": {
                "surfaceDecisions": surface_decisions,
            },
        }))
        return contract

    def _write_proposed(self, tmp: str, changes: list) -> Path:
        pf = Path(tmp) / "proposed_changes.json"
        pf.write_text(json.dumps({"proposed_changes": changes}))
        return pf

    def test_guard_passes_when_all_selected_surfaces_covered(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._write_contract(tmp, [
                {"surface": "skill", "status": "selected",
                 "requiredCapabilities": ["guidance"], "contracts": [], "implementationEvidence": "x", "validationEvidence": "x"},
            ])
            pf = self._write_proposed(tmp, [
                {"file": "skills/my-skill/SKILL.md", "operation": "create", "surface": "skill", "implements": "guidance"},
            ])
            proc = run_script(ROOT / "scripts/pre-apply-guard.py", pf, cwd=Path(tmp))
            self.assertEqual(proc.returncode, 0, proc.stdout)
            data = json.loads(proc.stdout)
            self.assertTrue(data["pass"])
            self.assertEqual(data["violations"], [])

    def test_guard_blocks_rejected_surface(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._write_contract(tmp, [
                {"surface": "skill", "status": "selected",
                 "requiredCapabilities": [], "contracts": [], "implementationEvidence": "x", "validationEvidence": "x"},
                {"surface": "middleware", "status": "rejected", "rationale": "not needed"},
            ])
            pf = self._write_proposed(tmp, [
                {"file": "skills/my-skill/SKILL.md", "operation": "create", "surface": "skill", "implements": "guidance"},
                {"file": "middleware/my_mw.py", "operation": "create", "surface": "middleware", "implements": "blocked"},
            ])
            proc = run_script(ROOT / "scripts/pre-apply-guard.py", pf, cwd=Path(tmp))
            self.assertNotEqual(proc.returncode, 0)
            data = json.loads(proc.stdout)
            self.assertFalse(data["pass"])
            self.assertIn("rejected-surface", {v["rule"] for v in data["violations"]})

    def test_guard_blocks_unauthorized_surface(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._write_contract(tmp, [
                {"surface": "skill", "status": "selected",
                 "requiredCapabilities": [], "contracts": [], "implementationEvidence": "x", "validationEvidence": "x"},
            ])
            pf = self._write_proposed(tmp, [
                {"file": "skills/my-skill/SKILL.md", "operation": "create", "surface": "skill", "implements": "guidance"},
                {"file": "tools/extra_tool.py", "operation": "create", "surface": "custom-tool", "implements": "unauthorized"},
            ])
            proc = run_script(ROOT / "scripts/pre-apply-guard.py", pf, cwd=Path(tmp))
            self.assertNotEqual(proc.returncode, 0)
            data = json.loads(proc.stdout)
            self.assertIn("unauthorized-surface", {v["rule"] for v in data["violations"]})

    def test_guard_blocks_missing_selected_surface(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._write_contract(tmp, [
                {"surface": "skill", "status": "selected",
                 "requiredCapabilities": [], "contracts": [], "implementationEvidence": "x", "validationEvidence": "x"},
                {"surface": "custom-tool", "status": "selected",
                 "requiredCapabilities": [], "contracts": [], "implementationEvidence": "x", "validationEvidence": "x"},
            ])
            pf = self._write_proposed(tmp, [
                {"file": "skills/my-skill/SKILL.md", "operation": "create", "surface": "skill", "implements": "guidance"},
                # custom-tool is selected but not proposed — guard must flag it
            ])
            proc = run_script(ROOT / "scripts/pre-apply-guard.py", pf, cwd=Path(tmp))
            self.assertNotEqual(proc.returncode, 0)
            data = json.loads(proc.stdout)
            self.assertIn("missing-selected-surface", {v["rule"] for v in data["violations"]})
            self.assertIn("custom-tool", data["uncovered_surfaces"])

    def test_guard_passes_without_contract_with_warning(self):
        with tempfile.TemporaryDirectory() as tmp:
            pf = self._write_proposed(tmp, [
                {"file": "skills/my-skill/SKILL.md", "operation": "create", "surface": "skill", "implements": "guidance"},
            ])
            proc = run_script(ROOT / "scripts/pre-apply-guard.py", pf, cwd=Path(tmp))
            self.assertEqual(proc.returncode, 0, proc.stdout)
            data = json.loads(proc.stdout)
            self.assertTrue(data["pass"])
            self.assertTrue(any("No contract found" in w for w in data["warnings"]))

    def test_guard_follows_contract_source_pointer(self):
        with tempfile.TemporaryDirectory() as tmp:
            rc = Path(tmp) / "REALIZATION_CONTRACT.json"
            rc.write_text(json.dumps({
                "mode": "realize_existing_concept",
                "required_runtime_surfaces": ["skill"],
            }))
            wf = Path(tmp) / "WORKFLOW_CONTRACT.json"
            wf.write_text(json.dumps({
                "phase": "realize-approved",
                "contract_source": "REALIZATION_CONTRACT.json",
            }))
            pf = self._write_proposed(tmp, [
                {"file": "skills/x/SKILL.md", "operation": "create", "surface": "skill", "implements": "realized skill"},
            ])
            proc = run_script(ROOT / "scripts/pre-apply-guard.py", pf, cwd=Path(tmp))
            self.assertEqual(proc.returncode, 0, proc.stdout)
            data = json.loads(proc.stdout)
            self.assertTrue(data["pass"])
            self.assertIn("REALIZATION_CONTRACT.json", data["contract_path"])

    def test_guard_accepts_surface_aliases(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._write_contract(tmp, [
                {"surface": "tools", "status": "selected",   # alias for custom-tool
                 "requiredCapabilities": [], "contracts": [], "implementationEvidence": "x", "validationEvidence": "x"},
            ])
            pf = self._write_proposed(tmp, [
                {"file": "tools/my_tool.py", "operation": "create", "surface": "basetool", "implements": "api call"},
            ])
            proc = run_script(ROOT / "scripts/pre-apply-guard.py", pf, cwd=Path(tmp))
            self.assertEqual(proc.returncode, 0, proc.stdout)

    def test_guard_exits_2_on_missing_proposed_file(self):
        proc = run_script(ROOT / "scripts/pre-apply-guard.py", Path("/nonexistent/proposed_changes.json"))
        self.assertEqual(proc.returncode, 2)

    def test_guard_retry_guidance_present_on_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._write_contract(tmp, [
                {"surface": "skill", "status": "selected",
                 "requiredCapabilities": [], "contracts": [], "implementationEvidence": "x", "validationEvidence": "x"},
            ])
            pf = self._write_proposed(tmp, [
                {"file": "tools/bad.py", "operation": "create", "surface": "custom-tool", "implements": "oops"},
            ])
            proc = run_script(ROOT / "scripts/pre-apply-guard.py", pf, cwd=Path(tmp))
            self.assertNotEqual(proc.returncode, 0)
            data = json.loads(proc.stdout)
            self.assertIn("retry_guidance", data)
            self.assertIn("proposed_changes.json", data["retry_guidance"])


if __name__ == "__main__":
    unittest.main()
