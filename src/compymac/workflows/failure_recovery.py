"""
FailureRecovery - Failure detection and recovery patterns.

This module implements failure recovery based on PALADIN (arXiv:2509.25238):
- Failure pattern detection from tool output
- Recovery action matching
- Taxonomy-aligned recovery strategies

Key insight: Tool failures cause cascading reasoning errors.
PALADIN improves Recovery Rate from 32.76% to 89.68%.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class FailureType(Enum):
    """Types of failures that can occur during workflow execution."""
    # Tool failures
    TIMEOUT = "timeout"
    API_ERROR = "api_error"
    RATE_LIMIT = "rate_limit"
    AUTH_ERROR = "auth_error"
    NETWORK_ERROR = "network_error"

    # Code failures
    SYNTAX_ERROR = "syntax_error"
    IMPORT_ERROR = "import_error"
    TYPE_ERROR = "type_error"
    RUNTIME_ERROR = "runtime_error"

    # Test failures
    TEST_FAILURE = "test_failure"
    ASSERTION_ERROR = "assertion_error"
    FIXTURE_ERROR = "fixture_error"

    # Lint failures
    LINT_ERROR = "lint_error"
    FORMAT_ERROR = "format_error"

    # Git failures
    MERGE_CONFLICT = "merge_conflict"
    PUSH_REJECTED = "push_rejected"
    BRANCH_EXISTS = "branch_exists"

    # CI failures
    CI_TIMEOUT = "ci_timeout"
    CI_BUILD_FAILED = "ci_build_failed"
    CI_TEST_FAILED = "ci_test_failed"
    CI_LINT_FAILED = "ci_lint_failed"

    # Unknown
    UNKNOWN = "unknown"


@dataclass
class RecoveryAction:
    """An action to recover from a failure."""
    name: str
    description: str
    action_type: str  # "retry", "fix", "skip", "escalate"
    parameters: dict[str, Any] = field(default_factory=dict)
    max_attempts: int = 3
    backoff_seconds: int = 1

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "name": self.name,
            "description": self.description,
            "action_type": self.action_type,
            "parameters": self.parameters,
            "max_attempts": self.max_attempts,
            "backoff_seconds": self.backoff_seconds,
        }


@dataclass
class FailureRecord:
    """Record of a detected failure."""
    failure_type: FailureType
    message: str
    context: str
    recovery_action: RecoveryAction | None = None
    recovered: bool = False
    attempts: int = 0
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "failure_type": self.failure_type.value,
            "message": self.message,
            "context": self.context,
            "recovery_action": self.recovery_action.to_dict() if self.recovery_action else None,
            "recovered": self.recovered,
            "attempts": self.attempts,
            "timestamp": self.timestamp.isoformat(),
        }


class FailureRecovery:
    """
    Failure detection and recovery system.

    Based on PALADIN patterns:
    - Failure Injection Training: Learn from recovery-annotated trajectories
    - Failure Exemplar Bank: 55+ failure patterns with recovery actions
    - Taxonomy-Aligned Recovery: Match failures to known patterns
    """

    # Failure pattern bank (based on PALADIN's 55+ patterns)
    FAILURE_PATTERNS: dict[str, tuple[FailureType, RecoveryAction]] = {
        # Timeout patterns
        "timed out": (
            FailureType.TIMEOUT,
            RecoveryAction(
                name="retry_with_timeout",
                description="Retry with increased timeout",
                action_type="retry",
                parameters={"timeout_multiplier": 2},
                max_attempts=3,
                backoff_seconds=5,
            ),
        ),
        "timeout expired": (
            FailureType.TIMEOUT,
            RecoveryAction(
                name="retry_with_timeout",
                description="Retry with increased timeout",
                action_type="retry",
                parameters={"timeout_multiplier": 2},
                max_attempts=3,
                backoff_seconds=5,
            ),
        ),

        # Rate limit patterns
        "rate limit": (
            FailureType.RATE_LIMIT,
            RecoveryAction(
                name="wait_and_retry",
                description="Wait for rate limit reset and retry",
                action_type="retry",
                parameters={"wait_seconds": 60},
                max_attempts=5,
                backoff_seconds=60,
            ),
        ),
        "429": (
            FailureType.RATE_LIMIT,
            RecoveryAction(
                name="wait_and_retry",
                description="Wait for rate limit reset and retry",
                action_type="retry",
                parameters={"wait_seconds": 60},
                max_attempts=5,
                backoff_seconds=60,
            ),
        ),
        "too many requests": (
            FailureType.RATE_LIMIT,
            RecoveryAction(
                name="wait_and_retry",
                description="Wait for rate limit reset and retry",
                action_type="retry",
                parameters={"wait_seconds": 60},
                max_attempts=5,
                backoff_seconds=60,
            ),
        ),

        # Auth patterns
        "unauthorized": (
            FailureType.AUTH_ERROR,
            RecoveryAction(
                name="refresh_auth",
                description="Refresh authentication and retry",
                action_type="fix",
                parameters={"action": "refresh_token"},
                max_attempts=2,
            ),
        ),
        "401": (
            FailureType.AUTH_ERROR,
            RecoveryAction(
                name="refresh_auth",
                description="Refresh authentication and retry",
                action_type="fix",
                parameters={"action": "refresh_token"},
                max_attempts=2,
            ),
        ),
        "403": (
            FailureType.AUTH_ERROR,
            RecoveryAction(
                name="check_permissions",
                description="Check and request necessary permissions",
                action_type="escalate",
                parameters={"action": "request_permissions"},
                max_attempts=1,
            ),
        ),

        # Network patterns
        "connection refused": (
            FailureType.NETWORK_ERROR,
            RecoveryAction(
                name="retry_connection",
                description="Retry connection with backoff",
                action_type="retry",
                max_attempts=5,
                backoff_seconds=10,
            ),
        ),
        "connection reset": (
            FailureType.NETWORK_ERROR,
            RecoveryAction(
                name="retry_connection",
                description="Retry connection with backoff",
                action_type="retry",
                max_attempts=5,
                backoff_seconds=10,
            ),
        ),
        "name resolution failed": (
            FailureType.NETWORK_ERROR,
            RecoveryAction(
                name="check_dns",
                description="Check DNS and network connectivity",
                action_type="fix",
                parameters={"action": "check_network"},
                max_attempts=3,
            ),
        ),

        # Syntax error patterns
        "syntaxerror": (
            FailureType.SYNTAX_ERROR,
            RecoveryAction(
                name="fix_syntax",
                description="Parse error message and fix syntax",
                action_type="fix",
                parameters={"action": "parse_and_fix"},
                max_attempts=3,
            ),
        ),
        "unexpected token": (
            FailureType.SYNTAX_ERROR,
            RecoveryAction(
                name="fix_syntax",
                description="Parse error message and fix syntax",
                action_type="fix",
                parameters={"action": "parse_and_fix"},
                max_attempts=3,
            ),
        ),

        # Import error patterns
        "modulenotfounderror": (
            FailureType.IMPORT_ERROR,
            RecoveryAction(
                name="install_dependency",
                description="Install missing dependency",
                action_type="fix",
                parameters={"action": "pip_install"},
                max_attempts=2,
            ),
        ),
        "importerror": (
            FailureType.IMPORT_ERROR,
            RecoveryAction(
                name="fix_import",
                description="Fix import statement or install dependency",
                action_type="fix",
                parameters={"action": "fix_import_path"},
                max_attempts=3,
            ),
        ),
        "no module named": (
            FailureType.IMPORT_ERROR,
            RecoveryAction(
                name="install_dependency",
                description="Install missing dependency",
                action_type="fix",
                parameters={"action": "pip_install"},
                max_attempts=2,
            ),
        ),

        # Type error patterns
        "typeerror": (
            FailureType.TYPE_ERROR,
            RecoveryAction(
                name="fix_types",
                description="Fix type mismatch",
                action_type="fix",
                parameters={"action": "analyze_types"},
                max_attempts=3,
            ),
        ),

        # Test failure patterns
        "failed": (
            FailureType.TEST_FAILURE,
            RecoveryAction(
                name="analyze_test_failure",
                description="Analyze test failure and fix code",
                action_type="fix",
                parameters={"action": "parse_test_output"},
                max_attempts=5,
            ),
        ),
        "assertionerror": (
            FailureType.ASSERTION_ERROR,
            RecoveryAction(
                name="fix_assertion",
                description="Analyze assertion and fix code or test",
                action_type="fix",
                parameters={"action": "analyze_assertion"},
                max_attempts=3,
            ),
        ),

        # Lint error patterns
        "ruff": (
            FailureType.LINT_ERROR,
            RecoveryAction(
                name="fix_lint",
                description="Apply lint fixes",
                action_type="fix",
                parameters={"action": "ruff_fix"},
                max_attempts=2,
            ),
        ),
        "flake8": (
            FailureType.LINT_ERROR,
            RecoveryAction(
                name="fix_lint",
                description="Apply lint fixes",
                action_type="fix",
                parameters={"action": "manual_fix"},
                max_attempts=3,
            ),
        ),
        "eslint": (
            FailureType.LINT_ERROR,
            RecoveryAction(
                name="fix_lint",
                description="Apply lint fixes",
                action_type="fix",
                parameters={"action": "eslint_fix"},
                max_attempts=2,
            ),
        ),

        # Git patterns
        "merge conflict": (
            FailureType.MERGE_CONFLICT,
            RecoveryAction(
                name="resolve_conflict",
                description="Analyze and resolve merge conflict",
                action_type="fix",
                parameters={"action": "parse_conflict"},
                max_attempts=3,
            ),
        ),
        "conflict": (
            FailureType.MERGE_CONFLICT,
            RecoveryAction(
                name="resolve_conflict",
                description="Analyze and resolve merge conflict",
                action_type="fix",
                parameters={"action": "parse_conflict"},
                max_attempts=3,
            ),
        ),
        "rejected": (
            FailureType.PUSH_REJECTED,
            RecoveryAction(
                name="pull_and_retry",
                description="Pull latest changes and retry push",
                action_type="fix",
                parameters={"action": "git_pull"},
                max_attempts=3,
            ),
        ),
        "already exists": (
            FailureType.BRANCH_EXISTS,
            RecoveryAction(
                name="use_new_branch",
                description="Create branch with different name",
                action_type="fix",
                parameters={"action": "rename_branch"},
                max_attempts=1,
            ),
        ),
    }

    def __init__(self):
        """Initialize failure recovery system."""
        self.failure_history: list[FailureRecord] = []
        self.recovery_stats: dict[str, dict[str, int]] = {}

    def detect_failure(self, output: str) -> FailureType | None:
        """
        Detect failure type from tool output.

        Args:
            output: Output from tool execution

        Returns:
            FailureType if failure detected, None otherwise
        """
        output_lower = output.lower()

        for pattern, (failure_type, _) in self.FAILURE_PATTERNS.items():
            if pattern in output_lower:
                return failure_type

        # Check for generic error indicators
        if "error" in output_lower or "exception" in output_lower:
            return FailureType.UNKNOWN

        return None

    def get_recovery_action(self, failure_type: FailureType, output: str = "") -> RecoveryAction:
        """
        Get appropriate recovery action for failure type.

        Args:
            failure_type: Type of failure
            output: Original output for context

        Returns:
            RecoveryAction to attempt
        """
        output_lower = output.lower()

        # Try to find specific pattern match
        for pattern, (ftype, action) in self.FAILURE_PATTERNS.items():
            if ftype == failure_type and pattern in output_lower:
                return action

        # Default recovery actions by failure type
        default_actions = {
            FailureType.TIMEOUT: RecoveryAction(
                name="retry",
                description="Retry with increased timeout",
                action_type="retry",
                max_attempts=3,
                backoff_seconds=5,
            ),
            FailureType.RATE_LIMIT: RecoveryAction(
                name="wait_and_retry",
                description="Wait and retry",
                action_type="retry",
                max_attempts=5,
                backoff_seconds=60,
            ),
            FailureType.NETWORK_ERROR: RecoveryAction(
                name="retry",
                description="Retry connection",
                action_type="retry",
                max_attempts=5,
                backoff_seconds=10,
            ),
            FailureType.UNKNOWN: RecoveryAction(
                name="escalate",
                description="Escalate to user for manual intervention",
                action_type="escalate",
                max_attempts=1,
            ),
        }

        return default_actions.get(
            failure_type,
            RecoveryAction(
                name="analyze_and_fix",
                description="Analyze error and attempt fix",
                action_type="fix",
                max_attempts=3,
            ),
        )

    def record_failure(
        self,
        failure_type: FailureType,
        message: str,
        context: str,
    ) -> FailureRecord:
        """
        Record a failure for tracking and analysis.

        Args:
            failure_type: Type of failure
            message: Error message
            context: Context where failure occurred

        Returns:
            FailureRecord for the failure
        """
        recovery_action = self.get_recovery_action(failure_type, message)
        record = FailureRecord(
            failure_type=failure_type,
            message=message,
            context=context,
            recovery_action=recovery_action,
        )
        self.failure_history.append(record)

        # Update stats
        type_key = failure_type.value
        if type_key not in self.recovery_stats:
            self.recovery_stats[type_key] = {"total": 0, "recovered": 0}
        self.recovery_stats[type_key]["total"] += 1

        return record

    def mark_recovered(self, record: FailureRecord) -> None:
        """Mark a failure as recovered."""
        record.recovered = True
        type_key = record.failure_type.value
        if type_key in self.recovery_stats:
            self.recovery_stats[type_key]["recovered"] += 1

    def get_recovery_rate(self) -> float:
        """Get overall recovery rate."""
        total = sum(s["total"] for s in self.recovery_stats.values())
        recovered = sum(s["recovered"] for s in self.recovery_stats.values())
        return recovered / total if total > 0 else 0.0

    def get_stats(self) -> dict[str, Any]:
        """Get failure recovery statistics."""
        return {
            "total_failures": len(self.failure_history),
            "recovery_rate": self.get_recovery_rate(),
            "by_type": self.recovery_stats,
            "recent_failures": [f.to_dict() for f in self.failure_history[-10:]],
        }

    def suggest_fix(self, failure_type: FailureType, error_message: str) -> str:
        """
        Suggest a fix based on failure type and error message.

        Args:
            failure_type: Type of failure
            error_message: The error message

        Returns:
            Suggested fix as a string
        """
        suggestions = {
            FailureType.SYNTAX_ERROR: f"Parse the syntax error location from: {error_message}\nFix the syntax at the indicated line.",
            FailureType.IMPORT_ERROR: f"Install missing module or fix import path.\nError: {error_message}",
            FailureType.TYPE_ERROR: f"Check type annotations and fix type mismatch.\nError: {error_message}",
            FailureType.TEST_FAILURE: f"Analyze test failure and fix the code or test.\nError: {error_message}",
            FailureType.LINT_ERROR: f"Run 'ruff check --fix' or manually fix lint errors.\nError: {error_message}",
            FailureType.MERGE_CONFLICT: "Resolve merge conflicts by choosing the correct version of conflicting code.",
            FailureType.PUSH_REJECTED: "Pull latest changes with 'git pull --rebase' and resolve any conflicts.",
        }

        return suggestions.get(
            failure_type,
            f"Analyze the error and determine appropriate fix.\nError: {error_message}",
        )
