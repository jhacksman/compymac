"""
CompyMac Workflows - Automated workflow patterns for common tasks.

This module implements Gap 4: Git PR Loop Automation by providing
workflow classes that orchestrate multi-step operations with approval gates.
"""

from compymac.workflows.git_pr import GitPRWorkflow, ApprovalGate, WorkflowState

__all__ = ["GitPRWorkflow", "ApprovalGate", "WorkflowState"]
