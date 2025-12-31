"""
Auditor Agent for CompyMac.

This module implements an independent auditor agent that verifies work completed
by the worker agent. The auditor has a fresh context (no access to worker's
conversation history) and makes decisions based on observable evidence.

Key principles (from arxiv research):
- Verifiability-First (2512.17259): Lightweight audit agents with attestation protocols
- AgentAuditor (OpenReview): Memory-augmented reasoning, skeptical of agent claims
- GuardAgent (2406.09187): Constrained toolset, knowledge-enabled reasoning

The auditor:
1. Receives an audit packet (structured evidence, not conversation history)
2. Can ask follow-up questions (bounded to prevent loops)
3. Produces a structured verdict with evidence citations
4. Cannot modify files or execute side effects (read-only)
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, UTC
from enum import Enum
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    pass


class AuditVerdict(Enum):
    """Possible verdicts from the auditor."""
    APPROVED = "approved"
    CHANGES_REQUESTED = "changes_requested"
    BLOCKED = "blocked"
    FOLLOW_UP = "follow_up"


class ReviewStatus(Enum):
    """Review status for a todo (separate from work status)."""
    NOT_REQUESTED = "not_requested"
    AUDITING = "auditing"
    APPROVED = "approved"
    CHANGES_REQUESTED = "changes_requested"
    OVERRIDDEN = "overridden"
    ESCALATED = "escalated"


class EscalationTrigger(Enum):
    """Reasons for escalating to human."""
    AUDIT_CAP_EXCEEDED = "audit_attempts exceeded maximum"
    REVISION_CAP_EXCEEDED = "revision_attempts exceeded maximum"
    FOLLOW_UP_CAP_EXCEEDED = "follow_up rounds exceeded maximum"
    AUDITOR_BLOCKED = "auditor returned verdict=blocked"
    TIMEOUT = "todo exceeded time limit"
    NO_PROGRESS = "no new evidence after revision request"
    MONOTONICITY_VIOLATION = "resubmission without new evidence"


@dataclass
class Evidence:
    """A piece of evidence supporting a claim."""
    id: str
    type: str  # file_path, command_output, test_result, git_diff, etc.
    data: dict[str, Any]
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "data": self.data,
            "timestamp": self.timestamp.isoformat(),
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Evidence":
        return cls(
            id=data["id"],
            type=data["type"],
            data=data["data"],
            timestamp=datetime.fromisoformat(data["timestamp"]) if isinstance(data.get("timestamp"), str) else datetime.now(UTC),
        )
    
    def content_hash(self) -> str:
        """Hash the evidence content for monotonicity checking."""
        content = json.dumps({"type": self.type, "data": self.data}, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()[:16]


@dataclass
class CommandLog:
    """Log of a command execution."""
    command: str
    stdout: str
    stderr: str
    exit_code: int
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "command": self.command,
            "stdout": self.stdout[:5000],  # Truncate for storage
            "stderr": self.stderr[:2000],
            "exit_code": self.exit_code,
            "timestamp": self.timestamp.isoformat(),
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CommandLog":
        return cls(
            command=data["command"],
            stdout=data.get("stdout", ""),
            stderr=data.get("stderr", ""),
            exit_code=data.get("exit_code", 0),
            timestamp=datetime.fromisoformat(data["timestamp"]) if isinstance(data.get("timestamp"), str) else datetime.now(UTC),
        )


@dataclass
class WorkerClaim:
    """A claim from the worker that a todo is complete."""
    todo_id: str
    explanation: str  # REQUIRED: What was done, how, why it satisfies criteria
    evidence: list[Evidence] = field(default_factory=list)
    files_modified: list[str] = field(default_factory=list)
    commands_run: list[CommandLog] = field(default_factory=list)
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "todo_id": self.todo_id,
            "explanation": self.explanation,
            "evidence": [e.to_dict() for e in self.evidence],
            "files_modified": self.files_modified,
            "commands_run": [c.to_dict() for c in self.commands_run],
            "timestamp": self.timestamp.isoformat(),
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WorkerClaim":
        return cls(
            todo_id=data["todo_id"],
            explanation=data["explanation"],
            evidence=[Evidence.from_dict(e) for e in data.get("evidence", [])],
            files_modified=data.get("files_modified", []),
            commands_run=[CommandLog.from_dict(c) for c in data.get("commands_run", [])],
            timestamp=datetime.fromisoformat(data["timestamp"]) if isinstance(data.get("timestamp"), str) else datetime.now(UTC),
        )
    
    def get_evidence_hashes(self) -> set[str]:
        """Get hashes of all evidence for monotonicity checking."""
        return {e.content_hash() for e in self.evidence}


@dataclass
class AuditorFollowUp:
    """A follow-up question from the auditor."""
    question: str
    evidence_requested: list[str]  # Specific evidence types needed
    reason: str  # Why this info is needed for verification
    round_number: int
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "question": self.question,
            "evidence_requested": self.evidence_requested,
            "reason": self.reason,
            "round_number": self.round_number,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class WorkerResponse:
    """A response from the worker to an auditor follow-up."""
    answer: str
    additional_evidence: list[Evidence] = field(default_factory=list)
    round_number: int = 0
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "answer": self.answer,
            "additional_evidence": [e.to_dict() for e in self.additional_evidence],
            "round_number": self.round_number,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class VerdictReason:
    """A reason for the auditor's verdict."""
    reason: str
    evidence_id: str | None = None
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "reason": self.reason,
            "evidence_id": self.evidence_id,
        }


