"""
Gap 6 Phase 3: Dynamic Orchestration Heuristics.

This module provides lightweight dynamic routing without RL training:
1. Capability-based agent routing
2. Task complexity estimation
3. Routing heuristics based on task type
4. Feedback loop to improve routing over time

Based on research from:
- AgentOrchestra (arXiv:2506.12508): Capability-based routing
- Evolving Orchestration (arXiv:2505.19591): Dynamic adaptation
- ALMAS (arXiv:2510.03463): Role-based agent alignment

Success Metric: 20% reduction in unnecessary agent invocations.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any

from compymac.workflows.agent_handoffs import (
    AgentArtifactType,
    HandoffManager,
)

if TYPE_CHECKING:
    from compymac.llm_client import LLMClient


class AgentCapability(Enum):
    """Capabilities that agents can have."""

    PLANNING = "planning"  # Breaking down tasks into steps
    CODING = "coding"  # Writing and modifying code
    TESTING = "testing"  # Running and analyzing tests
    DEBUGGING = "debugging"  # Finding and fixing bugs
    REVIEWING = "reviewing"  # Code review and quality checks
    REFACTORING = "refactoring"  # Improving code structure
    DOCUMENTATION = "documentation"  # Writing docs and comments
    RESEARCH = "research"  # Gathering information
    FILE_OPERATIONS = "file_operations"  # Reading/writing files
    SHELL_OPERATIONS = "shell_operations"  # Running commands
    BROWSER_OPERATIONS = "browser_operations"  # Web interactions


class TaskType(Enum):
    """Types of tasks that can be routed."""

    BUG_FIX = "bug_fix"
    FEATURE = "feature"
    REFACTOR = "refactor"
    TEST = "test"
    DOCUMENTATION = "documentation"
    DEBUGGING = "debugging"
    RESEARCH = "research"
    CODE_REVIEW = "code_review"
    DEPLOYMENT = "deployment"
    UNKNOWN = "unknown"


class TaskComplexity(Enum):
    """Estimated complexity levels for tasks."""

    TRIVIAL = "trivial"  # Single file, few lines, obvious fix
    SIMPLE = "simple"  # 1-2 files, straightforward changes
    MODERATE = "moderate"  # 3-5 files, some dependencies
    COMPLEX = "complex"  # 5-10 files, significant changes
    VERY_COMPLEX = "very_complex"  # 10+ files, architectural changes


class AgentRole(Enum):
    """Roles that agents can play (mirrors multi_agent.py)."""

    MANAGER = "manager"
    PLANNER = "planner"
    EXECUTOR = "executor"
    REFLECTOR = "reflector"
    REVIEWER = "reviewer"  # Extended for Phase 3


@dataclass
class AgentCapabilityProfile:
    """Profile of an agent's capabilities with proficiency scores."""

    agent_role: AgentRole
    capabilities: dict[AgentCapability, float] = field(default_factory=dict)
    preferred_task_types: list[TaskType] = field(default_factory=list)
    max_complexity: TaskComplexity = TaskComplexity.COMPLEX

    def get_proficiency(self, capability: AgentCapability) -> float:
        """Get proficiency score for a capability (0.0 to 1.0)."""
        return self.capabilities.get(capability, 0.0)

    def can_handle_complexity(self, complexity: TaskComplexity) -> bool:
        """Check if agent can handle the given complexity level."""
        complexity_order = list(TaskComplexity)
        return complexity_order.index(complexity) <= complexity_order.index(
            self.max_complexity
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_role": self.agent_role.value,
            "capabilities": {k.value: v for k, v in self.capabilities.items()},
            "preferred_task_types": [t.value for t in self.preferred_task_types],
            "max_complexity": self.max_complexity.value,
        }


