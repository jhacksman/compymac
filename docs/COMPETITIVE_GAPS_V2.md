# CompyMac Competitive Gaps Design Document (V2)

This document outlines the critical gaps between CompyMac and production systems like Manus and Devin, with implementation plans for each.

## Gap 1: Verification Not Completing (Auto-Verify)

### Problem
In the current implementation, todos end at "claimed" status instead of "verified". The agent calls `TodoClaim` but never calls `TodoVerify`, leaving tasks in an ambiguous state. This breaks the "done means done" contract that production systems rely on.

### Current Flow
```
pending → in_progress → claimed (STOPS HERE)
```

### Target Flow
```
pending → in_progress → claimed → verified (AUTO)
```

### Implementation Plan

1. **Auto-verify after claim**: When `TodoClaim` is called, automatically trigger verification logic
2. **Verification criteria**: Each todo should have acceptance criteria that can be checked:
   - File exists checks
   - Command output validation
   - Test pass/fail status
   - Code syntax validation
3. **Fallback to manual**: If auto-verification fails or criteria are unclear, prompt agent to provide verification evidence

### Code Changes

**File: `src/compymac/local_harness.py`**
- Modify `_handle_todo_claim()` to automatically call verification after claiming
- Add `auto_verify` parameter to control behavior
- Implement smart verification based on todo content (detect file creation, test running, etc.)

**File: `src/compymac/api/server.py`**
- Update WebSocket broadcast to show verification progress
- Add `verification_in_progress` status for UI feedback

### Success Criteria
- Todos automatically transition to "verified" when evidence supports completion
- UI shows green checkmark for verified todos
- Agent loop properly terminates when all todos are verified

---

## Gap 2: Persistent Workspace Substrate (Firecracker microVMs)

### Problem
Manus/Devin operate a persistent VM/container where software installs, credentials, browser profiles, and artifacts persist across turns and sessions. CompyMac has tools glued to an agent loop, not an always-on development machine.

### Current State
- Tools execute in the host environment
- No isolation between sessions
- No snapshotting or rollback capability
- Browser state lost between sessions

### Target State
- Isolated microVM workspace per project/user (Firecracker-based)
- Persistent filesystem with snapshotting via Firecracker snapshots
- Browser profile persistence
- Credential storage per workspace
- Sub-second VM boot times (~125ms)

### Decision / Rationale

**Docker was evaluated and rejected** for the following reasons:
- Docker containers share the host kernel, providing weaker isolation
- Container state is brittle ("pet container" problem)
- Snapshot/restore semantics are not first-class in Docker
- Security boundary is insufficient for untrusted agent code execution

**Firecracker microVMs were chosen** because:
- Strong isolation boundary (separate kernel per VM)
- First-class snapshot/restore via Firecracker API
- Sub-second boot times make on-demand VMs practical
- Same architecture as E2B (which Manus uses)
- Can run on bare metal (Intel NUC with 16GB RAM)

### Implementation Plan

A complete design document exists at: `/home/ubuntu/firecracker-workspace-service/DESIGN.md`

The implementation is a separate service that CompyMac integrates with:

1. **Firecracker Workspace Service** (separate repo/service)
   - FastAPI REST API for sandbox management
   - Sandbox Manager for Firecracker VM lifecycle
   - Guest Agent (vsock) for command execution inside VMs
   - Persistence Manager for pause/resume/snapshot

2. **CompyMac Integration**
   - Workspace Provider client to call the service API
   - Tool execution routed through workspace sandboxes
   - Session-to-workspace mapping

3. **Key Features**
   - `/sandboxes` - create/list/destroy sandboxes
   - `/sandboxes/{id}/exec` - execute commands in sandbox
   - `/sandboxes/{id}/pause` - snapshot sandbox state
   - `/sandboxes/{id}/resume` - restore from snapshot
   - `/sandboxes/{id}/files/*` - read/write files in sandbox

### Architecture

```
CompyMac Agent
      │
      │ HTTP/REST API
      ▼
Workspace Service (FastAPI)
      │
      │ Unix Socket API
      ▼
Firecracker VMM Process
      │
      ▼
MicroVM (Guest)
  - Kernel (6.x)
  - Root FS (Alpine)
  - Guest Agent (vsock)
  - Workspace Dir (/workspace)
```

### Success Criteria
- Each project gets isolated microVM workspace
- Workspaces persist across sessions via snapshots
- Can pause and resume workspace state in <1 second
- Agent code execution is fully sandboxed

---

## Gap 3: Workflow Closure (Full SWE Loop)

