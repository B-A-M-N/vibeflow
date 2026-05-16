"""
WF-Lite: check_scope tool — Mid-phase scope verification (preview only).

Tier: B (BaseTool subclass)
Source: references/examples/pr-workflow-lite/tools/check_scope.py

This tool does NOT gate phase transitions. It is a preview-only check
the model can call mid-phase to verify it's still within scope.
"""

from pydantic import BaseModel
from vibe.core.tools import BaseTool, InvokeContext


class CheckScopeInput(BaseModel):
    contract_path: str = ""


class CheckScopeTool(BaseTool):
    name = "check_scope"
    description = (
        "Check current write_evidence against scope contract. "
        "Preview only — does not block. Returns list of violations."
    )
    input_schema = CheckScopeInput

    async def execute(self, input: CheckScopeInput, ctx: InvokeContext):
        from pathlib import Path
        import json

        repo_path = getattr(ctx, "repo_path", None)
        if not repo_path:
            return {"success": False, "error": "No repo_path in context"}

        repo = Path(repo_path).name
        state_file = Path.home() / ".vibe" / "runs" / repo / "state.json"
        contract_file = (
            Path(input.contract_path)
            if input.contract_path
            else Path.home() / ".vibe" / "runs" / repo / "contract.md"
        )

        if not state_file.exists():
            return {"success": False, "error": "No state file"}

        state = json.loads(state_file.read_text())
        write_evidence = state.get("write_evidence", [])
        modified_files = [e["path"] for e in write_evidence if e.get("success")]

        if not contract_file.exists():
            return {
                "success": True,
                "violations": [],
                "modified_files": modified_files,
                "warning": "No contract.md found — scope not enforced",
            }

        # Simplified scope check — in production, parse contract for allowed paths
        contract_text = contract_file.read_text()
        violations = []
        for f in modified_files:
            # Check if file path is mentioned in contract scope
            if f not in contract_text:
                violations.append(f)

        return {
            "success": True,
            "violations": violations,
            "modified_files": modified_files,
            "within_scope": len(violations) == 0,
        }
