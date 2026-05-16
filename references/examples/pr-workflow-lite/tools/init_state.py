"""
WF-Lite: init_state tool — Initialize workflow state and create branch.

Tier: B (BaseTool subclass)
Source: references/examples/pr-workflow-lite/tools/init_state.py
"""

from pydantic import BaseModel
from vibe.core.tools import BaseTool, InvokeContext


class InitStateInput(BaseModel):
    repo_path: str
    source_url: str
    branch_name: str


class InitStateTool(BaseTool):
    name = "init_state"
    description = "Initialize workflow state file and create working branch. Call once during INTAKE."
    input_schema = InitStateInput

    async def execute(self, input: InitStateInput, ctx: InvokeContext):
        import subprocess
        import json
        from pathlib import Path
        from datetime import datetime, timezone

        # Validate git repo
        result = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            cwd=input.repo_path,
            capture_output=True,
        )
        if result.returncode != 0:
            return {"success": False, "error": "Not a git repository"}

        # Fetch issue/PR context
        fetch_result = subprocess.run(
            ["gh", "issue", "view", input.source_url, "--json", "title,body"],
            capture_output=True,
            text=True,
        )
        issue_context = ""
        if fetch_result.returncode == 0:
            issue_data = json.loads(fetch_result.stdout)
            issue_context = f"{issue_data.get('title', '')}\n\n{issue_data.get('body', '')}"

        # Create and checkout branch
        subprocess.run(
            ["git", "checkout", "-b", input.branch_name],
            cwd=input.repo_path,
            capture_output=True,
        )

        # Get repo info
        remote = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            cwd=input.repo_path,
            capture_output=True,
            text=True,
        )
        repo = remote.stdout.strip().split("/")[-1].replace(".git", "")

        # Initialize state
        state_dir = Path.home() / ".vibe" / "runs" / repo
        state_dir.mkdir(parents=True, exist_ok=True)

        state = {
            "phase": "INTAKE",
            "branch": input.branch_name,
            "repo": repo,
            "repo_path": input.repo_path,
            "source_url": input.source_url,
            "approval_granted": False,
            "gitnexus_used": False,
            "gitnexus_evidence": [],
            "write_evidence": [],
            "command_evidence": [],
            "phase_history": [],
            "todo_state": [],
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

        state_file = state_dir / "state.json"
        state_file.write_text(json.dumps(state, indent=2))

        return {
            "success": True,
            "branch": input.branch_name,
            "repo": repo,
            "state_file": str(state_file),
            "issue_context": issue_context[:500],
        }

    def is_available(self, ctx: InvokeContext):
        # Only available in INTAKE
        return True  # Schema enforcement via agent profile is sufficient