@dataclass
class RequiredAction:
    """An action required by the auditor."""
    action: str
    priority: str = "medium"  # high, medium, low
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "priority": self.priority,
        }


@dataclass
class AuditorVerdict:
    """The auditor's verdict on a claim."""
    verdict: AuditVerdict
    confidence: float  # 0.0 - 1.0
    reasons: list[VerdictReason] = field(default_factory=list)
    required_actions: list[RequiredAction] = field(default_factory=list)
    evidence_citations: list[str] = field(default_factory=list)
    follow_up: AuditorFollowUp | None = None  # If verdict is FOLLOW_UP
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "verdict": self.verdict.value,
            "confidence": self.confidence,
            "reasons": [r.to_dict() for r in self.reasons],
            "required_actions": [a.to_dict() for a in self.required_actions],
            "evidence_citations": self.evidence_citations,
            "follow_up": self.follow_up.to_dict() if self.follow_up else None,
            "timestamp": self.timestamp.isoformat(),
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AuditorVerdict":
        return cls(
            verdict=AuditVerdict(data["verdict"]),
            confidence=data.get("confidence", 0.5),
            reasons=[VerdictReason(**r) for r in data.get("reasons", [])],
            required_actions=[RequiredAction(**a) for a in data.get("required_actions", [])],
            evidence_citations=data.get("evidence_citations", []),
            follow_up=None,  # TODO: parse follow_up if needed
            timestamp=datetime.fromisoformat(data["timestamp"]) if isinstance(data.get("timestamp"), str) else datetime.now(UTC),
        )


@dataclass
class AuditPacket:
    """
    The structured packet sent to the auditor.
    
    This is the ONLY information the auditor receives - no conversation history.
    """
    # Todo information
    todo_id: str
    todo_content: str
    acceptance_criteria: list[dict[str, Any]] = field(default_factory=list)
    
    # Worker's claim
    worker_claim: WorkerClaim | None = None
    
    # Artifacts
    files_created: list[str] = field(default_factory=list)
    files_modified: list[str] = field(default_factory=list)
    git_diff: str = ""
    
    # Context
    repo_path: str = ""
    test_command: str | None = None
    
    # Audit metadata
    audit_attempt: int = 1
    follow_up_round: int = 0
    previous_verdicts: list[AuditorVerdict] = field(default_factory=list)
    dialogue_history: list[dict[str, Any]] = field(default_factory=list)  # Follow-up Q&A
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "todo_id": self.todo_id,
            "todo_content": self.todo_content,
            "acceptance_criteria": self.acceptance_criteria,
            "worker_claim": self.worker_claim.to_dict() if self.worker_claim else None,
            "files_created": self.files_created,
            "files_modified": self.files_modified,
            "git_diff": self.git_diff[:10000],  # Truncate large diffs
            "repo_path": self.repo_path,
            "test_command": self.test_command,
            "audit_attempt": self.audit_attempt,
            "follow_up_round": self.follow_up_round,
            "previous_verdicts": [v.to_dict() for v in self.previous_verdicts],
            "dialogue_history": self.dialogue_history,
        }


