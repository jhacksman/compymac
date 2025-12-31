# CompyMac Auditor Verification System Design

**Version:** 1.0  
**Created:** 2025-12-31  
**Status:** Design Document  
**Based on:** Arxiv research on multi-agent verification, human-in-the-loop systems, and agent safety

---

## Executive Summary

This document defines the architecture for CompyMac's verification system, which combines:
1. **Auditor Agent** - Independent verification with fresh context
2. **Human Intervention** - User can pause, override, and adjust at any time
3. **Safeguards** - Loop prevention, escalation, and audit trails

The design is backed by recent arxiv research on agent verification and safety.

---

## 1. Research Foundation

### 1.1 Key Papers

| Paper | Arxiv ID | Key Contribution |
|-------|----------|------------------|
| Verifiability-First Agents | 2512.17259 | Lightweight audit agents with attestation protocols, observability-first design |
| AgentAuditor | OpenReview | Memory-augmented reasoning for safety/security evaluation |
| GuardAgent | 2406.09187 | Guard agent with knowledge-enabled reasoning, constrained toolset |
| VeriGuard | 2510.05156 | Dual-stage verification: offline validation + online monitoring |
| Magentic-UI | 2507.22358 | Human-in-the-loop with co-planning, action guards, and checkpoints |
| VerifiAgent | 2504.00406 | Unified verification agent for LLM reasoning |
| FACT-AUDIT | 2502.17924 | Multi-agent framework for dynamic fact-checking |

### 1.2 Key Insights from Research

**From Verifiability-First Agents (2512.17259):**
> "Embeds lightweight Audit Agents that continuously verify intent vs. behavior using constrained reasoning, and enforces challenge-response attestation protocols for high-risk operations."

**From Magentic-UI (2507.22358):**
> "Human-in-the-loop agentic systems offer a promising path forward, combining human oversight and control with AI efficiency to unlock productivity from imperfect systems."

**From GuardAgent (2406.09187):**
> "GuardAgent oversees a target LLM agent by checking whether its inputs/outputs satisfy a set of given guard requests defined by the users."

---

## 2. Architecture Overview

### 2.1 System Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           USER INTERFACE                                 │
│  [Pause] [Resume] [Approve] [Reject] [Add Subtask] [Edit] [Delete]      │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         CONTROL PLANE                                    │
│  - Session state (running/paused)                                        │
│  - Todo version tracking                                                 │
│  - Audit trail (append-only log)                                         │
│  - Loop counters and caps                                                │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                    ┌───────────────┼───────────────┐
                    ▼               ▼               ▼
            ┌───────────┐   ┌───────────┐   ┌───────────┐
            │  WORKER   │   │  AUDITOR  │   │   HUMAN   │
            │   AGENT   │   │   AGENT   │   │ OVERRIDE  │
            └───────────┘   └───────────┘   └───────────┘
                    │               │               │
                    └───────────────┼───────────────┘
                                    ▼
                        ┌───────────────────┐
                        │   TODO STATE      │
                        │   MACHINE         │
                        └───────────────────┘
```

### 2.2 Todo State Machine

```
                                    ┌──────────────┐
                                    │   pending    │
                                    └──────┬───────┘
                                           │ TodoStart
                                           ▼
                                    ┌──────────────┐
                          ┌────────│ in_progress  │◄────────┐
                          │        └──────┬───────┘         │
                          │               │ TodoClaim       │
                          │               ▼                 │
                          │        ┌──────────────┐         │
                          │        │   claimed    │         │
                          │        └──────┬───────┘         │
                          │               │                 │
                          │     ┌─────────┼─────────┐       │
                          │     ▼         ▼         ▼       │
                          │ ┌────────┐ ┌────────┐ ┌────────┐│
                          │ │auditing│ │approved│ │rejected││
                          │ │(auto)  │ │(human) │ │(human) ││
                          │ └───┬────┘ └───┬────┘ └───┬────┘│
                          │     │          │          │     │
                          │     ▼          │          └─────┘
                          │ ┌────────────┐ │      changes_requested
                          │ │  auditor   │ │
                          │ │  verdict   │ │
                          │ └─────┬──────┘ │
                          │       │        │
                          │   ┌───┴───┐    │
                          │   ▼       ▼    ▼
                          │ ┌────┐ ┌──────────┐
                          │ │fail│ │ verified │
                          │ └──┬─┘ └──────────┘
                          │    │
                          └────┘ (back to in_progress with feedback)