# Default capability profiles for standard agents
DEFAULT_AGENT_PROFILES: dict[AgentRole, AgentCapabilityProfile] = {
    AgentRole.PLANNER: AgentCapabilityProfile(
        agent_role=AgentRole.PLANNER,
        capabilities={
            AgentCapability.PLANNING: 1.0,
            AgentCapability.RESEARCH: 0.8,
            AgentCapability.DOCUMENTATION: 0.6,
        },
        preferred_task_types=[TaskType.FEATURE, TaskType.REFACTOR],
        max_complexity=TaskComplexity.VERY_COMPLEX,
    ),
    AgentRole.EXECUTOR: AgentCapabilityProfile(
        agent_role=AgentRole.EXECUTOR,
        capabilities={
            AgentCapability.CODING: 1.0,
            AgentCapability.FILE_OPERATIONS: 1.0,
            AgentCapability.SHELL_OPERATIONS: 1.0,
            AgentCapability.TESTING: 0.7,
            AgentCapability.DEBUGGING: 0.8,
        },
        preferred_task_types=[TaskType.BUG_FIX, TaskType.FEATURE, TaskType.TEST],
        max_complexity=TaskComplexity.COMPLEX,
    ),
    AgentRole.REFLECTOR: AgentCapabilityProfile(
        agent_role=AgentRole.REFLECTOR,
        capabilities={
            AgentCapability.REVIEWING: 1.0,
            AgentCapability.DEBUGGING: 0.9,
            AgentCapability.TESTING: 0.8,
        },
        preferred_task_types=[TaskType.CODE_REVIEW, TaskType.DEBUGGING],
        max_complexity=TaskComplexity.VERY_COMPLEX,
    ),
    AgentRole.REVIEWER: AgentCapabilityProfile(
        agent_role=AgentRole.REVIEWER,
        capabilities={
            AgentCapability.REVIEWING: 1.0,
            AgentCapability.DOCUMENTATION: 0.7,
            AgentCapability.REFACTORING: 0.6,
        },
        preferred_task_types=[TaskType.CODE_REVIEW, TaskType.DOCUMENTATION],
        max_complexity=TaskComplexity.VERY_COMPLEX,
    ),
}


@dataclass
class TaskAnalysis:
    """Analysis of a task for routing decisions."""

    task_description: str
    detected_type: TaskType
    estimated_complexity: TaskComplexity
    required_capabilities: list[AgentCapability]
    file_count_estimate: int = 0
    keywords: list[str] = field(default_factory=list)
    confidence: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_description": self.task_description[:200],
            "detected_type": self.detected_type.value,
            "estimated_complexity": self.estimated_complexity.value,
            "required_capabilities": [c.value for c in self.required_capabilities],
            "file_count_estimate": self.file_count_estimate,
            "keywords": self.keywords,
            "confidence": self.confidence,
        }


@dataclass
class RoutingDecision:
    """A routing decision with reasoning."""

    task_analysis: TaskAnalysis
    selected_agent: AgentRole
    alternative_agents: list[AgentRole]
    reasoning: str
    confidence: float
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_analysis": self.task_analysis.to_dict(),
            "selected_agent": self.selected_agent.value,
            "alternative_agents": [a.value for a in self.alternative_agents],
            "reasoning": self.reasoning,
            "confidence": self.confidence,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class RoutingOutcome:
    """Outcome of a routing decision for feedback learning."""

    decision: RoutingDecision
    success: bool
    execution_time_ms: int
    iterations_used: int
    errors_encountered: list[str] = field(default_factory=list)
    would_reroute: bool = False
    better_agent: AgentRole | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision.to_dict(),
            "success": self.success,
            "execution_time_ms": self.execution_time_ms,
            "iterations_used": self.iterations_used,
            "errors_encountered": self.errors_encountered,
            "would_reroute": self.would_reroute,
            "better_agent": self.better_agent.value if self.better_agent else None,
        }