@dataclass
class TodoNote:
    """A note attached to a todo (from human, auditor, or worker)."""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    author: str = "system"  # "human" | "auditor" | "worker" | "system"
    content: str = ""
    action: str = "note"  # "feedback" | "revision_request" | "clarification" | "note"
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "author": self.author,
            "content": self.content,
            "action": self.action,
            "timestamp": self.timestamp.isoformat(),
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TodoNote":
        return cls(
            id=data.get("id", str(uuid.uuid4())[:8]),
            author=data.get("author", "system"),
            content=data.get("content", ""),
            action=data.get("action", "note"),
            timestamp=datetime.fromisoformat(data["timestamp"]) if isinstance(data.get("timestamp"), str) else datetime.now(UTC),
        )


@dataclass
class AuditEvent:
    """An event in the audit trail."""
    event_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    todo_id: str = ""
    actor: str = "system"  # "worker" | "auditor" | "human" | "system"
    action: str = ""  # "claimed" | "audit_started" | "approved" | etc.
    before_state: dict[str, Any] = field(default_factory=dict)
    after_state: dict[str, Any] = field(default_factory=dict)
    payload: dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "timestamp": self.timestamp.isoformat(),
            "todo_id": self.todo_id,
            "actor": self.actor,
            "action": self.action,
            "before_state": self.before_state,
            "after_state": self.after_state,
            "payload": self.payload,
        }


class TodoSafeguards:
    """Safeguards to prevent infinite loops and ensure bounded iteration."""
    
    # Maximum attempts before escalation
    MAX_AUDIT_ATTEMPTS = 3
    MAX_REVISION_ATTEMPTS = 2
    MAX_FOLLOW_UP_ROUNDS = 3
    MAX_TOOL_RETRIES = 3
    
    # Timeouts (in seconds)
    AUDIT_TIMEOUT_SECONDS = 300  # 5 minutes per audit
    TODO_TIMEOUT_SECONDS = 3600  # 1 hour per todo
    SESSION_TIMEOUT_SECONDS = 86400  # 24 hours per session


def check_monotonicity(
    previous_evidence_hashes: set[str],
    new_evidence_hashes: set[str],
) -> bool:
    """
    Check if there's materially new evidence.
    
    Prevents infinite loops where worker resubmits the same evidence.
    Returns True if there's new evidence, False otherwise.
    """
    new_hashes = new_evidence_hashes - previous_evidence_hashes
    return len(new_hashes) > 0


def check_escalation(
    audit_attempts: int,
    revision_attempts: int,
    follow_up_rounds: int,
    last_verdict: AuditorVerdict | None,
) -> EscalationTrigger | None:
    """
    Check if the todo should be escalated to human.
    
    Returns the escalation trigger if escalation is needed, None otherwise.
    """
    if audit_attempts > TodoSafeguards.MAX_AUDIT_ATTEMPTS:
        return EscalationTrigger.AUDIT_CAP_EXCEEDED
    
    if revision_attempts > TodoSafeguards.MAX_REVISION_ATTEMPTS:
        return EscalationTrigger.REVISION_CAP_EXCEEDED
    
    if follow_up_rounds > TodoSafeguards.MAX_FOLLOW_UP_ROUNDS:
        return EscalationTrigger.FOLLOW_UP_CAP_EXCEEDED
    
    if last_verdict and last_verdict.verdict == AuditVerdict.BLOCKED:
        return EscalationTrigger.AUDITOR_BLOCKED
    
    return None