Special States:
- needs_human: Escalated due to loop cap or auditor blocked
- blocked: Worker cannot proceed, needs clarification
```

### 2.3 Review Status (Separate from Work Status)

| Status | Description |
|--------|-------------|
| `not_requested` | Todo not yet claimed |
| `auditing` | Auditor agent is reviewing |
| `approved` | Auditor approved (or human approved) |
| `changes_requested` | Auditor/human requested revisions |
| `overridden` | Human overrode auditor verdict |
| `escalated` | Auto-escalated due to loop cap |

---

## 3. Worker-Auditor Dialogue Protocol

### 3.0 Core Principle: Skeptical Verification

**From AgentAuditor research:** The auditor must treat the worker as potentially hallucinating. 
The auditor does NOT take the worker at their word - it verifies against observable artifacts.

### 3.0.1 Worker Claim Requirements

When claiming a todo complete, the worker MUST provide:

```python
@dataclass
class WorkerClaim:
    todo_id: str
    explanation: str  # REQUIRED: What was done, how, why it satisfies criteria
    evidence: list[Evidence]  # Observable artifacts
    files_modified: list[str]  # Paths to changed files
    commands_run: list[CommandLog]  # Commands executed with outputs
```

**Explanation Requirements:**
- Must be self-contained (auditor has no access to worker's conversation)
- Must explain WHAT was done and HOW
- Must reference specific evidence (file paths, command outputs, test results)
- Must be detailed enough for independent verification

**Example Good Explanation:**
```
I implemented the user authentication feature by:
1. Created src/auth/login.py with LoginHandler class (see file_modified evidence)
2. Added password hashing using bcrypt (line 45-60 in login.py)
3. Ran pytest tests/test_auth.py - all 5 tests pass (see command_output evidence)
4. Updated README.md with usage instructions

Evidence: file_modified:src/auth/login.py, command_output:pytest_result
```

**Example Bad Explanation:**
```
Done. I fixed the auth issue.
```

### 3.0.2 Worker-Auditor Dialogue Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                    WORKER-AUDITOR DIALOGUE                       │
└─────────────────────────────────────────────────────────────────┘

Round 0: Worker Claim
┌─────────┐                              ┌─────────┐
│ WORKER  │ ──── Claim + Explanation ───►│ AUDITOR │
│         │      + Evidence              │         │
└─────────┘                              └────┬────┘
                                              │
                                              ▼
                                    ┌─────────────────┐
                                    │ Review evidence │
                                    │ Check artifacts │
                                    │ Run tests       │
                                    └────────┬────────┘
                                              │
                    ┌─────────────────────────┼─────────────────────────┐
                    ▼                         ▼                         ▼
            ┌───────────┐             ┌───────────┐             ┌───────────┐
            │ APPROVED  │             │ FOLLOW-UP │             │ REJECTED  │
            │           │             │ QUESTION  │             │           │
            └───────────┘             └─────┬─────┘             └───────────┘
                                            │
Round 1-N: Follow-up Questions              │
┌─────────┐                                 │
│ WORKER  │ ◄─── Question ──────────────────┘
│         │ ──── Response + More Evidence ──►
└─────────┘                              ┌─────────┐
                                         │ AUDITOR │
                                         └────┬────┘
                                              │
                                    (max 2-3 follow-up rounds)
                                              │
                                              ▼
                                    ┌─────────────────┐
                                    │  FINAL VERDICT  │
                                    └─────────────────┘
```

### 3.0.3 Follow-up Question Protocol

The auditor can ask follow-up questions before reaching a verdict:

```python
@dataclass
class AuditorFollowUp:
    question: str  # Specific question about the work
    evidence_requested: list[str]  # Specific evidence needed
    reason: str  # Why this info is needed for verification
    
@dataclass
class WorkerResponse:
    answer: str  # Response to the question
    additional_evidence: list[Evidence]  # New evidence provided
```

