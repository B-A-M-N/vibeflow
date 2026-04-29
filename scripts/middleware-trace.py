#!/usr/bin/env python3
"""VibeFlow Middleware Trace Mode - shows what middleware fired and what changed."""

import json
from datetime import datetime
from pathlib import Path

class MiddlewareTracer:
    def __init__(self):
        self.trace = []
        self.current_phase = None

    def log_middleware(self, middleware_name, event, details=None):
        entry = {
            "timestamp": datetime.now().isoformat(),
            "type": "middleware",
            "middleware": middleware_name,
            "event": event,
            "phase": self.current_phase,
            "details": details or {}
        }
        self.trace.append(entry)

    def log_phase(self, phase_id, event):
        self.current_phase = phase_id if event == "enter" else self.current_phase
        entry = {
            "timestamp": datetime.now().isoformat(),
            "type": "phase",
            "phase": phase_id,
            "event": event
        }
        self.trace.append(entry)

    def log_tool(self, tool_name, event, args=None, result=None):
        entry = {
            "timestamp": datetime.now().isoformat(),
            "type": "tool",
            "tool": tool_name,
            "event": event,
            "phase": self.current_phase,
            "args": args,
            "result": result
        }
        self.trace.append(entry)

    def log_state(self, mutation, before, after):
        entry = {
            "timestamp": datetime.now().isoformat(),
            "type": "state_mutation",
            "phase": self.current_phase,
            "mutation": mutation,
            "before": before,
            "after": after
        }
        self.trace.append(entry)

    def save(self, output_path):
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            json.dump({"trace": self.trace, "summary": self._summary()}, f, indent=2)

    def _summary(self):
        return {
            "total_events": len(self.trace),
            "middleware_fired": len([t for t in self.trace if t["type"] == "middleware"]),
            "tools_called": len([t for t in self.trace if t["type"] == "tool"]),
            "state_mutations": len([t for t in self.trace if t["type"] == "state_mutation"]),
            "phases_entered": len([t for t in self.trace if t["type"] == "phase" and t["event"] == "enter"])
        }

if __name__ == "__main__":
    # Demo output
    tracer = MiddlewareTracer()
    tracer.log_phase("diagnose", "enter")
    tracer.log_middleware("checkpoint_enforcer", "applied")
    tracer.log_middleware("phase_guard", "allowed")
    tracer.log_tool("read_files", "call", {"target": "foo.py"})
    tracer.log_state("evidence_added", {"evidence": []}, {"evidence": ["read foo.py"]})
    tracer.log_phase("diagnose", "exit")

    print(json.dumps(tracer._summary(), indent=2))