# Auditor system prompt for the LLM
AUDITOR_SYSTEM_PROMPT = """# Auditor Agent

You are an independent auditor verifying work completed by a worker agent.
Your role is to objectively evaluate whether the claimed work meets the acceptance criteria.

## Core Principles

1. **Independence**: You have NO access to the worker's reasoning or conversation.
   You only see the audit packet (evidence).

2. **Skepticism**: The worker may be hallucinating. Do NOT take claims at face value.
   Verify against observable artifacts (files, test outputs, git diffs).

3. **Evidence-Based**: Every verdict MUST cite specific evidence.
   No citation = cannot approve.

4. **Read-Only**: You can inspect but NEVER modify. No edits, no commits.

5. **Structured Output**: Always produce a verdict in the required JSON schema.

## Available Tools

You have access to read-only tools for verification:
- Read: Read file contents
- grep: Search for patterns in codebase
- glob: Find files by pattern
- git_diff: View changes made by worker
- git_log: View commit history
- browser_navigate: Navigate to URLs
- browser_view: View web page content
- web_search: Search the web for fact-checking
- run_tests: Execute test commands (verification only)

You do NOT have access to:
- Edit, Write (no file modifications)
- bash (no arbitrary commands)
- git_commit, git_push (no commits)
- deploy (no deployments)

## Audit Process

1. Review the todo description and acceptance criteria
2. Read the worker's explanation carefully (but skeptically)
3. Examine the evidence packet (diffs, files, command outputs)
4. Use tools to VERIFY claims independently:
   - Read files to check implementations actually exist
   - Run tests to verify functionality
   - Check git diff to see actual changes
   - Search web/arxiv to fact-check claims if needed
5. If you need more information, ask a follow-up question
6. Produce a structured verdict

## Verdict Schema

You MUST output your verdict as a JSON object with this exact structure:

```json
{
  "verdict": "approved" | "changes_requested" | "blocked" | "follow_up",
  "confidence": 0.0-1.0,
  "reasons": [
    {"reason": "description of why", "evidence_id": "evidence_id or null"}
  ],
  "required_actions": [
    {"action": "what needs to be done", "priority": "high" | "medium" | "low"}
  ],
  "evidence_citations": ["evidence_id_1", "evidence_id_2"],
  "follow_up_question": "question if verdict is follow_up, null otherwise"
}
```

## Rules

- If you cannot verify a claim, verdict = "blocked" with specific info needed
- If evidence is insufficient, verdict = "changes_requested" with required actions
- Only verdict = "approved" if ALL acceptance criteria are verifiably met
- Never approve without at least one evidence citation
- If tests exist and are relevant, they MUST pass for approval
- You may ask up to 3 follow-up questions total before making a final verdict
- Be specific in your reasons - cite file paths, line numbers, test names
"""


def generate_auditor_prompt(packet: AuditPacket) -> str:
    """
    Generate the full prompt for the auditor agent.
    
    This combines the system prompt with the audit packet.
    """
    prompt_parts = [AUDITOR_SYSTEM_PROMPT, "\n\n---\n\n# Audit Packet\n"]
    
    # Todo information
    prompt_parts.append(f"## Todo\n")
    prompt_parts.append(f"**ID:** {packet.todo_id}\n")
    prompt_parts.append(f"**Content:** {packet.todo_content}\n")
    
    if packet.acceptance_criteria:
        prompt_parts.append(f"\n**Acceptance Criteria:**\n")
        for i, criterion in enumerate(packet.acceptance_criteria, 1):
            prompt_parts.append(f"{i}. {criterion}\n")
    
    # Worker's claim
    if packet.worker_claim:
        prompt_parts.append(f"\n## Worker's Claim\n")
        prompt_parts.append(f"**Explanation:**\n{packet.worker_claim.explanation}\n")
        
        if packet.worker_claim.files_modified:
            prompt_parts.append(f"\n**Files Modified:** {', '.join(packet.worker_claim.files_modified)}\n")
        
        if packet.worker_claim.evidence:
            prompt_parts.append(f"\n**Evidence Provided:**\n")
            for e in packet.worker_claim.evidence:
                prompt_parts.append(f"- [{e.id}] {e.type}: {json.dumps(e.data)[:500]}\n")
        
        if packet.worker_claim.commands_run:
            prompt_parts.append(f"\n**Commands Run:**\n")
            for cmd in packet.worker_claim.commands_run:
                prompt_parts.append(f"- `{cmd.command}` (exit code: {cmd.exit_code})\n")
    
    # Git diff
    if packet.git_diff:
        prompt_parts.append(f"\n## Git Diff\n```diff\n{packet.git_diff[:5000]}\n```\n")
    
    # Context
    prompt_parts.append(f"\n## Context\n")
    prompt_parts.append(f"**Repo Path:** {packet.repo_path}\n")
    if packet.test_command:
        prompt_parts.append(f"**Test Command:** {packet.test_command}\n")
    
    # Audit metadata
    prompt_parts.append(f"\n## Audit Metadata\n")
    prompt_parts.append(f"**Audit Attempt:** {packet.audit_attempt}\n")
    prompt_parts.append(f"**Follow-up Round:** {packet.follow_up_round}\n")
    
    # Previous verdicts
    if packet.previous_verdicts:
        prompt_parts.append(f"\n**Previous Verdicts:**\n")
        for v in packet.previous_verdicts:
            prompt_parts.append(f"- {v.verdict.value}: {[r.reason for r in v.reasons]}\n")
    
    # Dialogue history
    if packet.dialogue_history:
        prompt_parts.append(f"\n## Follow-up Dialogue\n")
        for entry in packet.dialogue_history:
            if entry.get("type") == "question":
                prompt_parts.append(f"**Auditor Question:** {entry.get('content', '')}\n")
            elif entry.get("type") == "response":
                prompt_parts.append(f"**Worker Response:** {entry.get('content', '')}\n")
    
    # Instructions
    prompt_parts.append(f"\n---\n\n")
    prompt_parts.append(f"Now verify this claim. Use your tools to check the evidence, then output your verdict as JSON.\n")
    
    return "".join(prompt_parts)


