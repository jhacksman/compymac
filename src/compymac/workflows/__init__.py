"""
CompyMac Workflows - Automated workflow patterns for common tasks.

This module implements:
- Gap 3: Workflow Closure (Full SWE Loop) - SWEWorkflow, FailureRecovery, CIIntegration
- Gap 4: Git PR Loop Automation - GitPRWorkflow with approval gates

Based on arxiv research - see docs/GAP3_WORKFLOW_CLOSURE_RESEARCH.md
"""

from compymac.workflows.artifact_store import (
    Artifact,
    ArtifactStore,
    ArtifactType,
)
from compymac.workflows.ci_integration import (
    CICheckResult,
    CIError,
    CIErrorType,
    CIIntegration,
    CIStatus,
    Fix,
)
from compymac.workflows.failure_recovery import (
    FailureRecord,
    FailureRecovery,
    FailureType,
    RecoveryAction,
)
from compymac.workflows.git_pr import ApprovalGate, GitPRWorkflow, WorkflowState

# Gap 3: SWE Loop components
from compymac.workflows.swe_loop import (
    StageResult,
    SWEWorkflow,
    WorkflowStage,
    WorkflowStatus,
)

__all__ = [
    # Gap 4: Git PR workflow
    "GitPRWorkflow",
    "ApprovalGate",
    "WorkflowState",
    # Gap 3: SWE Loop
    "SWEWorkflow",
    "WorkflowStage",
    "WorkflowStatus",
    "StageResult",
    # Gap 3: Failure Recovery
    "FailureRecovery",
    "FailureType",
    "RecoveryAction",
    "FailureRecord",
    # Gap 3: CI Integration
    "CIIntegration",
    "CIStatus",
    "CIError",
    "CIErrorType",
    "CICheckResult",
    "Fix",
    # Gap 3: Artifact Store
    "ArtifactStore",
    "Artifact",
    "ArtifactType",
]