### Problem
Devin's killer feature is completing the full SWE loop: understand task -> plan -> modify code -> run tests/lint -> debug failures -> create PR -> respond to CI -> iterate. CompyMac has pieces but lacks hardened orchestration.

### Current State
- Individual tools exist (git, file ops, CLI)
- No opinionated workflow orchestration
- No automatic failure recovery
- No CI feedback integration

### Target State
- Default SWE workflow that handles common patterns
- Automatic retry on transient failures
- CI status polling and response
- Structured artifact storage (logs, diffs, test output)

### Research Required

**This gap requires research-backed implementation.** See: `docs/GAP3_WORKFLOW_CLOSURE_RESEARCH.md`

Key arxiv papers informing the design:
- **SWE-agent** (arXiv:2405.15793): Agent-Computer Interface design, search-replace format
- **HyperAgent** (OpenReview): Four-agent architecture (Planner, Navigator, Editor, Executor)
- **Meta Engineering Agent** (arXiv:2507.18755): ReAct harness, 15 actions, static analysis + test feedback
- **RepairAgent** (arXiv:2403.17134): FSM-guided tool invocation, interleaved actions
- **PALADIN** (arXiv:2509.25238): Failure recovery patterns, 89.68% recovery rate

### Workflow Stages (from research)

```
UNDERSTAND -> PLAN -> LOCATE -> MODIFY -> VALIDATE -> DEBUG -> PR -> CI -> ITERATE
```

### Key Implementation Patterns (from research)

1. **Search-Replace Format** (not unified diff) - Meta found this outperforms standard diffs
2. **Feedback Loops** - Static analysis + test execution traces significantly improve solve rate
3. **Failure Recovery** - Explicit failure detection and recovery actions (PALADIN patterns)
4. **LLM-as-Judge** - Validate patches meet quality standards before PR creation
5. **Artifact Storage** - Store all outputs for debugging and review

### Implementation Plan

1. **Workflow State Machine**
   - Define stages with validation criteria
   - Implement stage transitions
   - Add retry logic with backoff

2. **Feedback Loop Integration**
   - Test execution with structured output parsing
   - Static analysis (lint, type check) feedback
   - CI status polling and log parsing

3. **Failure Recovery**
   - Detect failure types from tool output
   - Match to known patterns
   - Execute recovery actions

4. **Artifact Management**
   - Store all tool outputs in structured format
   - Link artifacts to workflow stages
   - Make artifacts reviewable in UI

### Code Changes

**New file: `src/compymac/workflows/swe_loop.py`**
- `SWEWorkflow` class with stages: UNDERSTAND, PLAN, LOCATE, MODIFY, VALIDATE, DEBUG, PR, CI, ITERATE
- Methods: `advance()`, `retry()`, `get_artifacts()`
- Feedback loop integration

**New file: `src/compymac/workflows/failure_recovery.py`**
- `FailureRecovery` class with failure pattern matching
- Recovery action execution

**New file: `src/compymac/workflows/ci_integration.py`**
- `CIIntegration` class for CI status polling
- Log parsing for actionable errors
- Auto-fix generation for common errors

**File: `src/compymac/api/server.py`**
- Add workflow status to WebSocket broadcasts
- Expose workflow artifacts via REST API

### Success Criteria
- Agent can complete full PR workflow without manual intervention
- CI failures are automatically addressed (lint, type errors)
- Failure recovery rate > 80% for known failure patterns
- All artifacts are stored and reviewable

---

## Gap 4: Session Continuity (Resume from UI)

### Problem
RunStore exists for session persistence but isn't wired into the UI. Users can't "continue where we left off" from the web interface.

### Current State
- `RunStore` saves sessions to disk
- No UI for listing/resuming sessions
- No project-level memory (what was tried, why it failed)

### Target State
- Session list in UI sidebar
- One-click resume for interrupted sessions
- Project memory that persists learnings

### Implementation Plan

1. **Backend API**
   - Add REST endpoints for session management
   - `/api/sessions` - list sessions
   - `/api/sessions/{id}/resume` - resume session

2. **Frontend UI**
   - Update HistorySidebar to show real sessions
   - Add resume button for each session
   - Show session status (completed, interrupted, failed)

3. **Project Memory**
   - Store learnings per project (repo conventions, setup quirks)
   - Auto-load project memory when resuming

### Code Changes

**File: `src/compymac/api/server.py`**
- Add session management endpoints
- Wire RunStore to API

**File: `web/src/components/layout/HistorySidebar.tsx`**
- Fetch real sessions from API
- Add resume functionality

### Success Criteria
- Users can see all past sessions in UI
- Can resume any interrupted session
- Project-specific learnings persist

