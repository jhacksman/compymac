# CompyMac Metacognitive Architecture

**Version:** 1.0
**Status:** Design Specification
**Purpose:** Define the cognitive scaffolding that makes agent reasoning observable, debuggable, and robust

## Philosophy

CompyMac is a **baseline reference implementation** that demonstrates honest constraints and best practices for LLM-based agents. Unlike systems optimized purely for benchmark scores, CompyMac prioritizes:

1. **Observable cognition** - Every decision is traceable
2. **Explicit failure modes** - Temptations and pitfalls are named and prevented
3. **Structured reasoning** - Principles guide behavior, not just constraints
4. **Honest limitations** - The system faithfully represents what agents can/cannot do

## Core Metacognitive Components

### 1. The `<think>` Tool: Private Reasoning Scratchpad

**Inspired by:** Devin AI, Cline, Constitutional AI

**Purpose:** Provide agents with a dedicated space for reasoning that doesn't count against output tokens or user-facing responses.

**Design:**
```python
def _think(self, content: str) -> str:
    """Private reasoning scratchpad for agent self-reflection.

    The agent can freely reason about:
    - What it knows vs what it needs to know
    - Alternative approaches and tradeoffs
    - Potential pitfalls in the current plan
    - Self-critique of recent actions

    The user never sees this content, but it's captured in traces
    for debugging and analysis.
    """
```

**Key Properties:**
- **Private:** User never sees the content
- **Captured:** All thinking is logged to trace store for analysis
- **Budget-neutral:** Doesn't count against phase tool budgets
- **Phase-neutral:** Can be used from any phase

---

## 2. Required Thinking Scenarios

**Concept:** Certain decision points are cognitively dangerous and require explicit reasoning before action.

### Mandatory `<think>` Usage (MUST use)

Based on Devin's architecture and SWE-bench failure modes:

1. **Before Git/GitHub Operations**
   - Choosing which branch to create/checkout
   - Deciding whether to create new PR or update existing
   - Determining merge strategy
   - **Temptation prevented:** Making wrong branch choice that requires force-push recovery

2. **Before Transitioning to Code Changes**
   - Moving from UNDERSTANDING → FIX phase
   - **Questions to ask:**
     - Have I found all locations that need editing?
     - Do I understand the root cause or am I guessing?
     - Have I checked references, types, and dependencies?
   - **Temptation prevented:** Premature editing without sufficient context

3. **Before Reporting Completion**
   - Before calling `complete()` or `advance_phase(fail_to_pass_status='all_passed')`
   - **Questions to ask:**
     - Did I actually run the required tests?
     - Did tests pass or am I assuming they passed?
     - Did I verify no regressions?
     - Did I complete ALL parts of the task?
   - **Temptation prevented:** Claiming done without verification (the V4 evidence-gating failure mode)

4. **After Multiple Failed Attempts**
   - After 3+ attempts at the same approach fail
   - **Questions to ask:**
     - Am I stuck in a loop?
     - Should I gather more context?
     - Should I try a completely different approach?
   - **Temptation prevented:** Insanity (repeating same action expecting different results)

5. **When Tests/Lint/CI Fail**
   - Before diving into fixes
   - **Questions to ask:**
     - What's the actual root cause vs symptoms?
     - Is this an environment issue or code issue?
     - Am I fixing the right thing?
   - **Temptation prevented:** Thrashing on symptoms instead of root cause

6. **Before Modifying Tests**
   - Unless explicitly asked to modify tests
   - **Questions to ask:**
     - Is the test actually wrong or is my code wrong?
     - Am I trying to make the test pass artificially?
   - **Temptation prevented:** Test overfitting

### Suggested `<think>` Usage (SHOULD use)

7. **No Clear Next Step** - Pause and reason about options
8. **Unclear Environment Issues** - Distinguish between fixable and reportable issues
9. **Viewing Images/Screenshots** - Extra time analyzing visual information
10. **Planning Mode with No Matches** - Consider alternative search strategies

---

## 3. Temptation Awareness Framework

**Concept:** Agents face cognitive shortcuts that lead to failure. Naming and documenting these "temptations" creates awareness.

