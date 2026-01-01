"""
CompyMac Workflows - Automated workflow patterns for common tasks.

This module implements:
- Gap 3: Workflow Closure (Full SWE Loop) - SWEWorkflow, FailureRecovery, CIIntegration
- Gap 4: Git PR Loop Automation - GitPRWorkflow with approval gates
- Gap 6 Phase 1: Multi-Agent Orchestration - Structured artifact handoffs between agents
- Gap 6 Phase 2: Parallel Workstreams - Merge/review with conflict detection
- Gap 6 Phase 3: Dynamic Orchestration - Capability-based routing with feedback learning

Based on arxiv research - see docs/GAP3_WORKFLOW_CLOSURE_RESEARCH.md, GAP6_MULTI_AGENT_RESEARCH.md
"""

from compymac.workflows.agent_handoffs import (
    AgentArtifactType,
    FailureAnalysis,
    FileTarget,
    HandoffManager,
    HandoffValidationStatus,
    HandoffValidator,
    PatchPlan,
    ProblemStatement,
    ReviewFeedback,
    StructuredHandoff,
    TestPlan,
)
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

# Gap 6 Phase 3: Dynamic Orchestration
from compymac.workflows.dynamic_orchestration import (
    AgentCapability,
    AgentCapabilityProfile,
    CapabilityRouter,
    DynamicOrchestrator,
    HeuristicRouter,
    RoutingDecision,
    RoutingFeedbackStore,
    RoutingHeuristic,
    RoutingOutcome,
    TaskAnalysis,
    TaskAnalyzer,
    TaskComplexity,
    TaskType,
)
from compymac.workflows.failure_recovery import (
    FailureRecord,
    FailureRecovery,
    FailureType,
    RecoveryAction,
)
from compymac.workflows.git_pr import ApprovalGate, GitPRWorkflow, WorkflowState

# Gap 6 Phase 2: Parallel Workstreams
from compymac.workflows.parallel_workstreams import (
    ConflictDetector,
    ConflictReport,
    ConflictType,
    EnhancedWorkspaceMerger,
    FileConflict,
    MergeStrategy,
    ParallelWorkstreamOrchestrator,
    ResolutionStrategy,
    ReviewerArbiter,
    StructuredHypothesisResult,
)

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
    # Gap 6 Phase 1: Multi-Agent Handoffs
    "AgentArtifactType",
    "HandoffValidationStatus",
    "ProblemStatement",
    "FileTarget",
    "PatchPlan",
    "TestPlan",
    "FailureAnalysis",
    "ReviewFeedback",
    "StructuredHandoff",
    "HandoffValidator",
    "HandoffManager",
    # Gap 6 Phase 2: Parallel Workstreams
    "MergeStrategy",
    "ConflictType",
    "ResolutionStrategy",
    "FileConflict",
    "ConflictReport",
    "StructuredHypothesisResult",
    "ConflictDetector",
    "EnhancedWorkspaceMerger",
    "ReviewerArbiter",
    "ParallelWorkstreamOrchestrator",
    # Gap 6 Phase 3: Dynamic Orchestration
    "AgentCapability",
    "TaskType",
    "TaskComplexity",
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
]