def parse_auditor_verdict(response: str) -> AuditorVerdict | None:
    """
    Parse the auditor's response into a structured verdict.
    
    Returns None if parsing fails.
    """
    # Try to extract JSON from the response
    try:
        # Look for JSON block
        json_match = None
        
        # Try to find JSON in code block
        import re
        code_block_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response, re.DOTALL)
        if code_block_match:
            json_match = code_block_match.group(1)
        else:
            # Try to find raw JSON
            json_start = response.find('{')
            json_end = response.rfind('}')
            if json_start != -1 and json_end != -1:
                json_match = response[json_start:json_end + 1]
        
        if not json_match:
            return None
        
        data = json.loads(json_match)
        
        # Parse verdict
        verdict_str = data.get("verdict", "blocked")
        try:
            verdict = AuditVerdict(verdict_str)
        except ValueError:
            verdict = AuditVerdict.BLOCKED
        
        # Parse reasons
        reasons = []
        for r in data.get("reasons", []):
            if isinstance(r, dict):
                reasons.append(VerdictReason(
                    reason=r.get("reason", ""),
                    evidence_id=r.get("evidence_id"),
                ))
            elif isinstance(r, str):
                reasons.append(VerdictReason(reason=r))
        
        # Parse required actions
        required_actions = []
        for a in data.get("required_actions", []):
            if isinstance(a, dict):
                required_actions.append(RequiredAction(
                    action=a.get("action", ""),
                    priority=a.get("priority", "medium"),
                ))
            elif isinstance(a, str):
                required_actions.append(RequiredAction(action=a))
        
        # Parse follow-up if verdict is FOLLOW_UP
        follow_up = None
        if verdict == AuditVerdict.FOLLOW_UP:
            question = data.get("follow_up_question", "")
            if question:
                follow_up = AuditorFollowUp(
                    question=question,
                    evidence_requested=data.get("evidence_requested", []),
                    reason="Auditor needs more information",
                    round_number=0,  # Will be set by caller
                )
        
        return AuditorVerdict(
            verdict=verdict,
            confidence=float(data.get("confidence", 0.5)),
            reasons=reasons,
            required_actions=required_actions,
            evidence_citations=data.get("evidence_citations", []),
            follow_up=follow_up,
        )
    
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        # If parsing fails, return a blocked verdict
        return AuditorVerdict(
            verdict=AuditVerdict.BLOCKED,
            confidence=0.0,
            reasons=[VerdictReason(reason=f"Failed to parse auditor response: {e}")],
        )