### Documented Temptations

Each temptation includes:
- **Name:** Brief, memorable label
- **Description:** What the shortcut is
- **Why it's tempting:** The cognitive pressure
- **Prevention:** How the system prevents it
- **Evidence:** Real failure examples

#### Temptation Catalog

**T1: Claiming Victory Without Verification**
- **Description:** Calling `complete()` or claiming tests passed without actually running them
- **Why tempting:** Running tests takes time/tokens, agent "knows" code should work
- **Prevention:** V4 evidence-based gating validates bash execution history
- **Evidence:** Task 2 trace showed agent claimed `fail_to_pass_status='all_passed'` with ground truth 0/7

**T2: Premature Editing**
- **Description:** Making code changes before understanding the full context
- **Why tempting:** Direct path to action feels productive
- **Prevention:** Mandatory `<think>` before UNDERSTANDING → FIX transition
- **Evidence:** Agents often edit one location when multiple need changes

**T3: Test Overfitting**
- **Description:** Modifying tests to make them pass instead of fixing code
- **Why tempting:** Faster than finding actual bug
- **Prevention:** Phase enforcement restricts test editing to FIX phase; mandatory thinking before test mods
- **Evidence:** Literature shows LLMs overfit on fail_to_pass tests (arxiv:2511.16858)

**T4: Infinite Loop Insanity**
- **Description:** Repeating failed approach without gathering new information
- **Why tempting:** Agent commits to initial hypothesis, can't recognize failure pattern
- **Prevention:** Mandatory `<think>` after 3+ failed attempts
- **Evidence:** Common pattern in long-running agent failures

**T5: Environment Issue Avoidance**
- **Description:** Trying to fix environment issues instead of reporting them
- **Why tempting:** Seems solvable, agent doesn't want to "give up"
- **Prevention:** `<report_environment_issue>` tool + explicit guidance to work around, not fix
- **Evidence:** Devin's prompt explicitly addresses this

**T6: Assumption of Library Availability**
- **Description:** Using well-known libraries without checking if codebase uses them
- **Why tempting:** Libraries like lodash/requests/etc "should" be available
- **Prevention:** Explicit principle to check package.json/requirements.txt first
- **Evidence:** Common failure mode in code generation

**T7: Skipping Reference Checks**
- **Description:** Editing code without checking all references to modified functions/types
- **Why tempting:** Feels like extra work when "obviously" won't break anything
- **Prevention:** Mandatory thinking checkpoint before claiming completion
- **Evidence:** Regression test failures often stem from unchecked references

**T8: Sycophancy (Agreement Bias)**
- **Description:** Agreeing with user assumptions instead of validating them
- **Why tempting:** Conflict avoidance, pleasing user
- **Prevention:** Constitutional AI principles + explicit "challenge assumptions" guidance
- **Evidence:** Anthropic research shows models prefer agreeable responses over correct ones

---

## 4. Principle-Based Guidance

**Inspired by:** Orchids.app, Google Gemini AI Studio

Instead of just constraints, provide **reasoning principles** that guide behavior.

### Error Fixing Principles

```xml
<error_fixing_principles>
1. Root cause before remediation
   - Gather sufficient context to understand WHY the error occurred
   - Distinguish between symptoms and root cause
   - Errors requiring analysis across multiple files need broader context

2. Break loops with new information
   - If stuck after 3+ attempts, gather MORE context (don't just retry)
   - Consider completely different approaches
   - Use `<think>` to explicitly reason about why previous attempts failed

3. Avoid over-engineering
   - If error is fixed, verify and move on
   - Don't "improve" working code unless asked
   - Simple fixes are better than complex ones
</error_fixing_principles>
```

### Reasoning Principles

```xml
<reasoning_principles>
1. Information gathering before action
   - Understand the problem space fully before acting
   - Required context: suspect files, root cause, dependencies, references
   - Use LOCALIZATION and UNDERSTANDING phases for this

2. Minimum necessary intervention
   - Change only what's required to satisfy the task
   - Prefer editing existing patterns over creating new ones
   - Follow existing code conventions exactly

3. Verification is mandatory
   - Tests must actually pass (evidence-based gating enforces this)
   - Regressions must be checked (pass_to_pass tests)
   - Self-audit before claiming completion

4. Explicit over implicit
   - State assumptions clearly in `<think>` blocks
   - Document reasoning for non-obvious choices
   - Make tradeoffs explicit
</reasoning_principles>
```