class TaskAnalyzer:
    """
    Analyzes tasks to determine type, complexity, and required capabilities.

    Uses keyword matching and heuristics for lightweight analysis without LLM calls.
    """

    # Keywords for task type detection
    TASK_TYPE_KEYWORDS: dict[TaskType, list[str]] = {
        TaskType.BUG_FIX: [
            "fix",
            "bug",
            "error",
            "issue",
            "broken",
            "crash",
            "fail",
            "wrong",
            "incorrect",
        ],
        TaskType.FEATURE: [
            "add",
            "implement",
            "create",
            "new",
            "feature",
            "support",
            "enable",
        ],
        TaskType.REFACTOR: [
            "refactor",
            "clean",
            "improve",
            "optimize",
            "restructure",
            "simplify",
        ],
        TaskType.TEST: [
            "test",
            "coverage",
            "unittest",
            "pytest",
            "spec",
            "verify",
        ],
        TaskType.DOCUMENTATION: [
            "doc",
            "readme",
            "comment",
            "explain",
            "document",
        ],
        TaskType.DEBUGGING: [
            "debug",
            "trace",
            "investigate",
            "diagnose",
            "analyze",
        ],
        TaskType.RESEARCH: [
            "research",
            "explore",
            "find",
            "search",
            "look",
            "understand",
        ],
        TaskType.CODE_REVIEW: [
            "review",
            "check",
            "audit",
            "inspect",
            "validate",
        ],
        TaskType.DEPLOYMENT: [
            "deploy",
            "release",
            "publish",
            "ship",
            "ci",
            "cd",
        ],
    }

    # Capability requirements by task type
    TASK_CAPABILITIES: dict[TaskType, list[AgentCapability]] = {
        TaskType.BUG_FIX: [
            AgentCapability.DEBUGGING,
            AgentCapability.CODING,
            AgentCapability.TESTING,
        ],
        TaskType.FEATURE: [
            AgentCapability.PLANNING,
            AgentCapability.CODING,
            AgentCapability.TESTING,
        ],
        TaskType.REFACTOR: [
            AgentCapability.REFACTORING,
            AgentCapability.CODING,
            AgentCapability.REVIEWING,
        ],
        TaskType.TEST: [AgentCapability.TESTING, AgentCapability.CODING],
        TaskType.DOCUMENTATION: [
            AgentCapability.DOCUMENTATION,
            AgentCapability.RESEARCH,
        ],
        TaskType.DEBUGGING: [
            AgentCapability.DEBUGGING,
            AgentCapability.SHELL_OPERATIONS,
        ],
        TaskType.RESEARCH: [
            AgentCapability.RESEARCH,
            AgentCapability.BROWSER_OPERATIONS,
        ],
        TaskType.CODE_REVIEW: [AgentCapability.REVIEWING, AgentCapability.TESTING],
        TaskType.DEPLOYMENT: [
            AgentCapability.SHELL_OPERATIONS,
            AgentCapability.FILE_OPERATIONS,
        ],
        TaskType.UNKNOWN: [AgentCapability.PLANNING],
    }

    # Complexity indicators
    COMPLEXITY_INDICATORS: dict[TaskComplexity, dict[str, Any]] = {
        TaskComplexity.TRIVIAL: {"max_files": 1, "keywords": ["simple", "quick", "minor", "typo"]},
        TaskComplexity.SIMPLE: {"max_files": 2, "keywords": ["small", "basic", "straightforward"]},
        TaskComplexity.MODERATE: {"max_files": 5, "keywords": ["several", "multiple", "few"]},
        TaskComplexity.COMPLEX: {"max_files": 10, "keywords": ["many", "significant", "major"]},
        TaskComplexity.VERY_COMPLEX: {
            "max_files": 100,
            "keywords": ["all", "entire", "architecture", "redesign"],
        },
    }

    def analyze(self, task_description: str, context: dict[str, Any] | None = None) -> TaskAnalysis:
        """
        Analyze a task to determine its type, complexity, and requirements.

        Args:
            task_description: The task description to analyze
            context: Optional context (file list, repo info, etc.)

        Returns:
            TaskAnalysis with detected type, complexity, and capabilities
        """
        task_lower = task_description.lower()

        # Detect task type
        detected_type, type_confidence = self._detect_task_type(task_lower)

        # Estimate complexity
        estimated_complexity = self._estimate_complexity(task_lower, context)

        # Get required capabilities
        required_capabilities = self.TASK_CAPABILITIES.get(
            detected_type, [AgentCapability.PLANNING]
        )

        # Extract keywords
        keywords = self._extract_keywords(task_lower)

        # Estimate file count from context
        file_count = 0
        if context and "files" in context:
            file_count = len(context["files"])

        return TaskAnalysis(
            task_description=task_description,
            detected_type=detected_type,
            estimated_complexity=estimated_complexity,
            required_capabilities=required_capabilities,
            file_count_estimate=file_count,
            keywords=keywords,
            confidence=type_confidence,
        )

    def _detect_task_type(self, task_lower: str) -> tuple[TaskType, float]:
        """Detect task type from keywords."""
        type_scores: dict[TaskType, int] = {}

        for task_type, keywords in self.TASK_TYPE_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in task_lower)
            if score > 0:
                type_scores[task_type] = score

        if not type_scores:
            return TaskType.UNKNOWN, 0.3

        best_type = max(type_scores, key=type_scores.get)  # type: ignore
        confidence = min(type_scores[best_type] / 3.0, 1.0)  # Normalize to 0-1

        return best_type, confidence

    def _estimate_complexity(
        self, task_lower: str, context: dict[str, Any] | None
    ) -> TaskComplexity:
        """Estimate task complexity from description and context."""
        # Check for complexity keywords
        for complexity, indicators in self.COMPLEXITY_INDICATORS.items():
            for keyword in indicators["keywords"]:
                if keyword in task_lower:
                    return complexity

        # Use file count from context if available
        if context and "files" in context:
            file_count = len(context["files"])
            for complexity, indicators in self.COMPLEXITY_INDICATORS.items():
                if file_count <= indicators["max_files"]:
                    return complexity

        # Default to moderate
        return TaskComplexity.MODERATE

    def _extract_keywords(self, task_lower: str) -> list[str]:
        """Extract relevant keywords from task description."""
        all_keywords = []
        for keywords in self.TASK_TYPE_KEYWORDS.values():
            all_keywords.extend(keywords)

        found = [kw for kw in all_keywords if kw in task_lower]
        return list(set(found))[:10]  # Limit to 10 unique keywords