---

## Gap 5: Safety and Controls

### Problem
No tool permissioning, sandboxing, cost controls, or human approval gates for risky operations. Can't let users run unattended.

### Current State
- All tools execute with full permissions
- No cost tracking or limits
- No approval workflow for destructive operations
- No audit logging

### Target State
- Tool permission levels (read-only, write, admin)
- Token/cost budgets per session
- Approval gates for risky operations (delete, deploy, etc.)
- Full audit trail

### Implementation Plan

1. **Permission System**
   - Define permission levels for each tool
   - Check permissions before tool execution
   - Allow users to configure permission level

2. **Cost Controls**
   - Track token usage per session
   - Set budgets with warnings and hard limits
   - Pause execution when budget exceeded

3. **Approval Gates**
   - Define risky operations (file delete, git push, deploy)
   - Pause and request approval via WebSocket
   - Resume after user approval

4. **Audit Logging**
   - Log all tool calls with parameters
   - Log all approvals/denials
   - Make audit log searchable

### Code Changes

**New file: `src/compymac/security/permissions.py`**
- `PermissionLevel` enum: READ, WRITE, ADMIN
- `PermissionChecker` class

**New file: `src/compymac/security/approval.py`**
- `ApprovalGate` class for risky operations
- WebSocket integration for approval requests

**File: `src/compymac/api/server.py`**
- Add approval workflow to message handler
- Add cost tracking middleware

### Success Criteria
- Risky operations require user approval
- Sessions respect token budgets
- Full audit trail available

---

## Gap 6: Multi-Agent Orchestration

### Problem
Current parallel cognition is "parallel thoughts", not specialized roles (planner/coder/tester/reviewer) with coordination protocols.

### Current State
- `ParallelHypothesisExecutor` runs same agent in parallel
- `HypothesisArbiter` picks best result
- No role specialization
- No coordination between agents

### Target State
- Specialized agent roles with different prompts/tools
- Coordination protocol for handoffs
- Shared scratchpad for communication
- Conflict resolution for overlapping work

### Implementation Plan

1. **Role Definitions**
   - Define roles: Planner, Coder, Tester, Reviewer
   - Each role has specialized system prompt
   - Each role has restricted tool access

2. **Coordination Protocol**
   - Define handoff messages between roles
   - Implement shared scratchpad
   - Add conflict detection and resolution

3. **Orchestrator**
   - Route tasks to appropriate roles
   - Manage role lifecycles
   - Aggregate results

### Code Changes

**New file: `src/compymac/multi_agent/roles.py`**
- `AgentRole` enum and role definitions
- Role-specific prompts and tool restrictions

**New file: `src/compymac/multi_agent/coordinator.py`**
- `MultiAgentCoordinator` class
- Methods: `assign_task()`, `handoff()`, `resolve_conflict()`

**New file: `src/compymac/multi_agent/scratchpad.py`**
- `SharedScratchpad` for inter-agent communication

### Success Criteria
- Tasks are routed to specialized agents
- Agents can hand off work cleanly
- Conflicts are detected and resolved

---

## Implementation Priority

1. **Gap 1: Auto-Verify** - DONE - Todos auto-verify after claim
2. **Gap 4: Session Continuity** - DONE - UI shows real sessions from RunStore
3. **Gap 3: Workflow Closure** - Infrastructure complete, integration/validation pending
4. **Gap 6: Multi-Agent** - Research complete (see GAP6_MULTI_AGENT_RESEARCH.md), primitives exist but not wired for structured handoffs
5. **Gap 2: Persistent Workspace** - Design complete (Firecracker microVMs), implementation pending on NUC hardware
6. **Gap 5: Safety Controls** - Low priority, optional until unattended operation is a goal

## Status

- Gap 1: COMPLETED
- Gap 4: COMPLETED
- Gap 3: INFRASTRUCTURE COMPLETE - `swe_loop.py`, `failure_recovery.py`, `ci_integration.py`, `artifact_store.py` exist but:
  - Not wired into main agent loop
  - No end-to-end integration tests
  - No SWE-bench validation
  - Needs: integration with AgentLoop, real-world validation
- Gap 2: Design complete, implementation pending (requires NUC setup)
- Gap 5: Deprioritized
- Gap 6: RESEARCH COMPLETE (see GAP6_MULTI_AGENT_RESEARCH.md)
  - Primitives exist (`multi_agent.py`, `parallel.py`) but share raw workspace state
  - Not using structured artifact handoffs as research recommends
  - Needs: typed artifact handoffs, agent-to-agent communication protocol
