#!/usr/bin/env python3
"""VibeFlow Convergence Scorer - quantifies workflow convergence behavior."""

import json
import sys
from collections import defaultdict

def score_convergence(simulation_path, manifest_path):
    """Calculate convergence metrics from simulation/trace data."""
    with open(simulation_path) as f:
        sim = json.load(f)
    with open(manifest_path) as f:
        manifest = json.load(f)

    # Count iterations per phase
    phase_iterations = defaultdict(int)
    phase_entries = defaultdict(int)
    phase_exits = defaultdict(int)
    retry_counts = defaultdict(int)

    timeline = sim.get("timeline", [])

    for entry in timeline:
        phase_id = entry.get("phase")
        event = entry.get("event")

        if event == "enter":
            phase_entries[phase_id] += 1
            if phase_entries[phase_id] > 1:
                phase_iterations[phase_id] += 1
        elif event == "exit":
            phase_exits[phase_id] += 1
        elif event == "retry":
            retry_counts[phase_id] += 1

    # Get retry limits from manifest
    retry_limits = {}
    for phase in manifest.get("phases", []):
        retry_limits[phase["id"]] = phase.get("retryLimit", 3)

    # Score each phase
    scores = {}
    all_converged = True
    stalled_phases = []

    for phase_id in phase_entries:
        iterations = phase_iterations.get(phase_id, 0)
        limit = retry_limits.get(phase_id, 3)
        exits = phase_exits.get(phase_id, 0)

        # Convergence: did it exit within retry limit?
        converged = exits > 0 and iterations <= limit
        if not converged:
            all_converged = False

        # Stall detection: many iterations, no exit
        if iterations >= limit and exits == 0:
            stalled_phases.append(phase_id)

        scores[phase_id] = {
            "iterations": iterations,
            "exits": exits,
            "retry_limit": limit,
            "converged": converged,
            "stalled": iterations >= limit and exits == 0,
            "status": "converged" if converged else ("stalled" if iterations >= limit else "in_progress")
        }

    # Overall score
    total_iterations = sum(phase_iterations.values())
    total_exits = sum(phase_exits.values())
    total_phases = len(phase_entries)

    # FAIL if no simulation data exists (no phases entered)
    if total_phases == 0:
        return {
            "overall": {
                "total_iterations": 0,
                "total_exits": 0,
                "phases_entered": 0,
                "phases_stalled": [],
                "all_converged": False,
                "convergence_rate": 0,
                "stalled_phases": [],
                "error": "No simulation data - workflow never entered any phases"
            },
            "phase_scores": {},
            "pass": False
        }

    overall = {
        "total_iterations": total_iterations,
        "total_exits": total_exits,
        "phases_entered": total_phases,
        "phases_stalled": len(stalled_phases),
        "all_converged": all_converged,
        "convergence_rate": total_exits / total_phases if total_phases > 0 else 0,
        "stalled_phases": stalled_phases
    }

    return {
        "overall": overall,
        "phase_scores": scores,
        "pass": all_converged and len(stalled_phases) == 0
    }


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: convergence-scorer.py <simulation.json> <manifest.json>")
        sys.exit(1)

    result = score_convergence(sys.argv[1], sys.argv[2])
    print(json.dumps(result, indent=2))
    sys.exit(0 if result["pass"] else 1)