class CapabilityRouter:
    """
    Routes tasks to agents based on capability matching.

    Matches task requirements to agent capability profiles to find
    the best agent for each task.
    """

    def __init__(
        self,
        agent_profiles: dict[AgentRole, AgentCapabilityProfile] | None = None,
    ):
        self.agent_profiles = agent_profiles or DEFAULT_AGENT_PROFILES

    def route(self, task_analysis: TaskAnalysis) -> RoutingDecision:
        """
        Route a task to the best agent based on capabilities.

        Args:
            task_analysis: Analysis of the task to route

        Returns:
            RoutingDecision with selected agent and reasoning
        """
        scores: dict[AgentRole, float] = {}
        reasons: dict[AgentRole, list[str]] = {}

        for role, profile in self.agent_profiles.items():
            score, reason_list = self._score_agent(task_analysis, profile)
            scores[role] = score
            reasons[role] = reason_list

        # Sort by score
        sorted_agents = sorted(scores.keys(), key=lambda r: scores[r], reverse=True)
        best_agent = sorted_agents[0]
        alternatives = sorted_agents[1:3]  # Top 2 alternatives

        # Build reasoning
        reasoning = f"Selected {best_agent.value} (score: {scores[best_agent]:.2f}). "
        reasoning += "; ".join(reasons[best_agent][:3])

        return RoutingDecision(
            task_analysis=task_analysis,
            selected_agent=best_agent,
            alternative_agents=alternatives,
            reasoning=reasoning,
            confidence=scores[best_agent],
        )

    def _score_agent(
        self,
        task_analysis: TaskAnalysis,
        profile: AgentCapabilityProfile,
    ) -> tuple[float, list[str]]:
        """Score an agent for a task based on capability match."""
        score = 0.0
        reasons: list[str] = []

        # Score based on capability match
        for capability in task_analysis.required_capabilities:
            proficiency = profile.get_proficiency(capability)
            score += proficiency
            if proficiency > 0.5:
                reasons.append(f"Good at {capability.value} ({proficiency:.1f})")

        # Bonus for preferred task type
        if task_analysis.detected_type in profile.preferred_task_types:
            score += 0.5
            reasons.append(f"Prefers {task_analysis.detected_type.value} tasks")

        # Penalty if complexity exceeds max
        if not profile.can_handle_complexity(task_analysis.estimated_complexity):
            score *= 0.5
            reasons.append(f"Complexity {task_analysis.estimated_complexity.value} may be too high")

        # Normalize score
        if task_analysis.required_capabilities:
            score /= len(task_analysis.required_capabilities)

        return score, reasons