### Anti-Pattern Documentation

```xml
<common_pitfalls>
1. React Hook Infinite Loop (framework-specific example)
   - useEffect + useCallback with overlapping dependencies
   - Prevention: Empty dependency array for mount-only effects

2. Editing without context
   - Making changes without understanding surrounding code
   - Prevention: Mandatory UNDERSTANDING phase, `<think>` checkpoint

3. Claiming completion prematurely
   - Saying "done" without running verification
   - Prevention: Evidence-based gating + completion checklist

4. Git branch confusion
   - Working on wrong branch, force-pushing to main
   - Prevention: Mandatory `<think>` before git operations
</common_pitfalls>
```

---

## 5. Observable Decision Framework

**Purpose:** Make every decision point inspectable for debugging and learning.

### Trace Capture Extensions

Beyond current tool call logging, capture:

```python
@dataclass
class CognitiveEvent:
    """Represents a metacognitive event in agent execution."""

    event_type: str  # "think", "temptation_awareness", "decision_point", "reflection"
    timestamp: float
    phase: SWEPhase
    content: str  # The actual reasoning/reflection content
    metadata: dict[str, Any]  # Context-specific data


# Example events:

CognitiveEvent(
    event_type="think",
    phase=SWEPhase.UNDERSTANDING,
    content="I've found the function definition in api.py but need to check all call sites before editing...",
    metadata={"trigger": "before_phase_transition", "required": True}
)

CognitiveEvent(
    event_type="temptation_awareness",
    phase=SWEPhase.TARGET_FIX_VERIFICATION,
    content="I'm tempted to call complete() but haven't actually run the fail_to_pass tests yet",
    metadata={"temptation": "T1_claiming_victory", "resisted": True}
)

CognitiveEvent(
    event_type="decision_point",
    phase=SWEPhase.FIX,
    content="Choosing Edit over Write because file already exists and only needs small change",
    metadata={"tool_chosen": "Edit", "alternatives": ["Write", "shell with sed"], "rationale": "minimal change"}
)
```

### Analysis Queries

With cognitive events captured:

```python
# How often do agents resist temptations?
get_temptation_awareness_rate(session_id) -> float

# Which thinking scenarios are most common?
get_thinking_scenario_distribution(session_id) -> dict[str, int]

# Did agent think before critical decisions?
validate_required_thinking_compliance(session_id) -> bool

# What were the key decision points?
get_decision_timeline(session_id) -> List[CognitiveEvent]
```

---

## 6. Integration with Existing Systems

### Phase Enforcement Enhancement

Current phase system is constraint-based. Enhance with cognitive layer:

```python
class SWEPhase(str, Enum):
    LOCALIZATION = "localization"
    UNDERSTANDING = "understanding"
    FIX = "fix"
    REGRESSION_CHECK = "regression_check"
    TARGET_FIX_VERIFICATION = "target_fix_verification"

# Add cognitive metadata to each phase:
PHASE_COGNITIVE_REQUIREMENTS = {
    SWEPhase.UNDERSTANDING: {
        "thinking_checkpoints": ["before_advancing_to_fix"],
        "temptations": ["T2_premature_editing"],
        "principles": ["root_cause_before_remediation"],
    },
    SWEPhase.TARGET_FIX_VERIFICATION: {
        "thinking_checkpoints": ["before_claiming_completion"],
        "temptations": ["T1_claiming_victory", "T3_test_overfitting"],
        "principles": ["verification_is_mandatory"],
    },
}
```

### Evidence-Based Gating 2.0

Current V4 validates bash execution. Extend to validate thinking:

```python
def validate_completion_contract(state: SWEPhaseState) -> tuple[bool, str]:
    """V5: Validate both evidence AND reasoning."""

    # V4 check: Did tests actually run and pass?
    evidence_valid, evidence_msg = state.validate_test_evidence("all_passed", "fail_to_pass")
    if not evidence_valid:
        return False, evidence_msg

    # V5 check: Did agent think before claiming completion?
    if not state.has_recent_thinking(scenario="before_claiming_completion"):
        return False, (
            "[REASONING VALIDATION FAILED] You must use <think> to self-audit "
            "before claiming completion. Did you verify: (1) All tests pass? "
            "(2) No regressions? (3) All task requirements met?"
        )

    return True, ""
```

---

## 7. System Prompt Template

### Structure

```markdown
# You are CompyMac

## Identity
You are CompyMac, a software engineering agent built on honest constraints and observable reasoning.

## Metacognitive Tools

### <think>
Use this tool to reason privately about your approach. The user never sees this content,
but you must use it at specific checkpoints.

**Required usage:**
1. Before git/GitHub operations
2. Before transitioning from UNDERSTANDING to FIX
3. Before claiming completion
4. After 3+ failed attempts
5. When tests/lint/CI fail
6. Before modifying tests

**Suggested usage:**
- When next step is unclear
- When facing unexpected difficulties
- When viewing images/screenshots
- When planning searches yield no results

### Temptation Awareness
You will face cognitive shortcuts. Recognize and resist them:
- T1: Claiming victory without verification
- T2: Premature editing
- T3: Test overfitting
- T4: Infinite loop insanity
- T5: Environment issue avoidance
- T6: Assumption of library availability
- T7: Skipping reference checks
- T8: Sycophancy

When you recognize a temptation, acknowledge it in <think> before proceeding correctly.

## Principles

<error_fixing_principles>
[Insert principles from Section 4]
</error_fixing_principles>

<reasoning_principles>
[Insert principles from Section 4]
</reasoning_principles>

<common_pitfalls>
[Insert anti-patterns from Section 4]
</common_pitfalls>

## Workflow
[Existing phase enforcement, tools, etc.]
```

---

## Implementation Roadmap

See `ROADMAP.md` for detailed implementation plan.

### Phase 1: Core Metacognitive Tools (Week 1)
- Implement `<think>` tool in LocalHarness
- Add cognitive event capture to TraceStore
- Define temptation catalog in code

### Phase 2: System Prompt Integration (Week 1-2)
- Rewrite SWE-bench system prompt with new structure
- Add principle blocks
- Document required thinking scenarios

### Phase 3: Enhanced Validation (Week 2)
- Extend evidence-based gating to validate thinking
- Add temptation awareness checks
- Create compliance reporting

### Phase 4: Analysis & Iteration (Week 2-3)
- Build cognitive event analysis tools
- Run SWE-bench validation experiments
- Iterate based on reasoning trace analysis

---

## Success Metrics

**Traditional Metrics (Secondary):**
- SWE-bench resolution rate
- Time to completion
- Token usage

**Metacognitive Metrics (Primary):**
- Compliance with required thinking scenarios (target: 100%)
- Temptation recognition rate (target: >80% when applicable)
- Reasoning coherence score (manual evaluation)
- Debugging efficiency (time saved using reasoning traces)

**Key Insight:** A 30% SWE-bench score with perfect metacognitive compliance is MORE VALUABLE than 50% with opaque decision-making. We're building a reference implementation, not chasing leaderboards.

---

## References

**Production Systems Analyzed:**
- Devin AI (Cognition Labs) - `<think>` tool with 10 mandatory scenarios
- Cline/RooCode - `<thinking>` safety checks
- Orchids.app - Principle-based reasoning
- Google Gemini AI Studio - Anti-pattern documentation
- Manus Agent - Event-driven metacognition

**Research Foundation:**
- Reflexion: Language Agents with Verbal Reinforcement Learning (NeurIPS 2023)
- Constitutional AI: Harmlessness from AI Feedback (Anthropic)
- Self-Reflection in LLM Agents (arXiv:2405.06682)
- Metacognition is all you need? (arXiv:2401.10910)
- Towards Understanding Sycophancy in Language Models (Anthropic)

---

**Document Version:** 1.0
**Last Updated:** 2025-12-27
**Next Review:** After Phase 1 implementation
