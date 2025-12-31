# CompyMac Evaluation Framework
#
# This module provides end-to-end evaluation of CompyMac using Venice.ai.
# No mocking, no scripted tests - just real tasks solved by real LLM calls.

from compymac.evaluation.runner import EvaluationRunner, TaskResult
from compymac.evaluation.tasks import TASK_BANK, Task, TaskCategory

__all__ = [
    "EvaluationRunner",
    "TaskResult",
    "TASK_BANK",
    "Task",
    "TaskCategory",
]
