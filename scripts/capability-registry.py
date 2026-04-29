#!/usr/bin/env python3
"""VibeFlow Capability Registry - machine-readable list of available tools/middleware/skills."""

import json

def build_registry():
    registry = {
        "tools": {
            "bash": {"source": "vibe/tools/bash.py", "available": True},
            "read_file": {"source": "vibe/tools/read_file.py", "available": True},
            "write_file": {"source": "vibe/tools/write_file.py", "available": True},
            "grep": {"source": "vibe/tools/grep.py", "available": True},
            "search_replace": {"source": "vibe/tools/search_replace.py", "available": True},
        },
        "middleware": {
            "checkpoint_enforcer": {"interface": "vibe/middleware/checkpoint.py", "hooks": ["pre_tool", "post_tool"]},
            "no_user_deferral_guard": {"interface": "vibe/middleware/no_deferral.py", "hooks": ["pre_agent", "post_agent"]},
            "workflow_phase_guard": {"interface": "vibe/middleware/phase_guard.py", "hooks": ["phase_enter", "phase_exit"]},
        },
        "skills": {
            "vibe-workflow-design": {"path": "skills/vibe-workflow-design/", "trigger": "design workflow"},
            "vibe-workflow-apply": {"path": "skills/vibe-workflow-apply/", "trigger": "apply workflow"},
            "vibe-workflow-validate": {"path": "skills/vibe-workflow-validate/", "trigger": "validate workflow"},
        },
        "models": ["mistral-large", "mistral-medium", "mixtral-8x22b"],
        "commands": ["vibe", "vibe-acp", "vibe --resume"],
        "permissions": ["read", "write", "execute", "network"]
    }
    return registry

if __name__ == "__main__":
    registry = build_registry()
    print(json.dumps(registry, indent=2))
