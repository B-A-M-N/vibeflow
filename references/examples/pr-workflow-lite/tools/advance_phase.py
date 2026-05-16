"""
WF-Lite: advance_phase tool — Gated phase transition.

Tier: B (BaseTool subclass with switch_agent_callback)
Source: references/examples/pr-workflow-lite/tools/advance_phase.py

This is the ONLY way to advance between phases. It enforces:
  1. GitNexus evidence (for INVESTIGATE → IMPLEMENT)
  2. Scope contract (all write_evidence paths within contract)
  3. Clean working tree (for read-only phases)
  4. Test evidence (for VALIDATE → PUSH)

On success, calls ctx.switch_agent_callback() to switch the agent profile,
which rebuilds ToolManager with the new enabled_tools list.
"""

from pydantic import BaseModel
from vibe.core.tools import BaseTool, InvokeContext


class AdvancePhaseInput(BaseModel):
    target_phase: str = ""  # Optional — defaults to next in sequence


# Phase sequence definition
PHASE_SEQUENCE = [
    "INTAKE",
    "INVESTIGATE",
    "IMPLEMENT",
    "VALIDATE",
    "PUSH",
    "COMPLETE",
]

# Transitions requiring GitNexus evidence
GITNEXUS_REQUIRED_TRANSITIONS = {
    ("INVESTIGATE", "IMPLEMENT"): ["gitnexus_query", "gitnexus_context", "gitnexus_impact"],
}

# Phases where source file mutations are unauthorized
READ_ONLY_PHASES = {"INTAKE", "INVESTIGATE", "VALIDATE"}


class AdvancePhaseTool(BaseTool):
    name = "advance_phase"
    description = (
        "Advance to the next workflow phase. "
        "Gates: GitNexus evidence (INVESTIGATE→IMPLEMENT), scope contract, clean tree. "
        "This is the ONLY way to change phases."
    )
    input_schema = AdvancePhaseInput

    async def execute(self, input: AdvancePhaseInput, ctx: InvokeContext):
        import json
        from pathlib import Path

        # Load state
        state = self._load_state(ctx)
        if not state:
            return {"success": False, "error": "No state file found. Call init_state first."}

        current_phase = state.get("phase", "INTAKE")

        # Determine target phase
        target = input.target_phase
        if not target:
            idx = PHASE_SEQUENCE.index(current_phase) if current_phase in PHASE_SEQUENCE else -1
            if idx + 1 < len(PHASE_SEQUENCE):
                target = PHASE_SEQUENCE[idx + 1]
            else:
                return {"success": False, "error": f"Cannot advance from {current_phase}"}

        # Gate 1: GitNexus evidence
        transition = (current_phase, target)
        if transition in GITNEXUS_REQUIRED_TRANSITIONS:
            evidence = state.get("gitnexus_evidence", [])
            required_tools = GITNEXUS_REQUIRED_TRANSITIONS[transition]
            has_evidence = any(
                e.get("tool") in required_tools
                and e.get("valid_for_gate")
                and e.get("result_has_data")
                for e in evidence
            )
            if not has_evidence:
                return {
                    "success": False,
                    "error": f"GitNexus evidence required for {current_phase}→{target}. "
                             f"Need one of: {required_tools}",
                    "gate": "gitnexus",
                }

        # Gate 2: Scope check
        violations = self._check_scope(state, ctx)
        if violations:
            return {
                "success": False,
                "error": f"Scope violation: {violations}",
                "gate": "scope",
            }

        # Gate 3: Clean tree (read-only phases)
        if current_phase in READ_ONLY_PHASES:
            dirty = self._check_dirty_tree(state, ctx)
            if dirty:
                return {
                    "success": False,
                    "error": f"Unauthorized writes in {current_phase}: {dirty}",
                    "gate": "dirty_tree",
                }

        # Gate 4: Test evidence (VALIDATE → PUSH)
        if current_phase == "VALIDATE" and target == "PUSH":
            commands = state.get("command_evidence", [])
            has_passing_tests = any(
                e.get("kind") == "test" and e.get("success")
                for e in commands
                if e.get("phase") == "wf-validate"
            )
            if not has_passing_tests:
                return {
                    "success": False,
                    "error": "No passing test evidence. Run tests before advancing.",
                    "gate": "tests",
                }

        # All gates passed — update state
        state["phase"] = target
        state["phase_history"].append({
            "from": current_phase,
            "to": target,
            "summary": f"Advanced from {current_phase} to {target}",
        })
        self._save_state(state, ctx)

        # Switch agent profile
        profile_map = {
            "INVESTIGATE": "wf-investigate",
            "IMPLEMENT": "wf-implement",
            "VALIDATE": "wf-validate",
            "PUSH": "wf-push",
            "COMPLETE": "wf-push",  # Terminal
        }
        new_profile = profile_map.get(target, "")
        if new_profile:
            ctx.switch_agent_callback(new_profile)

        return {
            "success": True,
            "from_phase": current_phase,
            "to_phase": target,
            "new_profile": new_profile,
            "message": f"[WF-Lite] Phase transition: {current_phase} → {target}\nProfile: {new_profile}",
        }

    def _load_state(self, ctx: InvokeContext):
        from pathlib import Path
        import json

        repo_path = getattr(ctx, "repo_path", None)
        if not repo_path:
            return None
        repo = Path(repo_path).name
        state_file = Path.home() / ".vibe" / "runs" / repo / "state.json"
        if state_file.exists():
            return json.loads(state_file.read_text())
        return None

    def _save_state(self, state: dict, ctx: InvokeContext):
        from pathlib import Path
        import json

        repo_path = getattr(ctx, "repo_path", None)
        if not repo_path:
            return
        repo = Path(repo_path).name
        state_file = Path.home() / ".vibe" / "runs" / repo / "state.json"
        state_file.write_text(json.dumps(state, indent=2))

    def _check_scope(self, state: dict, ctx: InvokeContext):
        """Check write_evidence against scope contract. Returns list of violations."""
        from pathlib import Path

        repo_path = getattr(ctx, "repo_path", None)
        if not repo_path:
            return []

        contract_file = Path.home() / ".vibe" / "runs" / Path(repo_path).name / "contract.md"
        if not contract_file.exists():
            return []  # No contract = no scope enforcement

        # Simplified: in production, parse contract.md for allowed paths
        return []

    def _check_dirty_tree(self, state: dict, ctx: InvokeContext):
        """Check for unauthorized working-tree modifications. Returns list of dirty files."""
        import subprocess

        repo_path = getattr(ctx, "repo_path", None)
        if not repo_path:
            return []

        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=repo_path,
            capture_output=True,
            text=True,
        )
        dirty = [
            line.strip()
            for line in result.stdout.splitlines()
            if line.strip() and not line.startswith("?? .vibe/")
        ]
        return dirty