class RoutingHeuristic:
    """A single routing heuristic rule."""

    def __init__(
        self,
        name: str,
        condition: str,  # Regex pattern to match
        preferred_agent: AgentRole,
        priority: int = 0,
    ):
        self.name = name
        self.condition = condition
        self.preferred_agent = preferred_agent
        self.priority = priority
        self._pattern = re.compile(condition, re.IGNORECASE)

    def matches(self, task_description: str) -> bool:
        """Check if this heuristic matches the task."""
        return bool(self._pattern.search(task_description))

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "condition": self.condition,
            "preferred_agent": self.preferred_agent.value,
            "priority": self.priority,
        }


# Default routing heuristics
DEFAULT_HEURISTICS: list[RoutingHeuristic] = [
    RoutingHeuristic(
        name="test_failures",
        condition=r"test.*fail|fail.*test|pytest.*error",
        preferred_agent=AgentRole.EXECUTOR,
        priority=10,
    ),
    RoutingHeuristic(
        name="lint_errors",
        condition=r"lint|ruff|flake8|mypy|type.*error",
        preferred_agent=AgentRole.EXECUTOR,
        priority=10,
    ),
    RoutingHeuristic(
        name="code_review",
        condition=r"review|pr|pull.*request|merge",
        preferred_agent=AgentRole.REVIEWER,
        priority=8,
    ),
    RoutingHeuristic(
        name="planning_needed",
        condition=r"plan|design|architect|how.*should",
        preferred_agent=AgentRole.PLANNER,
        priority=9,
    ),
    RoutingHeuristic(
        name="debugging",
        condition=r"debug|trace|why.*not.*work|investigate",
        preferred_agent=AgentRole.REFLECTOR,
        priority=8,
    ),
    RoutingHeuristic(
        name="simple_fix",
        condition=r"typo|simple.*fix|quick.*change|minor",
        preferred_agent=AgentRole.EXECUTOR,
        priority=7,
    ),
]


class HeuristicRouter:
    """
    Routes tasks using pattern-based heuristics.

    Applies heuristic rules in priority order to quickly route
    common task patterns without full capability analysis.
    """

    def __init__(self, heuristics: list[RoutingHeuristic] | None = None):
        self.heuristics = heuristics or DEFAULT_HEURISTICS
        # Sort by priority (highest first)
        self.heuristics.sort(key=lambda h: h.priority, reverse=True)

    def route(self, task_description: str) -> tuple[AgentRole | None, str | None]:
        """
        Try to route using heuristics.

        Args:
            task_description: The task to route

        Returns:
            Tuple of (agent_role, heuristic_name) if matched, (None, None) otherwise
        """
        for heuristic in self.heuristics:
            if heuristic.matches(task_description):
                return heuristic.preferred_agent, heuristic.name

        return None, None

    def add_heuristic(self, heuristic: RoutingHeuristic) -> None:
        """Add a new heuristic and re-sort."""
        self.heuristics.append(heuristic)
        self.heuristics.sort(key=lambda h: h.priority, reverse=True)