**Safeguards:**
- Maximum 3 follow-up rounds per audit
- Each follow-up must request specific, verifiable information
- If worker cannot provide requested evidence, auditor must decide based on available info

---

## 4. Auditor Agent Design

### 4.1 Auditor Identity & Purpose

The Auditor Agent is a **separate LLM context** that:
- Has NO access to the worker's conversation history (fresh context)
- Receives only the **audit packet** (structured evidence)
- Treats worker claims with skepticism (may be hallucinating)
- Can ask follow-up questions (bounded)
- Produces a **structured verdict** with citations
- Cannot modify files or execute side effects

### 3.2 Auditor Toolset

**Available Tools (Read-Only + Research):**

| Tool | Purpose |
|------|---------|
| `Read` | Read file contents to verify changes |
| `grep` | Search for patterns in codebase |
| `glob` | Find files by pattern |
| `git_diff` | View changes made by worker |
| `git_log` | View commit history |
| `browser_navigate` | Navigate to URLs |
| `browser_view` | View web page content |
| `web_search` | Search the web for fact-checking |
| `arxiv_search` | Search arxiv for research verification |
| `run_tests` | Execute test commands (read-only verification) |

**Future Stubs:**
| Tool | Purpose |
|------|---------|
| `epub_read` | Read EPUB documents |
| `pdf_read` | Read PDF documents |

**NOT Available (No Side Effects):**

| Tool | Reason |
|------|--------|
| `Edit` | No file modifications |
| `Write` | No file creation |
| `bash` (general) | No arbitrary commands |
| `git_commit` | No commits |
| `git_push` | No pushes |
| `deploy` | No deployments |

### 3.3 Auditor System Prompt

```markdown
# Auditor Agent

You are an independent auditor verifying work completed by a worker agent.
Your role is to objectively evaluate whether the claimed work meets the 
acceptance criteria.

## Core Principles

1. **Independence**: You have NO access to the worker's reasoning or conversation.
   You only see the audit packet (evidence).

2. **Evidence-Based**: Every verdict MUST cite specific evidence.
   No citation = cannot approve.

3. **Read-Only**: You can inspect but NEVER modify. No edits, no commits.

4. **Structured Output**: Always produce a verdict in the required schema.

## Audit Process

1. Review the todo description and acceptance criteria
2. Examine the evidence packet (diffs, files, command outputs)
3. Use tools to verify claims:
   - Read files to check implementations
   - Run tests to verify functionality
   - Search web/arxiv to fact-check claims
   - Use browser to verify web-related work
4. Produce a structured verdict

## Verdict Schema

You MUST output your verdict in this exact format:

```json
{
  "verdict": "approved" | "changes_requested" | "blocked",
  "confidence": 0.0-1.0,
  "reasons": [
    {"reason": "string", "evidence_id": "string"}
  ],
  "required_actions": [
    {"action": "string", "priority": "high" | "medium" | "low"}
  ],
  "evidence_citations": ["evidence_id_1", "evidence_id_2"]
}
```

## Rules

- If you cannot verify a claim, verdict = "blocked" with specific info needed
- If evidence is insufficient, verdict = "changes_requested" 
- Only verdict = "approved" if ALL acceptance criteria are verifiably met
- Never approve without at least one evidence citation
- If tests exist, they MUST pass for approval
```

### 3.4 Audit Packet Schema

The auditor receives a structured packet, NOT the full conversation:

```python
@dataclass
class AuditPacket:
    # Todo information
    todo_id: str
    todo_content: str
    acceptance_criteria: list[dict]  # [{type, params}]
    
    # Evidence from worker
    evidence: list[Evidence]  # [{type, data, timestamp}]
    
    # Artifacts
    files_created: list[str]  # File paths
    files_modified: list[str]  # File paths
    git_diff: str  # Unified diff of changes
    
    # Command history
    commands_run: list[CommandLog]  # [{command, stdout, stderr, exit_code}]
    
    # Context
    repo_path: str
    test_command: str | None  # How to run tests
    
    # Audit metadata
    audit_attempt: int  # Which audit attempt this is
    previous_verdicts: list[Verdict]  # Previous audit results
```

---

