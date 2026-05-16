# PR Workflow Lite — Vision

## Goal

Create a guided, semi-automated workflow that takes a GitHub issue URL or code change request and produces a professional pull request through a structured 5-phase pipeline.

## Scope

**In scope:**
- Single-repo PR creation (no fork management)
- Code changes with test coverage
- Automated linting and type-checking via hooks
- GitNexus-powered code intelligence for investigation
- Human approval gate before push

**Out of scope:**
- Multi-repo or fork-aware push routing (see PRForgeVibe for full implementation)
- PR portfolio triage
- Opportunity discovery
- Auto-merge or CI/CD integration

## Success Criteria

1. Every phase transition is gated — the model cannot skip phases
2. Tool schema changes between phases enforce what the model can attempt
3. Unauthorized file modifications in read-only phases are blocked
4. Context compaction between model-tier switches preserves state on disk
5. The workflow recovers from empty model responses and phase stalls (max 5 retries)
6. Human approval is required before any push operation

## Constraints

- Must be implementable without source modifications to `vibe/core/` (Tier B max)
- GitNexus MCP is required for INVESTIGATE phase evidence
- All state must survive compaction (persisted to disk, not held in memory)
- Hooks must be phase-filtered (lint/typecheck only in IMPLEMENT and VALIDATE)

## Assumptions

- GitNexus MCP server is configured and the target repo is indexed
- `gh` CLI is authenticated and configured
- The target repo uses Python (ruff + pyright for hooks)
- User is available for the APPROVAL gate (synchronous workflow)
