"""
Agent Handoffs - Structured artifact-based communication between agents.

This module implements Gap 6 Phase 1: Structured Artifact Handoffs based on:
- MetaGPT (arXiv:2308.00352): SOP-style structured outputs reduce cascading hallucinations
- AgentOrchestra (arXiv:2506.12508): Capability-based routing with typed artifacts

Key insight: Agents should communicate through typed, validated artifacts rather than
raw workspace state. This enables verification gates and reduces error propagation.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class AgentArtifactType(Enum):
    """Types of artifacts passed between agents in the multi-agent workflow."""
    PROBLEM_STATEMENT = "problem_statement"
    EXECUTION_PLAN = "execution_plan"
    FILE_TARGETS = "file_targets"
    PATCH_PLAN = "patch_plan"
    CODE_CHANGE = "code_change"
    TEST_PLAN = "test_plan"
    TEST_RESULT = "test_result"
    FAILURE_ANALYSIS = "failure_analysis"
    REVIEW_FEEDBACK = "review_feedback"
    PR_DESCRIPTION = "pr_description"
    REFLECTION = "reflection"


class HandoffValidationStatus(Enum):
    """Status of handoff validation."""
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    PENDING = "pending"


@dataclass
class ProblemStatement:
    """Structured understanding of the task/issue."""
    summary: str
    root_cause_hypothesis: str | None = None
    affected_components: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    success_criteria: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "summary": self.summary,
            "root_cause_hypothesis": self.root_cause_hypothesis,
            "affected_components": self.affected_components,
            "constraints": self.constraints,
            "success_criteria": self.success_criteria,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ProblemStatement":
        return cls(
            summary=data.get("summary", ""),
            root_cause_hypothesis=data.get("root_cause_hypothesis"),
            affected_components=data.get("affected_components", []),
            constraints=data.get("constraints", []),
            success_criteria=data.get("success_criteria", []),
        )


@dataclass
class FileTarget:
    """A file targeted for modification."""
    path: str
    reason: str
    change_type: str = "modify"
    confidence: float = 0.8

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "reason": self.reason,
            "change_type": self.change_type,
            "confidence": self.confidence,
        }


@dataclass
class PatchPlan:
    """Plan for specific code changes."""
    file_path: str
    description: str
    search_pattern: str | None = None
    replacement: str | None = None
    line_range: tuple[int, int] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "file_path": self.file_path,
            "description": self.description,
            "search_pattern": self.search_pattern,
            "replacement": self.replacement,
            "line_range": self.line_range,
        }


@dataclass
class TestPlan:
    """Plan for testing changes."""
    test_commands: list[str] = field(default_factory=list)
    expected_outcomes: list[str] = field(default_factory=list)
    lint_commands: list[str] = field(default_factory=list)
    coverage_threshold: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "test_commands": self.test_commands,
            "expected_outcomes": self.expected_outcomes,
            "lint_commands": self.lint_commands,
            "coverage_threshold": self.coverage_threshold,
        }


@dataclass
class FailureAnalysis:
    """Structured analysis of a failure."""
    failure_type: str
    error_message: str
    root_cause: str | None = None
    suggested_fixes: list[str] = field(default_factory=list)
    affected_files: list[str] = field(default_factory=list)
    is_recoverable: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "failure_type": self.failure_type,
            "error_message": self.error_message,
            "root_cause": self.root_cause,
            "suggested_fixes": self.suggested_fixes,
            "affected_files": self.affected_files,
            "is_recoverable": self.is_recoverable,
        }


@dataclass
class ReviewFeedback:
    """Feedback from a reviewer agent."""
    approved: bool
    issues: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)
    confidence: float = 0.8
    requires_changes: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "approved": self.approved,
            "issues": self.issues,
            "suggestions": self.suggestions,
            "confidence": self.confidence,
            "requires_changes": self.requires_changes,
        }


@dataclass
class StructuredHandoff:
    """A structured handoff between agents."""
    from_agent: str
    to_agent: str
    artifact_type: AgentArtifactType
    content: dict[str, Any]
    validation_status: HandoffValidationStatus = HandoffValidationStatus.PENDING
    validation_errors: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    handoff_id: str = ""

    def __post_init__(self):
        if not self.handoff_id:
            import hashlib
            hash_input = f"{self.from_agent}:{self.to_agent}:{self.artifact_type.value}:{self.created_at.isoformat()}"
            self.handoff_id = hashlib.sha256(hash_input.encode()).hexdigest()[:12]

    def to_dict(self) -> dict[str, Any]:
        return {
            "handoff_id": self.handoff_id,
            "from_agent": self.from_agent,
            "to_agent": self.to_agent,
            "artifact_type": self.artifact_type.value,
            "content": self.content,
            "validation_status": self.validation_status.value,
            "validation_errors": self.validation_errors,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "StructuredHandoff":
        handoff = cls(
            from_agent=data["from_agent"],
            to_agent=data["to_agent"],
            artifact_type=AgentArtifactType(data["artifact_type"]),
            content=data["content"],
            validation_status=HandoffValidationStatus(data.get("validation_status", "pending")),
            validation_errors=data.get("validation_errors", []),
            handoff_id=data.get("handoff_id", ""),
        )
        if data.get("created_at"):
            handoff.created_at = datetime.fromisoformat(data["created_at"])
        return handoff


class HandoffValidator:
    """Validates structured handoffs between agents."""

    REQUIRED_FIELDS: dict[AgentArtifactType, list[str]] = {
        AgentArtifactType.PROBLEM_STATEMENT: ["summary"],
        AgentArtifactType.EXECUTION_PLAN: ["steps"],
        AgentArtifactType.FILE_TARGETS: ["targets"],
        AgentArtifactType.PATCH_PLAN: ["file_path", "description"],
        AgentArtifactType.CODE_CHANGE: ["file_path", "diff"],
        AgentArtifactType.TEST_PLAN: ["test_commands"],
        AgentArtifactType.TEST_RESULT: ["passed", "output"],
        AgentArtifactType.FAILURE_ANALYSIS: ["failure_type", "error_message"],
        AgentArtifactType.REVIEW_FEEDBACK: ["approved"],
        AgentArtifactType.PR_DESCRIPTION: ["title", "body"],
        AgentArtifactType.REFLECTION: ["action", "reasoning"],
    }

    VALID_TRANSITIONS: dict[str, list[str]] = {
        "planner": ["executor", "manager"],
        "executor": ["reflector", "manager"],
        "reflector": ["manager", "planner"],
        "manager": ["planner", "executor", "reflector"],
    }

    def validate(self, handoff: StructuredHandoff) -> tuple[bool, list[str]]:
        """
        Validate a structured handoff.

        Returns:
            Tuple of (is_valid, list of error messages)
        """
        errors = []

        if not self._validate_transition(handoff.from_agent, handoff.to_agent):
            errors.append(f"Invalid transition: {handoff.from_agent} -> {handoff.to_agent}")

        field_errors = self._validate_required_fields(handoff.artifact_type, handoff.content)
        errors.extend(field_errors)

        content_errors = self._validate_content(handoff.artifact_type, handoff.content)
        errors.extend(content_errors)

        is_valid = len(errors) == 0
        handoff.validation_status = HandoffValidationStatus.PASSED if is_valid else HandoffValidationStatus.FAILED
        handoff.validation_errors = errors

        if errors:
            logger.warning(f"Handoff validation failed: {errors}")

        return is_valid, errors

    def _validate_transition(self, from_agent: str, to_agent: str) -> bool:
        """Check if the agent transition is valid."""
        from_agent_lower = from_agent.lower()
        to_agent_lower = to_agent.lower()

        if from_agent_lower not in self.VALID_TRANSITIONS:
            return True

        return to_agent_lower in self.VALID_TRANSITIONS.get(from_agent_lower, [])

    def _validate_required_fields(self, artifact_type: AgentArtifactType, content: dict[str, Any]) -> list[str]:
        """Check that required fields are present."""
        errors = []
        required = self.REQUIRED_FIELDS.get(artifact_type, [])

        for field_name in required:
            if field_name not in content:
                errors.append(f"Missing required field '{field_name}' for {artifact_type.value}")
            elif content[field_name] is None or content[field_name] == "":
                errors.append(f"Empty required field '{field_name}' for {artifact_type.value}")

        return errors

    def _validate_content(self, artifact_type: AgentArtifactType, content: dict[str, Any]) -> list[str]:
        """Validate content based on artifact type."""
        errors = []

        if artifact_type == AgentArtifactType.EXECUTION_PLAN:
            steps = content.get("steps", [])
            if not isinstance(steps, list):
                errors.append("'steps' must be a list")
            elif len(steps) == 0:
                errors.append("Execution plan must have at least one step")

        elif artifact_type == AgentArtifactType.FILE_TARGETS:
            targets = content.get("targets", [])
            if not isinstance(targets, list):
                errors.append("'targets' must be a list")
            for i, target in enumerate(targets):
                if not isinstance(target, dict) or "path" not in target:
                    errors.append(f"Target {i} must have a 'path' field")

        elif artifact_type == AgentArtifactType.TEST_RESULT:
            if "passed" in content and not isinstance(content["passed"], bool):
                errors.append("'passed' must be a boolean")

        elif artifact_type == AgentArtifactType.REVIEW_FEEDBACK:
            if "approved" in content and not isinstance(content["approved"], bool):
                errors.append("'approved' must be a boolean")

        return errors


class HandoffManager:
    """Manages structured handoffs between agents with ArtifactStore integration."""

    def __init__(self, artifact_store: Any | None = None):
        """
        Initialize the handoff manager.

        Args:
            artifact_store: Optional ArtifactStore for persistence
        """
        self.validator = HandoffValidator()
        self.artifact_store = artifact_store
        self.handoff_history: list[StructuredHandoff] = []

    def create_handoff(
        self,
        from_agent: str,
        to_agent: str,
        artifact_type: AgentArtifactType,
        content: dict[str, Any],
        validate: bool = True,
    ) -> StructuredHandoff:
        """
        Create a structured handoff between agents.

        Args:
            from_agent: Source agent role
            to_agent: Target agent role
            artifact_type: Type of artifact being handed off
            content: Artifact content
            validate: Whether to validate the handoff

        Returns:
            The created StructuredHandoff
        """
        handoff = StructuredHandoff(
            from_agent=from_agent,
            to_agent=to_agent,
            artifact_type=artifact_type,
            content=content,
        )

        if validate:
            is_valid, errors = self.validator.validate(handoff)
            if not is_valid:
                logger.warning(f"Handoff validation failed: {errors}")

        self.handoff_history.append(handoff)

        if self.artifact_store:
            self._persist_to_artifact_store(handoff)

        logger.info(
            f"[HANDOFF] {from_agent} -> {to_agent}: {artifact_type.value} "
            f"(status={handoff.validation_status.value})"
        )

        return handoff

    def _persist_to_artifact_store(self, handoff: StructuredHandoff) -> None:
        """Persist handoff to ArtifactStore."""
        if not self.artifact_store:
            return

        from compymac.workflows.artifact_store import Artifact, ArtifactType

        artifact_type_map = {
            AgentArtifactType.PROBLEM_STATEMENT: ArtifactType.UNDERSTANDING,
            AgentArtifactType.EXECUTION_PLAN: ArtifactType.PLAN,
            AgentArtifactType.FILE_TARGETS: ArtifactType.NOTE,
            AgentArtifactType.PATCH_PLAN: ArtifactType.SEARCH_REPLACE,
            AgentArtifactType.CODE_CHANGE: ArtifactType.CODE_DIFF,
            AgentArtifactType.TEST_PLAN: ArtifactType.NOTE,
            AgentArtifactType.TEST_RESULT: ArtifactType.TEST_OUTPUT,
            AgentArtifactType.FAILURE_ANALYSIS: ArtifactType.ERROR_ANALYSIS,
            AgentArtifactType.REVIEW_FEEDBACK: ArtifactType.NOTE,
            AgentArtifactType.PR_DESCRIPTION: ArtifactType.PR,
            AgentArtifactType.REFLECTION: ArtifactType.NOTE,
        }

        store_type = artifact_type_map.get(handoff.artifact_type, ArtifactType.GENERIC)

        artifact = Artifact(
            artifact_type=store_type,
            content=handoff.to_dict(),
            stage=f"handoff_{handoff.from_agent}_to_{handoff.to_agent}",
            description=f"Handoff: {handoff.artifact_type.value}",
            metadata={
                "handoff_id": handoff.handoff_id,
                "from_agent": handoff.from_agent,
                "to_agent": handoff.to_agent,
                "validation_status": handoff.validation_status.value,
            },
        )

        self.artifact_store.store(artifact)

    def get_handoffs_for_agent(self, agent: str) -> list[StructuredHandoff]:
        """Get all handoffs targeting a specific agent."""
        return [h for h in self.handoff_history if h.to_agent.lower() == agent.lower()]

    def get_handoffs_from_agent(self, agent: str) -> list[StructuredHandoff]:
        """Get all handoffs from a specific agent."""
        return [h for h in self.handoff_history if h.from_agent.lower() == agent.lower()]

    def get_latest_handoff(self, artifact_type: AgentArtifactType) -> StructuredHandoff | None:
        """Get the most recent handoff of a specific type."""
        matching = [h for h in self.handoff_history if h.artifact_type == artifact_type]
        return matching[-1] if matching else None

    def get_validation_stats(self) -> dict[str, Any]:
        """Get validation statistics for handoffs."""
        total = len(self.handoff_history)
        passed = sum(1 for h in self.handoff_history if h.validation_status == HandoffValidationStatus.PASSED)
        failed = sum(1 for h in self.handoff_history if h.validation_status == HandoffValidationStatus.FAILED)

        return {
            "total_handoffs": total,
            "passed": passed,
            "failed": failed,
            "pass_rate": passed / total if total > 0 else 0.0,
            "by_type": self._count_by_type(),
        }

    def _count_by_type(self) -> dict[str, int]:
        """Count handoffs by artifact type."""
        counts: dict[str, int] = {}
        for handoff in self.handoff_history:
            type_name = handoff.artifact_type.value
            counts[type_name] = counts.get(type_name, 0) + 1
        return counts

    def clear_history(self) -> None:
        """Clear handoff history."""
        self.handoff_history = []
