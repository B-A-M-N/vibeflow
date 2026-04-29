#!/usr/bin/env python3
"""VibeFlow Source Map Generator - machine-readable map of Vibe source locations."""

import json
import sys
from pathlib import Path

def generate_source_map(vibe_source_root="."):
    """Generate source map by scanning Vibe source tree."""
    source_map = {
        "agent_loop": "vibe/agent_loop.py",
        "middleware_interfaces": "vibe/middleware/",
        "tool_executor": "vibe/tools/",
        "skill_manager": "vibe/skills/",
        "config_model": "vibe/config.py",
        "state_checkpoint": "vibe/state.py",
        "cli_registration": "vibe/cli/",
        "acp_integration": "vibe/acp/",
        "session_manager": "vibe/session.py",
        "tool_manager": "vibe/tools/manager.py",
        "llm_backend": "vibe/llm/",
        "streaming_events": "vibe/streaming.py",
    }

    # Verify paths exist
    vibe_root = Path(vibe_source_root)
    for key, path in list(source_map.items()):
        full_path = vibe_root / path
        exists_key = f"{key}_exists"
        if not full_path.exists():
            source_map[exists_key] = "false"
        else:
            source_map[exists_key] = "true"

    return source_map

if __name__ == "__main__":
    root = sys.argv[1] if len(sys.argv) > 1 else "."
    source_map = generate_source_map(root)
    output_path = Path(".vibe-workflow/source-map.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(source_map, f, indent=2)
    print(f"Source map generated: {output_path}")
    print(json.dumps(source_map, indent=2))