class RoutingFeedbackStore:
    """
    Stores routing outcomes for learning and optimization.

    Persists outcomes to disk and provides statistics for
    improving routing decisions over time.
    """

    def __init__(self, storage_path: Path | None = None):
        self.storage_path = storage_path or Path.home() / ".compymac" / "routing_feedback.json"
        self.outcomes: list[RoutingOutcome] = []
        self._load()

    def _load(self) -> None:
        """Load outcomes from disk."""
        if self.storage_path.exists():
            try:
                with open(self.storage_path) as f:
                    data = json.load(f)
                    # Just store raw data for now, full deserialization is complex
                    self._raw_outcomes = data.get("outcomes", [])
            except (json.JSONDecodeError, OSError):
                self._raw_outcomes = []
        else:
            self._raw_outcomes = []

    def _save(self) -> None:
        """Save outcomes to disk."""
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.storage_path, "w") as f:
            json.dump(
                {
                    "outcomes": [o.to_dict() for o in self.outcomes] + self._raw_outcomes,
                    "updated_at": datetime.now(UTC).isoformat(),
                },
                f,
                indent=2,
            )

    def record_outcome(self, outcome: RoutingOutcome) -> None:
        """Record a routing outcome."""
        self.outcomes.append(outcome)
        self._save()

    def get_success_rate(self, agent: AgentRole) -> float:
        """Get success rate for an agent."""
        agent_outcomes = [
            o for o in self.outcomes if o.decision.selected_agent == agent
        ]
        if not agent_outcomes:
            return 0.5  # Default 50% if no data

        successes = sum(1 for o in agent_outcomes if o.success)
        return successes / len(agent_outcomes)

    def get_reroute_suggestions(self) -> dict[AgentRole, AgentRole]:
        """Get suggested reroutes based on feedback."""
        suggestions: dict[AgentRole, dict[AgentRole, int]] = {}

        for outcome in self.outcomes:
            if outcome.would_reroute and outcome.better_agent:
                original = outcome.decision.selected_agent
                better = outcome.better_agent

                if original not in suggestions:
                    suggestions[original] = {}
                if better not in suggestions[original]:
                    suggestions[original][better] = 0
                suggestions[original][better] += 1

        # Return most common reroute for each agent
        result: dict[AgentRole, AgentRole] = {}
        for original, betters in suggestions.items():
            if betters:
                best = max(betters, key=betters.get)  # type: ignore
                result[original] = best

        return result

    def get_statistics(self) -> dict[str, Any]:
        """Get overall routing statistics."""
        total = len(self.outcomes) + len(self._raw_outcomes)
        successes = sum(1 for o in self.outcomes if o.success)

        return {
            "total_outcomes": total,
            "session_outcomes": len(self.outcomes),
            "session_successes": successes,
            "session_success_rate": successes / len(self.outcomes) if self.outcomes else 0.0,
            "reroute_suggestions": len(self.get_reroute_suggestions()),
        }