## 4. Safeguards & Loop Prevention

### 4.1 Bounded Retry Limits

Based on Verifiability-First Agents research, we implement hard caps:

| Counter | Default Cap | On Exceed |
|---------|-------------|-----------|
| `audit_attempts` | 3 | Escalate to `needs_human` |
| `revision_attempts` | 2 | Escalate to `needs_human` |
| `tool_retries` | 3 | Fail the tool call |

```python
class TodoSafeguards:
    MAX_AUDIT_ATTEMPTS = 3
    MAX_REVISION_ATTEMPTS = 2
    MAX_TOOL_RETRIES = 3
    AUDIT_TIMEOUT_SECONDS = 300  # 5 minutes
    TODO_TIMEOUT_SECONDS = 3600  # 1 hour
```

### 4.2 Monotonicity Gate

Prevent "same submission" loops by requiring new evidence:

```python
def can_resubmit_for_audit(todo: Todo, new_evidence: list) -> bool:
    """
    Worker can only resubmit if there's materially new evidence.
    Prevents infinite loops of same submission.
    """
    if not todo.previous_evidence:
        return True
    
    # Check for new evidence types
    old_hashes = {hash(e) for e in todo.previous_evidence}
    new_hashes = {hash(e) for e in new_evidence}
    
    has_new_evidence = bool(new_hashes - old_hashes)
    
    if not has_new_evidence:
        # No new evidence - cannot resubmit
        raise MonotonicityViolation(
            "Cannot resubmit without new evidence. "
            "Add new files, test results, or artifacts."
        )
    
    return True
```

### 4.3 Escalation States

```python
class EscalationTrigger(Enum):
    AUDIT_CAP_EXCEEDED = "audit_attempts > MAX_AUDIT_ATTEMPTS"
    REVISION_CAP_EXCEEDED = "revision_attempts > MAX_REVISION_ATTEMPTS"
    AUDITOR_BLOCKED = "auditor returned verdict=blocked"
    TIMEOUT = "todo exceeded time limit"
    NO_PROGRESS = "no new evidence after revision request"

def check_escalation(todo: Todo) -> EscalationTrigger | None:
    if todo.audit_attempts > MAX_AUDIT_ATTEMPTS:
        return EscalationTrigger.AUDIT_CAP_EXCEEDED
    if todo.revision_attempts > MAX_REVISION_ATTEMPTS:
        return EscalationTrigger.REVISION_CAP_EXCEEDED
    # ... etc
    return None

def escalate_to_human(todo: Todo, trigger: EscalationTrigger):
    todo.status = "needs_human"
    todo.review_status = "escalated"
    todo.escalation_reason = trigger.value
    session.pause()  # Auto-pause for human intervention
    broadcast_escalation(todo)
```

### 4.4 Timeout Mechanisms

```python
class TimeoutConfig:
    # Per tool call
    TOOL_TIMEOUT = 30  # seconds
    
    # Per audit pass
    AUDIT_TIMEOUT = 300  # 5 minutes
    
    # Per todo overall
    TODO_TIMEOUT = 3600  # 1 hour
    
    # Per session
    SESSION_TIMEOUT = 86400  # 24 hours

async def run_with_timeout(coro, timeout: int, on_timeout: Callable):
    try:
        return await asyncio.wait_for(coro, timeout=timeout)
    except asyncio.TimeoutError:
        return on_timeout()
```

---

## 5. Human Intervention UI

### 5.1 Session Controls

| Control | Action |
|---------|--------|
| **Pause** | Stop agent before next action (cooperative pause) |
| **Resume** | Continue agent execution |
| **Stop** | Cancel current run entirely |

### 5.2 Per-Todo Controls

| Control | Action | State Transition |
|---------|--------|------------------|
| **Approve** | User manually verifies | claimed → verified |
| **Reject** | User rejects with feedback | claimed → in_progress |
| **Add Subtask** | Break into nested todos | Creates child todo |
| **Edit** | Modify todo text | Updates content |
| **Delete** | Remove todo | Removes from list |
| **Reorder** | Change priority | Updates order_index |

### 5.3 Feedback/Notes

Each todo has a `notes` field for human feedback:

```python
@dataclass
class TodoNote:
    author: str  # "human" | "auditor" | "worker"
    content: str
    timestamp: datetime
    action: str  # "feedback" | "revision_request" | "clarification"
```

When user rejects with feedback:
1. Note is attached to todo
2. Todo moves to `in_progress`
3. Worker sees feedback in next turn
4. Revision counter increments

### 5.4 Nested Sub-tasks

```python
@dataclass
class Todo:
    id: str
    content: str
    status: str
    parent_id: str | None  # For nesting
    children: list[str]  # Child todo IDs
    order_index: int  # For ordering
    
def can_verify_parent(parent: Todo) -> bool:
    """Parent can only be verified if all children are verified."""
    for child_id in parent.children:
        child = get_todo(child_id)
        if child.status != "verified":
            return False
    return True
```

---

## 6. Audit Trail

### 6.1 Event Schema

Every state change is logged:

```python
@dataclass
class AuditEvent:
    event_id: str
    timestamp: datetime
    todo_id: str
    actor: str  # "worker" | "auditor" | "human" | "system"
    action: str  # "claimed" | "audit_started" | "approved" | etc.
    before_state: dict
    after_state: dict
    payload: dict  # Additional data (verdict, feedback, etc.)
```

### 6.2 Event Types

| Event | Actor | Description |
|-------|-------|-------------|
| `todo_created` | worker/human | New todo added |
| `todo_started` | worker | pending → in_progress |
| `todo_claimed` | worker | in_progress → claimed |
| `audit_started` | system | Auditor spawned |
| `audit_completed` | auditor | Verdict produced |
| `approved` | auditor/human | claimed → verified |
| `changes_requested` | auditor/human | Revision needed |
| `escalated` | system | Auto-escalated to human |
| `human_override` | human | User overrode auditor |
| `paused` | human | Session paused |
| `resumed` | human | Session resumed |

---

## 7. Implementation Plan

### Phase 1: Core Infrastructure
1. Update todo schema with new fields (parent_id, review_status, audit_attempts, etc.)
2. Implement audit trail logging
3. Add safeguard counters and caps

### Phase 2: Auditor Agent
1. Create auditor system prompt
2. Implement audit packet generation
3. Implement auditor tool restrictions
4. Implement verdict parsing

### Phase 3: Human Intervention UI
1. Add pause/resume controls
2. Add per-todo action buttons (approve, reject, edit, delete)
3. Add subtask creation
4. Add feedback/notes UI

### Phase 4: Integration
1. Wire auditor into todo claim flow
2. Implement escalation logic
3. Add WebSocket broadcasts for UI updates
4. Test end-to-end flow

---

## 8. Success Criteria

1. **Auditor Independence**: Auditor has no access to worker conversation
2. **Evidence-Based Verdicts**: All approvals cite specific evidence
3. **Loop Prevention**: No infinite worker↔auditor loops
4. **Human Control**: User can pause/override at any time
5. **Audit Trail**: All state changes logged with actor/timestamp
6. **Nested Tasks**: Parent verification requires child verification

---

## References

1. Gupta, A. (2025). "Verifiability-First Agents: Provable Observability and Lightweight Audit Agents for Controlling Autonomous LLM Systems." arXiv:2512.17259
2. Luo, H. et al. (2025). "AgentAuditor: Human-Level Safety and Security Evaluation for LLM Agents." OpenReview.
3. Xiang, Z. et al. (2024). "GuardAgent: Safeguard LLM Agents by a Guard Agent via Knowledge-Enabled Reasoning." arXiv:2406.09187
4. Miculicich, L. et al. (2025). "VeriGuard: Enhancing LLM Agent Safety via Verified Code Generation." arXiv:2510.05156
5. Mozannar, H. et al. (2025). "Magentic-UI: Towards Human-in-the-loop Agentic Systems." arXiv:2507.22358
6. Han, J. et al. (2025). "VerifiAgent: a Unified Verification Agent in Language Model Reasoning." arXiv:2504.00406
7. Lin, H. et al. (2025). "FACT-AUDIT: An Adaptive Multi-Agent Framework for Dynamic Fact-Checking Evaluation of Large Language Models." arXiv:2502.17924
