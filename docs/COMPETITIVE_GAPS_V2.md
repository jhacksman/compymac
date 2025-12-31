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

## Gap 2: Persistent Workspace Substrate

### Problem
Manus/Devin operate a persistent VM/container where software installs, credentials, browser profiles, and artifacts persist across turns and sessions. CompyMac has tools glued to an agent loop, not an always-on development machine.

### Current State
- Tools execute in the host environment
- No isolation between sessions
- No snapshotting or rollback capability
- Browser state lost between sessions

### Target State
- Containerized workspace per project/user
- Persistent filesystem with snapshotting
- Browser profile persistence
- Credential storage per workspace

### Implementation Plan

1. **Phase 1: Docker-based workspaces**
   - Create workspace containers on-demand
   - Mount persistent volumes for project files
   - Expose tools via container exec

2. **Phase 2: Snapshotting**
   - Implement checkpoint/restore using Docker commits
   - Allow rollback to previous states
   - Track workspace history

3. **Phase 3: Browser persistence**
   - Persist Playwright browser profiles
   - Store cookies/sessions per workspace

### Code Changes

**New file: `src/compymac/workspace/container.py`**
- `WorkspaceContainer` class for managing Docker containers
- Methods: `create()`, `snapshot()`, `restore()`, `destroy()`

**New file: `src/compymac/workspace/volume.py`**
- `PersistentVolume` class for managing workspace storage
- Methods: `mount()`, `unmount()`, `list_snapshots()`

### Success Criteria
- Each project gets isolated workspace
- Workspaces persist across sessions
- Can snapshot and restore workspace state

---

## Gap 3: Workflow Closure (Full SWE Loop)

### Problem
Devin's killer feature is completing the full SWE loop: understand task → plan → modify code → run tests/lint → debug failures → create PR → respond to CI → iterate. CompyMac has pieces but lacks hardened orchestration.

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

### Implementation Plan

1. **SWE Workflow Orchestrator**
   - Define standard workflow stages
   - Implement stage transitions with validation
   - Add retry logic for each stage

2. **CI Integration**
   - Poll CI status after PR creation
   - Parse CI logs for actionable errors
   - Auto-fix common CI failures (lint, type errors)

3. **Artifact Management**
   - Store all tool outputs in structured format
   - Link artifacts to workflow stages
   - Make artifacts reviewable in UI

### Code Changes

**New file: `src/compymac/workflows/swe_loop.py`**
- `SWEWorkflow` class with stages: PLAN, CODE, TEST, DEBUG, PR, CI, ITERATE
- Methods: `advance()`, `retry()`, `get_artifacts()`

**File: `src/compymac/api/server.py`**
- Add workflow status to WebSocket broadcasts
- Expose workflow artifacts via REST API

### Success Criteria
- Agent can complete full PR workflow without manual intervention
- CI failures are automatically addressed
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

1. **Gap 1: Auto-Verify** - Quick win, fixes broken UX
2. **Gap 4: Session Continuity** - High user value, moderate effort
3. **Gap 5: Safety Controls** - Required for unattended use
4. **Gap 3: Workflow Closure** - Core value proposition
5. **Gap 2: Persistent Workspace** - Infrastructure heavy
6. **Gap 6: Multi-Agent** - Research-heavy, longer term

## Next Steps

Starting with Gap 1 implementation immediately.