class DynamicOrchestrator:
    """
    Main orchestrator combining all Phase 3 components.

    Provides intelligent task routing using:
    1. Fast heuristic matching for common patterns
    2. Capability-based routing for complex decisions
    3. Feedback-based optimization over time
    """

    def __init__(
        self,
        llm_client: LLMClient | None = None,
        handoff_manager: HandoffManager | None = None,
        feedback_store: RoutingFeedbackStore | None = None,
        agent_profiles: dict[AgentRole, AgentCapabilityProfile] | None = None,
    ):
        self.llm_client = llm_client
        self.handoff_manager = handoff_manager or HandoffManager()
        self.feedback_store = feedback_store or RoutingFeedbackStore()

        self.task_analyzer = TaskAnalyzer()
        self.capability_router = CapabilityRouter(agent_profiles)
        self.heuristic_router = HeuristicRouter()

        # Track routing decisions for feedback
        self._pending_decisions: dict[str, RoutingDecision] = {}

    def route_task(
        self,
        task_description: str,
        context: dict[str, Any] | None = None,
        use_heuristics: bool = True,
    ) -> RoutingDecision:
        """
        Route a task to the best agent.

        Args:
            task_description: Description of the task
            context: Optional context (files, repo info, etc.)
            use_heuristics: Whether to try fast heuristic routing first

        Returns:
            RoutingDecision with selected agent and reasoning
        """
        # Try fast heuristic routing first
        if use_heuristics:
            heuristic_agent, heuristic_name = self.heuristic_router.route(
                task_description
            )
            if heuristic_agent:
                # Create a quick task analysis for the decision
                analysis = TaskAnalysis(
                    task_description=task_description,
                    detected_type=TaskType.UNKNOWN,
                    estimated_complexity=TaskComplexity.MODERATE,
                    required_capabilities=[],
                    confidence=0.8,
                )
                decision = RoutingDecision(
                    task_analysis=analysis,
                    selected_agent=heuristic_agent,
                    alternative_agents=[],
                    reasoning=f"Matched heuristic: {heuristic_name}",
                    confidence=0.8,
                )
                self._record_decision(decision)
                return decision

        # Full capability-based routing
        analysis = self.task_analyzer.analyze(task_description, context)
        decision = self.capability_router.route(analysis)

        # Apply feedback-based adjustments
        decision = self._apply_feedback_adjustments(decision)

        self._record_decision(decision)
        return decision

    def _apply_feedback_adjustments(
        self, decision: RoutingDecision
    ) -> RoutingDecision:
        """Apply adjustments based on historical feedback."""
        reroute_suggestions = self.feedback_store.get_reroute_suggestions()

        if decision.selected_agent in reroute_suggestions:
            suggested = reroute_suggestions[decision.selected_agent]
            # Only reroute if we have enough confidence
            original_success_rate = self.feedback_store.get_success_rate(
                decision.selected_agent
            )
            suggested_success_rate = self.feedback_store.get_success_rate(suggested)

            if suggested_success_rate > original_success_rate + 0.1:
                # Reroute to better agent
                decision = RoutingDecision(
                    task_analysis=decision.task_analysis,
                    selected_agent=suggested,
                    alternative_agents=[decision.selected_agent]
                    + decision.alternative_agents[:1],
                    reasoning=f"Rerouted from {decision.selected_agent.value} to {suggested.value} based on feedback",
                    confidence=decision.confidence * 0.9,  # Slightly lower confidence
                    created_at=decision.created_at,
                )

        return decision

    def _record_decision(self, decision: RoutingDecision) -> None:
        """Record a routing decision for later feedback."""
        decision_id = f"{decision.created_at.timestamp()}_{decision.selected_agent.value}"
        self._pending_decisions[decision_id] = decision

        # Create handoff artifact
        if self.handoff_manager:
            self.handoff_manager.create_handoff(
                from_agent="orchestrator",
                to_agent=decision.selected_agent.value,
                artifact_type=AgentArtifactType.EXECUTION_PLAN,
                content={
                    "routing_decision": decision.to_dict(),
                    "task_type": decision.task_analysis.detected_type.value,
                    "complexity": decision.task_analysis.estimated_complexity.value,
                },
            )

    def record_outcome(
        self,
        decision_id: str,
        success: bool,
        execution_time_ms: int,
        iterations_used: int,
        errors: list[str] | None = None,
        would_reroute: bool = False,
        better_agent: AgentRole | None = None,
    ) -> None:
        """
        Record the outcome of a routing decision.

        Args:
            decision_id: ID of the decision (from RoutingDecision)
            success: Whether the task succeeded
            execution_time_ms: Time taken to execute
            iterations_used: Number of agent iterations
            errors: Any errors encountered
            would_reroute: Whether a different agent would have been better
            better_agent: The agent that would have been better
        """
        if decision_id not in self._pending_decisions:
            return

        decision = self._pending_decisions.pop(decision_id)
        outcome = RoutingOutcome(
            decision=decision,
            success=success,
            execution_time_ms=execution_time_ms,
            iterations_used=iterations_used,
            errors_encountered=errors or [],
            would_reroute=would_reroute,
            better_agent=better_agent,
        )

        self.feedback_store.record_outcome(outcome)

    def get_orchestration_stats(self) -> dict[str, Any]:
        """Get statistics about orchestration."""
        return {
            "feedback_stats": self.feedback_store.get_statistics(),
            "pending_decisions": len(self._pending_decisions),
            "heuristic_count": len(self.heuristic_router.heuristics),
            "agent_profiles": list(self.capability_router.agent_profiles.keys()),
        }


# Export all public classes
__all__ = [
    "AgentCapability",
    "TaskType",
    "TaskComplexity",
    "AgentRole",
    "AgentCapabilityProfile",
    "TaskAnalysis",
    "RoutingDecision",
    "RoutingOutcome",
    "TaskAnalyzer",
    "CapabilityRouter",
    "RoutingHeuristic",
    "HeuristicRouter",
    "RoutingFeedbackStore",
    "DynamicOrchestrator",
    "DEFAULT_AGENT_PROFILES",
    "DEFAULT_HEURISTICS",
]
