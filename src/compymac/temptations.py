"""Temptation Awareness Framework for Metacognitive Architecture (V5).

This module defines the cognitive shortcuts that agents are tempted to take,
along with their descriptions, prevention strategies, and evidence.

Naming and documenting these "temptations" creates awareness and enables
the system to detect and prevent them.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any


class Temptation(Enum):
    """Enumeration of documented cognitive shortcuts that lead to failure.

    Each temptation represents a pattern where agents take shortcuts
    that seem efficient but lead to incorrect results.
    """

    CLAIMING_VICTORY = "T1_claiming_victory"
    PREMATURE_EDITING = "T2_premature_editing"
    TEST_OVERFITTING = "T3_test_overfitting"
    INFINITE_LOOP = "T4_infinite_loop"
    ENVIRONMENT_FIXING = "T5_environment_fixing"
    LIBRARY_ASSUMPTION = "T6_library_assumption"
    SKIPPING_REFERENCES = "T7_skipping_references"
    SYCOPHANCY = "T8_sycophancy"


@dataclass
class TemptationDefinition:
    """Complete definition of a temptation with prevention guidance.

    Attributes:
        name: Brief, memorable label for the temptation
        description: What the cognitive shortcut is
        why_tempting: The cognitive pressure that makes this tempting
        prevention: How the system prevents this temptation
        evidence: Real failure examples demonstrating this pattern
    """

    name: str
    description: str
    why_tempting: str
    prevention: str
    evidence: str

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "name": self.name,
            "description": self.description,
            "why_tempting": self.why_tempting,
            "prevention": self.prevention,
            "evidence": self.evidence,
        }


TEMPTATION_CATALOG: dict[Temptation, TemptationDefinition] = {
    Temptation.CLAIMING_VICTORY: TemptationDefinition(
        name="Claiming Victory Without Verification",
        description="Calling complete() or claiming tests passed without actually running them",
        why_tempting="Running tests takes time/tokens, agent 'knows' code should work",
        prevention="V4 evidence-based gating validates bash execution history",
        evidence="Task 2 trace showed agent claimed fail_to_pass_status='all_passed' with ground truth 0/7",
    ),
    Temptation.PREMATURE_EDITING: TemptationDefinition(
        name="Premature Editing",
        description="Making code changes before understanding the full context",
        why_tempting="Direct path to action feels productive",
        prevention="Mandatory <think> before UNDERSTANDING -> FIX transition",
        evidence="Agents often edit one location when multiple need changes",
    ),
    Temptation.TEST_OVERFITTING: TemptationDefinition(
        name="Test Overfitting",
        description="Modifying tests to make them pass instead of fixing code",
        why_tempting="Faster than finding actual bug",
        prevention="Phase enforcement restricts test editing to FIX phase; mandatory thinking before test mods",
        evidence="Literature shows LLMs overfit on fail_to_pass tests (arxiv:2511.16858)",
    ),
    Temptation.INFINITE_LOOP: TemptationDefinition(
        name="Infinite Loop Insanity",
        description="Repeating failed approach without gathering new information",
        why_tempting="Agent commits to initial hypothesis, can't recognize failure pattern",
        prevention="Mandatory <think> after 3+ failed attempts",
        evidence="Common pattern in long-running agent failures",
    ),
    Temptation.ENVIRONMENT_FIXING: TemptationDefinition(
        name="Environment Issue Avoidance",
        description="Trying to fix environment issues instead of reporting them",
        why_tempting="Seems solvable, agent doesn't want to 'give up'",
        prevention="<report_environment_issue> tool + explicit guidance to work around, not fix",
        evidence="Devin's prompt explicitly addresses this",
    ),
    Temptation.LIBRARY_ASSUMPTION: TemptationDefinition(
        name="Assumption of Library Availability",
        description="Using well-known libraries without checking if codebase uses them",
        why_tempting="Libraries like lodash/requests/etc 'should' be available",
        prevention="Explicit principle to check package.json/requirements.txt first",
        evidence="Common failure mode in code generation",
    ),
    Temptation.SKIPPING_REFERENCES: TemptationDefinition(
        name="Skipping Reference Checks",
        description="Editing code without checking all references to modified functions/types",
        why_tempting="Feels like extra work when 'obviously' won't break anything",
        prevention="Mandatory thinking checkpoint before claiming completion",
        evidence="Regression test failures often stem from unchecked references",
    ),
    Temptation.SYCOPHANCY: TemptationDefinition(
        name="Sycophancy (Agreement Bias)",
        description="Agreeing with user assumptions instead of validating them",
        why_tempting="Conflict avoidance, pleasing user",
        prevention="Constitutional AI principles + explicit 'challenge assumptions' guidance",
        evidence="Anthropic research shows models prefer agreeable responses over correct ones",
    ),
}


def get_temptation_description(temptation: Temptation) -> str:
    """Get a brief description of a temptation.

    Args:
        temptation: The temptation to describe

    Returns:
        A string in the format "Name: Description"
    """
    defn = TEMPTATION_CATALOG[temptation]
    return f"{defn.name}: {defn.description}"


def get_relevant_temptations(phase: str) -> list[Temptation]:
    """Get temptations that are particularly relevant to a given phase.

    Different phases have different cognitive pressures that make
    certain temptations more likely.

    Args:
        phase: The current SWE workflow phase (as string value)

    Returns:
        List of Temptation enums relevant to this phase
    """
    temptations_by_phase: dict[str, list[Temptation]] = {
        "LOCALIZATION": [
            Temptation.PREMATURE_EDITING,
            Temptation.LIBRARY_ASSUMPTION,
        ],
        "UNDERSTANDING": [
            Temptation.PREMATURE_EDITING,
            Temptation.SKIPPING_REFERENCES,
        ],
        "FIX": [
            Temptation.TEST_OVERFITTING,
            Temptation.INFINITE_LOOP,
            Temptation.ENVIRONMENT_FIXING,
        ],
        "REGRESSION_CHECK": [
            Temptation.CLAIMING_VICTORY,
            Temptation.TEST_OVERFITTING,
        ],
        "TARGET_FIX_VERIFICATION": [
            Temptation.CLAIMING_VICTORY,
            Temptation.SYCOPHANCY,
        ],
    }
    return temptations_by_phase.get(phase, [])
