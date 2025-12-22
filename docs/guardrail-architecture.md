# CompyMac Guardrail Architecture

## Problem Statement

LLM-based agents are vulnerable to hallucination - not just "linguistic errors" but fabricated or misjudged behaviors that can occur at any stage of the agent pipeline. When an agent can bulk-rewrite state (like declaring all todos complete), there's no architectural defense against hallucination ruining an entire job.

This document defines CompyMac's guardrail architecture pattern to prevent agents from "declaring victory" without verifiable evidence.

## Research Foundation

Based on recent arxiv research on agent hallucinations:

**"LLM-based Agents Suffer from Hallucinations: A Survey" (arXiv:2509.18970)**
- Agent hallucinations have longer propagation chains than regular LLM hallucinations
- Errors span multiple steps and accumulate over time
- Consequences are "physically consequential" - affecting real-world task execution

**"AgentSpec: Customizable Runtime Enforcement" (arXiv:2503.18666)**
- Runtime constraints with triggers, predicates, and enforcement mechanisms
- Constraints checked at execution time, not just prompting

**"MIRAGE-Bench" (arXiv:2507.21017)**
- Three types of agentic hallucinations:
  1. Actions unfaithful to task instructions
  2. Actions unfaithful to execution history
  3. Actions unfaithful to environment observations

## Core Principles

### 1. Immutable Audit Log

Every state mutation must be logged with:
- Timestamp
- Actor ID (which agent/tool made the change)
- Operation type
- Before/after state
- Tool call ID that triggered the change

The log is append-only. No operation can erase or modify history.

**CompyMac Implementation**: EventLog and TraceStore already provide this foundation.

### 2. Per-Item Targeting with Stable IDs

State mutations must target specific items by stable ID. No bulk "replace all" operations that could rewrite history.

**Anti-pattern (vulnerable to hallucination)**:
```python
TodoWrite(todos=[...])  # Replaces entire list - agent can "declare victory"
```

**Correct pattern**:
```python
TodoCreate(content="...", status="pending") -> returns stable_id
TodoUpdate(id=stable_id, status="in_progress")
TodoComplete(id=stable_id, evidence=[...])
```

### 3. Deterministic Verification

Completion of work items requires machine-checkable evidence, not LLM assertion.

**Types of verifiable evidence**:
- File existence/content checks
- Command exit codes (tests pass, lint passes)
- Git state (commits exist, PRs created)
- API responses (deployment succeeded)
- Tool call IDs that performed the work

**Status state machine**:
```
pending -> in_progress -> claimed_complete -> verified_complete
                              |                    ^
                              |                    |
                              +-- verification ----+
                                   (deterministic)
```

The agent can only set `claimed_complete`. The harness verifies and sets `verified_complete` based on acceptance criteria.

### 4. Runtime Enforcement

Constraints are checked at tool execution time, not just in prompts.

**Enforcement points**:
- Schema validation (already implemented)
- State transition validation (new)
- Evidence validation (new)
- Acceptance criteria checking (new)

## Application to Todo System

### Current Design (Vulnerable)

```python
class TodoWrite:
    """Replace entire todo list"""
    # Agent can write: todos=[] or todos=[{status: "completed"}, ...]
    # No verification that work was actually done
```

### Guardrailed Design

```python
class TodoItem:
    id: str  # Stable UUID, never reused
    content: str
    status: Literal["pending", "in_progress", "claimed", "verified"]
    created_at: datetime
    acceptance_criteria: list[AcceptanceCriterion] | None
    evidence: list[Evidence]  # Tool call IDs, file hashes, etc.

class AcceptanceCriterion:
    type: Literal["command_exit_zero", "file_exists", "file_contains", "pr_merged", ...]
    params: dict  # e.g., {"command": "ruff check", "path": "/src/..."}

class Evidence:
    tool_call_id: str
    timestamp: datetime
    type: str
    data: dict
```

**Tools**:
- `TodoCreate(content, acceptance_criteria?) -> id` - Create one item
- `TodoRead() -> list[TodoItem]` - List all with IDs and status
- `TodoStart(id)` - Move pending -> in_progress
- `TodoClaim(id, evidence)` - Move in_progress -> claimed (agent asserts done)
- `TodoVerify(id)` - Harness checks acceptance criteria, moves claimed -> verified

**What the agent CANNOT do**:
- Bulk-replace the todo list
- Skip status transitions (pending -> verified)
- Set verified status directly
- Delete todos to hide incomplete work

### Audit Log Example

```
[2025-01-15T10:00:00Z] TODO_CREATE id=abc123 content="Fix lint errors" actor=agent
[2025-01-15T10:00:05Z] TODO_START id=abc123 actor=agent
[2025-01-15T10:05:00Z] TODO_CLAIM id=abc123 evidence=[tool_call_id=xyz789] actor=agent
[2025-01-15T10:05:01Z] TODO_VERIFY id=abc123 result=PASS criteria=[ruff_exit_zero] actor=harness
```

## Generalization to Other Stateful Systems

This pattern applies to any stateful system where the agent could "declare victory":

### Memory System
- Facts should have provenance (which tool call established them)
- Fact deletion should be logged, not silent
- Compression/summarization should preserve audit trail

### Session State
- No bulk state replacement
- State transitions logged with evidence

### File Operations
- Already have good patterns (Read/Write/Edit are atomic, logged)
- Could add verification for "file contains expected content"

## Implementation Phases

### Phase 1: Audit Infrastructure
- Extend EventLog/TraceStore to capture state mutations
- Add `StateChange` event type with before/after snapshots

### Phase 2: Todo System Redesign
- Remove TodoWrite bulk operation
- Implement TodoCreate, TodoStart, TodoClaim, TodoVerify
- Add acceptance criteria and evidence tracking

### Phase 3: Verification Engine
- Implement acceptance criterion checkers
- Command exit code checker
- File existence/content checker
- Git state checker
- PR status checker

### Phase 4: Generalize Pattern
- Apply to memory system
- Apply to any new stateful subsystems
- Document pattern for future development

## Success Criteria

The guardrail architecture is successful when:

1. **No bulk rewrite capability** - Agent cannot replace entire state
2. **Immutable history** - All mutations logged, nothing erased
3. **Verifiable completion** - "Done" requires machine-checkable evidence
4. **Audit trail** - Any claim can be traced to supporting tool calls
5. **Hallucination-resistant** - False claims are detectable and correctable

## References

- arXiv:2509.18970 - "LLM-based Agents Suffer from Hallucinations: A Survey"
- arXiv:2503.18666 - "AgentSpec: Customizable Runtime Enforcement for Safe and Reliable LLM Agents"
- arXiv:2507.21017 - "MIRAGE-Bench: LLM Agent is Hallucinating and Where to Find Them"
- arXiv:2406.09187 - "GuardAgent: Safeguard LLM Agents via Knowledge-Enabled Reasoning"
