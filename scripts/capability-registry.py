#!/usr/bin/env python3
"""VibeFlow Capability Registry - machine-readable runtime capabilities."""

import json

BUILTIN_TOOL_SOURCE = "vibe/core/tools/builtins/"
MIDDLEWARE_SOURCE = "vibe/core/middleware.py"


def build_registry():
    registry = {
        "tools": {
            "bash": {"source": BUILTIN_TOOL_SOURCE, "class": "Bash", "available": True, "aliases": ["Bash"]},
            "read_file": {"source": BUILTIN_TOOL_SOURCE, "class": "ReadFile", "available": True, "aliases": ["ReadFile"]},
            "write_file": {"source": BUILTIN_TOOL_SOURCE, "class": "WriteFile", "available": True, "aliases": ["WriteFile"]},
            "edit": {"source": BUILTIN_TOOL_SOURCE, "class": "EditFile", "available": True, "aliases": ["Edit", "EditFile"]},
            "grep": {"source": BUILTIN_TOOL_SOURCE, "class": "Grep", "available": True, "aliases": ["Grep"]},
            "search_replace": {"source": BUILTIN_TOOL_SOURCE, "class": "SearchReplace", "available": True, "aliases": ["SearchReplace"]},
            "glob": {"source": BUILTIN_TOOL_SOURCE, "class": "Glob", "available": True, "aliases": ["Glob"]},
            "lsp": {"source": BUILTIN_TOOL_SOURCE, "class": "LSP", "available": True, "aliases": ["LSP"]},
            "webfetch": {"source": BUILTIN_TOOL_SOURCE, "class": "WebFetch", "available": True, "aliases": ["WebFetch", "web_fetch"]},
            "websearch": {"source": BUILTIN_TOOL_SOURCE, "class": "WebSearch", "available": True, "aliases": ["WebSearch", "web_search"]},
            "ask_user_question": {"source": BUILTIN_TOOL_SOURCE, "class": "AskUserQuestion", "available": True, "aliases": ["ask_user_question", "AskUserQuestion"]},
            "exit_plan_mode": {"source": BUILTIN_TOOL_SOURCE, "class": "ExitPlanMode", "available": True, "aliases": ["exit_plan_mode", "ExitPlanMode"]},
            "todo": {"source": BUILTIN_TOOL_SOURCE, "class": "Todo", "available": True, "aliases": ["todo", "Todo"]},
            "task": {"source": BUILTIN_TOOL_SOURCE, "class": "Task", "available": True, "aliases": ["task", "Task"]},
        },
        "middleware": {
            "TurnLimitMiddleware": {"interface": MIDDLEWARE_SOURCE, "hooks": ["before_turn"]},
            "PriceLimitMiddleware": {"interface": MIDDLEWARE_SOURCE, "hooks": ["before_turn"]},
            "AutoCompactMiddleware": {"interface": MIDDLEWARE_SOURCE, "hooks": ["before_turn"]},
            "ReadOnlyAgentMiddleware": {"interface": MIDDLEWARE_SOURCE, "hooks": ["before_turn"]},
            "ContextWarningMiddleware": {"interface": MIDDLEWARE_SOURCE, "hooks": ["before_turn"]},
        },
        # NOT built-in. Require Tier D source changes: registration in _setup_middleware() in AgentLoop.
        # Listed as reference examples only — not available without source modification.
        "custom_middleware_examples": {
            "workflow_phase_guard": {"interface": MIDDLEWARE_SOURCE, "hooks": ["before_turn"], "tier": "D", "requires_source_registration": True},
            "no_user_deferral_guard": {"interface": MIDDLEWARE_SOURCE, "hooks": ["before_turn"], "tier": "D", "requires_source_registration": True},
        },
        "skills": {
            "vibe-workflow-init": {"path": "skills/vibe-workflow-init/", "trigger": "init workflow"},
            "vibe-workflow-design": {"path": "skills/vibe-workflow-design/", "trigger": "design workflow"},
            "vibe-workflow-plan": {"path": "skills/vibe-workflow-plan/", "trigger": "plan workflow"},
            "vibe-workflow-apply": {"path": "skills/vibe-workflow-apply/", "trigger": "apply workflow"},
            "vibe-workflow-validate": {"path": "skills/vibe-workflow-validate/", "trigger": "validate workflow"},
            "vibe-workflow-inspect": {"path": "skills/vibe-workflow-inspect/", "trigger": "inspect workflow"},
            "vibe-workflow-update": {"path": "skills/vibe-workflow-update/", "trigger": "update workflow"},
            "vibe-workflow-realize": {"path": "skills/vibe-workflow-realize/", "trigger": "realize existing workflow"},
        },
        "models": ["mistral-large", "mistral-medium", "mixtral-8x22b"],
        "commands": ["vibe", "vibe-acp", "vibe --resume"],
        "permissions": ["read", "write", "execute", "network"]
    }
    return registry


def tool_available(name):
    normalized = str(name).strip()
    registry = build_registry()["tools"]
    if normalized in registry:
        return registry[normalized].get("available", False)
    lowered = normalized.lower()
    for tool_name, spec in registry.items():
        aliases = {alias.lower() for alias in spec.get("aliases", [])}
        if lowered == tool_name.lower() or lowered in aliases:
            return spec.get("available", False)
    return False

if __name__ == "__main__":
    registry = build_registry()
    print(json.dumps(registry, indent=2))
