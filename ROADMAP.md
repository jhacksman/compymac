# CompyMac Development Roadmap

**Vision:** Build a baseline reference implementation for LLM agents with observable, debuggable cognition

**Status:** Transitioning from tactical SWE-bench optimization to principled architecture

**Priority:** Metacognitive scaffolding > Benchmark scores

---

## Context: Where We Are

### Completed Work (V1-V4)

**V1: Initial Phase Enforcement**
- Basic SWE workflow phases (LOCALIZATION → UNDERSTANDING → FIX → VERIFICATION)
- Phase-based tool restrictions and budgets
- Foundation for structured agent behavior

**V2: Regression-Aware Verification**
- Split verification into REGRESSION_CHECK and TARGET_FIX_VERIFICATION
- Separate pass_to_pass vs fail_to_pass test tracking
- Addressed test overfitting problem (arxiv:2511.16858)

**V3: Natural Workflow Completion**
- Merged COMPLETE phase into TARGET_FIX_VERIFICATION
- Agent calls `complete()` directly when tests pass
- Eliminated awkward extra phase transition

**V4: Evidence-Based Gating** ✅ **JUST COMPLETED**
- Prevents claiming `fail_to_pass_status='all_passed'` without proof
- Validates bash execution history (command, exit_code, timestamp)
- Ensures tests run AFTER last code edit
- **Validated on real SWE-bench tasks:** 1/3 resolution (pylint passed, no false positives)

### Current Limitations

Despite V1-V4 progress, CompyMac lacks:
1. **Metacognitive scaffolding** - No `<think>` or reflection tools
2. **Temptation awareness** - Failure modes not explicitly documented
3. **Principle-based guidance** - Only constraints, no reasoning principles
4. **Observable decisions** - Can't inspect WHY agent chose action X over Y
5. **Production-grade prompts** - Missing patterns from Devin, Cline, etc.

**Key Gap:** Production agents like Devin have 10+ mandatory thinking scenarios. CompyMac has zero.

---

## Strategic Shift

### Old Mindset ❌
"Agent failed on task X → add constraint Y → test again"

### New Mindset ✅
"What cognitive architecture would prevent failure mode X? → implement metacognitive scaffolding → validate on task X → analyze reasoning traces"

### Success Metrics Reordering

**Primary (Cognitive Quality):**
- Compliance with required thinking scenarios: 100%
- Temptation recognition rate: >80% when applicable
- Reasoning trace coherence: Manual evaluation score >7/10
- Debugging efficiency: <30min to diagnose failure with reasoning traces

**Secondary (Task Performance):**
- SWE-bench resolution rate
- Time to completion
- Token usage

**Philosophy:** 30% SWE-bench score with perfect metacognitive compliance > 50% with opaque reasoning

---

## Phase 1: Core Metacognitive Tools (Priority 1 - Start Here)

**Goal:** Implement the foundational cognitive infrastructure

**Owner:** Devin (next session)
**Duration:** 2-3 days
**Deliverables:**
- ✅ `<think>` tool in LocalHarness
- ✅ CognitiveEvent dataclass and trace capture
- ✅ Temptation catalog as code
- ✅ Required thinking scenario enforcement

### Tasks

#### 1.1 Implement `<think>` Tool

**File:** `src/compymac/local_harness.py`

Add new tool:
```python
def _think(self, content: str) -> str:
    """Private reasoning scratchpad for agent self-reflection.

    Args:
        content: The agent's reasoning (not shown to user)

    Returns:
        Confirmation message (brief, user never sees the actual content)
    """
    import logging
    logger = logging.getLogger(__name__)

    # Log the thinking content (will be captured in traces)
    logger.info(f"[THINK] {content[:100]}...")

    # Capture as cognitive event
    if self._trace_context:
        from compymac.trace_store import CognitiveEvent
        import time

        event = CognitiveEvent(
            event_type="think",
            timestamp=time.time(),
            phase=self._swe_phase_state.current_phase if self._swe_phase_state else None,
            content=content,
            metadata={"trigger": self._last_thinking_trigger or "voluntary"}
        )
        self._trace_context.add_cognitive_event(event)

    # Track that thinking occurred (for compliance validation)
    if self._swe_phase_enabled and self._swe_phase_state:
        self._swe_phase_state.record_thinking(content, trigger=self._last_thinking_trigger)
        self._last_thinking_trigger = None  # Reset

    return "Reasoning recorded. Proceed with next action."
```

Register tool:
```python
self.register_tool(
    schema=ToolSchema(
        name="think",
        description=(
            "Private reasoning scratchpad. Use this to reason about your approach, "
            "weigh alternatives, and self-critique. Required before critical decisions. "
            "The user never sees this content."
        ),
        required_params=["content"],
        optional_params=[],
        param_info={
            "content": "Your reasoning, reflections, and analysis",
        },
    ),
    handler=self._think,
    category=ToolCategory.CORE,
    is_core=True,
)
```

**Acceptance criteria:**
- `_think()` method exists and works
- Tool registered in BUDGET_NEUTRAL_TOOLS
- Tool registered in PHASE_NEUTRAL_TOOLS
- Thinking content captured in trace store
- User never sees thinking content (only confirmation message)

---

#### 1.2 Extend SWEPhaseState for Thinking Tracking

**File:** `src/compymac/swe_workflow.py`

Add to `SWEPhaseState` dataclass:
```python
@dataclass
class SWEPhaseState:
    # ... existing fields ...

    # V5: Metacognitive tracking
    thinking_events: list[dict[str, Any]] = field(default_factory=list)  # {content, trigger, timestamp}
    last_thinking_scenario: str = ""  # Most recent required scenario that triggered thinking

    def record_thinking(self, content: str, trigger: str | None = None, timestamp: float | None = None) -> None:
        """Record a thinking event for metacognitive compliance validation."""
        import time
        self.thinking_events.append({
            "content": content,
            "trigger": trigger or "voluntary",
            "timestamp": timestamp or time.time(),
        })
        if trigger:
            self.last_thinking_scenario = trigger

    def has_recent_thinking(self, scenario: str, within_seconds: float = 300) -> bool:
        """Check if agent has thought about a specific scenario recently."""
        import time
        cutoff = time.time() - within_seconds
        return any(
            event["trigger"] == scenario and event["timestamp"] > cutoff
            for event in self.thinking_events
        )

    def get_thinking_compliance_rate(self) -> float:
        """Calculate what % of required thinking scenarios were satisfied."""
        required_scenarios = get_required_thinking_scenarios(self.current_phase)
        if not required_scenarios:
            return 1.0

        satisfied = sum(
            1 for scenario in required_scenarios
            if self.has_recent_thinking(scenario)
        )
        return satisfied / len(required_scenarios)
```

Add helper:
```python
def get_required_thinking_scenarios(phase: SWEPhase) -> list[str]:
    """Get list of required thinking scenarios for a phase."""
    scenarios_by_phase = {
        SWEPhase.UNDERSTANDING: ["before_advancing_to_fix"],
        SWEPhase.FIX: ["before_git_operations"],
        SWEPhase.TARGET_FIX_VERIFICATION: ["before_claiming_completion"],
    }
    return scenarios_by_phase.get(phase, [])
```

**Acceptance criteria:**
- Thinking events tracked in SWEPhaseState
- Can validate if required thinking occurred
- Compliance rate calculable

---

#### 1.3 Create CognitiveEvent in Trace Store

**File:** `src/compymac/trace_store.py`

Add dataclass:
```python
@dataclass
class CognitiveEvent:
    """Represents a metacognitive event (thinking, temptation awareness, decision)."""

    event_type: str  # "think", "temptation_awareness", "decision_point", "reflection"
    timestamp: float
    phase: SWEPhase | None
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_type": self.event_type,
            "timestamp": self.timestamp,
            "phase": self.phase.value if self.phase else None,
            "content": self.content,
            "metadata": self.metadata,
        }
```

Extend `TraceContext`:
```python
class TraceContext:
    # ... existing methods ...

    def add_cognitive_event(self, event: CognitiveEvent) -> None:
        """Record a cognitive event (thinking, temptation awareness, etc.)."""
        if self.trace_store:
            self.trace_store.store_cognitive_event(self.trace_id, event)
```

Extend `TraceStore`:
```python
class TraceStore:
    # ... existing methods ...

    def store_cognitive_event(self, trace_id: str, event: CognitiveEvent) -> None:
        """Store a cognitive event."""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            INSERT INTO cognitive_events (trace_id, event_type, timestamp, phase, content, metadata)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                trace_id,
                event.event_type,
                event.timestamp,
                event.phase.value if event.phase else None,
                event.content,
                json.dumps(event.metadata),
            ),
        )
        self.conn.commit()

    def get_cognitive_events(self, trace_id: str) -> list[CognitiveEvent]:
        """Retrieve all cognitive events for a trace."""
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT event_type, timestamp, phase, content, metadata FROM cognitive_events WHERE trace_id = ? ORDER BY timestamp",
            (trace_id,),
        )
        events = []
        for row in cursor.fetchall():
            events.append(
                CognitiveEvent(
                    event_type=row[0],
                    timestamp=row[1],
                    phase=SWEPhase(row[2]) if row[2] else None,
                    content=row[3],
                    metadata=json.loads(row[4]),
                )
            )
        return events
```

Add schema migration:
```python
def _initialize_schema(self):
    # ... existing tables ...

    # Cognitive events table
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS cognitive_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trace_id TEXT NOT NULL,
            event_type TEXT NOT NULL,
            timestamp REAL NOT NULL,
            phase TEXT,
            content TEXT NOT NULL,
            metadata TEXT,
            FOREIGN KEY (trace_id) REFERENCES traces(trace_id)
        )
        """
    )
```

**Acceptance criteria:**
- CognitiveEvent dataclass exists
- Trace store can save/retrieve cognitive events
- Database schema supports cognitive events

---

#### 1.4 Define Temptation Catalog

**File:** `src/compymac/temptations.py` (new file)

Create enumeration and documentation:
```python
"""Temptation catalog - cognitive shortcuts that lead to agent failure."""

from enum import Enum
from dataclasses import dataclass


class Temptation(str, Enum):
    """Known cognitive shortcuts that agents are tempted to take."""

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
    """Documentation for a specific temptation."""

    name: str
    description: str
    why_tempting: str
    prevention: str
    evidence: str


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
        prevention="Mandatory <think> before UNDERSTANDING → FIX transition",
        evidence="Agents often edit one location when multiple need changes",
    ),
    # ... add remaining 6 temptations ...
}


def get_temptation_description(temptation: Temptation) -> str:
    """Get human-readable description of a temptation."""
    defn = TEMPTATION_CATALOG[temptation]
    return f"{defn.name}: {defn.description}"


def get_relevant_temptations(phase: "SWEPhase") -> list[Temptation]:
    """Get temptations relevant to a specific phase."""
    from compymac.swe_workflow import SWEPhase

    temptations_by_phase = {
        SWEPhase.UNDERSTANDING: [Temptation.PREMATURE_EDITING],
        SWEPhase.FIX: [Temptation.LIBRARY_ASSUMPTION, Temptation.SKIPPING_REFERENCES],
        SWEPhase.REGRESSION_CHECK: [Temptation.TEST_OVERFITTING],
        SWEPhase.TARGET_FIX_VERIFICATION: [Temptation.CLAIMING_VICTORY, Temptation.TEST_OVERFITTING],
    }
    return temptations_by_phase.get(phase, [])
```

**Acceptance criteria:**
- All 8 temptations documented
- Helper functions for retrieving temptation info
- Can map phases to relevant temptations

---

### Phase 1 Validation

Before moving to Phase 2, verify:
- [ ] `think` tool works (call it manually, check trace store)
- [ ] Thinking events recorded in SWEPhaseState
- [ ] CognitiveEvent table in SQLite has data
- [ ] Temptation catalog complete and importable
- [ ] Run `pytest tests/` - all existing tests still pass

---

## Phase 2: System Prompt Integration (Priority 2)

**Goal:** Rewrite agent prompts with metacognitive scaffolding

**Owner:** Devin
**Duration:** 1-2 days
**Deliverables:**
- ✅ New SWE-bench system prompt with `<think>` guidance
- ✅ Principle blocks integrated
- ✅ Required thinking scenarios documented in prompt
- ✅ Temptation awareness guidance

### Tasks

#### 2.1 Create Enhanced System Prompt Template

**File:** `src/compymac/prompts/swe_bench_v5.md` (new file)

Structure:
```markdown
# You are CompyMac - Software Engineering Agent

[Use template from METACOGNITIVE_ARCHITECTURE.md Section 7]

Key sections:
1. Identity and philosophy
2. Metacognitive tools (<think>, temptation awareness)
3. Required thinking scenarios (10 scenarios)
4. Principle blocks (error fixing, reasoning, anti-patterns)
5. Phase-based workflow
6. Tool reference
```

**Acceptance criteria:**
- Prompt includes all 10 thinking scenarios
- Temptations T1-T8 documented
- Principles from architecture doc integrated
- Clear, actionable language (not vague)

---

#### 2.2 Integrate Prompt into SWE-bench Runner

**File:** `src/compymac/swe_bench.py`

Update `SWEBenchRunner` to use new prompt:
```python
def _build_system_prompt(self, task: SWEBenchTask) -> str:
    """Build system prompt with metacognitive scaffolding."""
    from pathlib import Path

    # Load V5 prompt template
    prompt_file = Path(__file__).parent / "prompts" / "swe_bench_v5.md"
    template = prompt_file.read_text()

    # Inject task-specific context
    prompt = template.format(
        instance_id=task.instance_id,
        problem_statement=task.problem_statement,
        repo_path=str(self.workspace_path),
        # ... other context ...
    )

    return prompt
```

**Acceptance criteria:**
- New prompt loaded correctly
- Task-specific context injected
- Agent receives V5 prompt during SWE-bench runs

---

#### 2.3 Add Thinking Trigger System

**File:** `src/compymac/local_harness.py`

Before critical operations, set thinking trigger:
```python
def _advance_phase(self, ...):
    # Before allowing UNDERSTANDING → FIX transition, require thinking
    if state.current_phase == SWEPhase.UNDERSTANDING:
        if not state.has_recent_thinking("before_advancing_to_fix", within_seconds=300):
            return (
                "[THINKING REQUIRED] Before advancing to FIX phase, you must use <think> "
                "to verify you have sufficient context. Questions to consider:\n"
                "- Have you found ALL locations that need editing?\n"
                "- Do you understand the root cause?\n"
                "- Have you checked references, types, and dependencies?"
            )

# Similar checks for other critical transitions
```

**Acceptance criteria:**
- Can't advance UNDERSTANDING → FIX without thinking
- Can't call `complete()` without thinking
- Can't do git operations without thinking (if in SWE mode)

---

### Phase 2 Validation

Before moving to Phase 3:
- [ ] New prompt renders correctly
- [ ] Thinking triggers block invalid transitions
- [ ] Agent uses `<think>` in practice (run 1-2 SWE-bench tasks)
- [ ] Reasoning captured in traces

---

## Phase 3: Enhanced Validation (Priority 3)

**Goal:** Extend evidence-based gating to validate thinking compliance

**Owner:** Devin
**Duration:** 1-2 days
**Deliverables:**
- ✅ V5 gating validates both evidence AND thinking
- ✅ Temptation awareness tracking
- ✅ Compliance reporting

### Tasks

#### 3.1 Upgrade Evidence-Based Gating to V5

**File:** `src/compymac/local_harness.py`

Enhance `_complete()` validation:
```python
def _complete(self, final_answer: str) -> str:
    # ... existing code ...

    # V4: Evidence-based gating (bash execution validation)
    if self._swe_phase_enabled and self._swe_phase_state:
        evidence_valid, evidence_msg = state.validate_test_evidence(
            "all_passed", "fail_to_pass"
        )
        if not evidence_valid:
            return f"[EVIDENCE VALIDATION FAILED] {evidence_msg}"

        # V5: Reasoning validation (thinking compliance)
        reasoning_valid, reasoning_msg = state.validate_completion_reasoning()
        if not reasoning_valid:
            return f"[REASONING VALIDATION FAILED] {reasoning_msg}"

    # Proceed with completion...
```

Add to `SWEPhaseState`:
```python
def validate_completion_reasoning(self) -> tuple[bool, str]:
    """V5: Validate agent has thought through completion checklist."""

    if not self.has_recent_thinking("before_claiming_completion", within_seconds=600):
        return False, (
            "You must use <think> to self-audit before claiming completion. "
            "Required checklist:\n"
            "1. Did tests actually pass (evidence-based gating confirmed this)?\n"
            "2. Did you check for regressions (pass_to_pass tests)?\n"
            "3. Did you complete ALL parts of the task?\n"
            "4. Did you verify all edited locations?\n\n"
            "Use <think> to verify these points, then call complete() again."
        )

    return True, ""
```

**Acceptance criteria:**
- Can't complete without both evidence AND thinking
- Error messages are clear and actionable
- V5 gating protects against false completions

---

#### 3.2 Temptation Awareness Tracking

**File:** `src/compymac/swe_workflow.py`

Add to `SWEPhaseState`:
```python
@dataclass
class SWEPhaseState:
    # ... existing fields ...

    # Temptation tracking
    temptations_encountered: list[dict[str, Any]] = field(default_factory=list)  # {temptation, recognized, resisted, timestamp}

    def record_temptation(
        self,
        temptation: Temptation,
        recognized: bool,
        resisted: bool,
        context: str = "",
    ) -> None:
        """Record when agent encounters a temptation."""
        import time
        self.temptations_encountered.append({
            "temptation": temptation.value,
            "recognized": recognized,
            "resisted": resisted,
            "context": context,
            "timestamp": time.time(),
        })

    def get_temptation_resistance_rate(self) -> float:
        """Calculate % of temptations that were resisted."""
        if not self.temptations_encountered:
            return 1.0
        resisted = sum(1 for t in self.temptations_encountered if t["resisted"])
        return resisted / len(self.temptations_encountered)
```

When agent attempts completion without evidence:
```python
# In validate_test_evidence()
if test_status == "all_passed" and not matching_test_runs:
    # Record this as encountering T1_claiming_victory temptation
    self.record_temptation(
        Temptation.CLAIMING_VICTORY,
        recognized=False,  # Agent didn't use <think> to acknowledge
        resisted=False,    # Attempted the shortcut
        context="Claimed all_passed without running tests"
    )
    return False, "..."
```

**Acceptance criteria:**
- Temptations recorded when encountered
- Can calculate resistance rate
- Data available for analysis

---

#### 3.3 Compliance Reporting

**File:** `scripts/analyze_cognitive_compliance.py` (new file)

Create analysis script:
```python
#!/usr/bin/env python3
"""Analyze metacognitive compliance from trace store."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from compymac.trace_store import TraceStore

def analyze_compliance(trace_id: str):
    """Generate compliance report for a trace."""
    store = TraceStore()

    # Get cognitive events
    events = store.get_cognitive_events(trace_id)

    thinking_events = [e for e in events if e.event_type == "think"]
    decision_events = [e for e in events if e.event_type == "decision_point"]

    print(f"Trace: {trace_id}")
    print(f"  Thinking events: {len(thinking_events)}")
    print(f"  Decision events: {len(decision_events)}")

    # Check required scenarios
    required = ["before_claiming_completion", "before_advancing_to_fix"]
    for scenario in required:
        satisfied = any(scenario in e.metadata.get("trigger", "") for e in thinking_events)
        status = "✓" if satisfied else "✗"
        print(f"  {status} Required scenario: {scenario}")

    # ... more analysis ...

if __name__ == "__main__":
    analyze_compliance(sys.argv[1])
```

**Acceptance criteria:**
- Can analyze traces for compliance
- Reports which required scenarios were satisfied
- Outputs actionable metrics

---

### Phase 3 Validation

Before moving to Phase 4:
- [ ] V5 gating blocks completion without thinking
- [ ] Temptations tracked correctly
- [ ] Compliance script runs and produces useful output
- [ ] Run 3-5 SWE-bench tasks, analyze compliance

---

## Phase 4: Analysis & Iteration (Priority 4)

**Goal:** Use reasoning traces to improve the system

**Owner:** Devin + Human review
**Duration:** 2-3 days ongoing
**Deliverables:**
- ✅ Cognitive event analysis dashboard
- ✅ SWE-bench validation experiments (5-10 tasks)
- ✅ Iteration based on reasoning trace insights

### Tasks

#### 4.1 Build Analysis Dashboard

Create Jupyter notebook or web dashboard showing:
- Thinking compliance rate by phase
- Most common thinking scenarios triggered
- Temptation encounter/resistance rates
- Decision point timeline visualization
- Reasoning coherence samples (manual review)

#### 4.2 Run Validation Experiments

Run CompyMac V5 on 5-10 diverse SWE-bench tasks:
- Easy: pylint-dev__pylint-5859 (already solved with V4)
- Medium: 2-3 tasks with moderate complexity
- Hard: 2-3 tasks known to be difficult

For each task:
1. Run with V5 metacognitive scaffolding
2. Capture full reasoning traces
3. Analyze compliance report
4. Review thinking content for coherence
5. Identify failure modes (if task failed)

#### 4.3 Iterate Based on Insights

Common patterns to look for:
- Which thinking scenarios are most/least triggered?
- Are there missing required scenarios?
- Do agents resist or succumb to temptations?
- Is thinking content coherent or rambling?
- Are decision points well-reasoned?

Adjust:
- Add new required thinking scenarios if gaps found
- Refine temptation definitions
- Improve prompt guidance based on observed confusion
- Tune validation thresholds

---

## Success Criteria (Overall)

**After Phase 4 completion, CompyMac should achieve:**

### Cognitive Quality (Primary)
- ✅ 100% compliance with required thinking scenarios in successful runs
- ✅ >80% temptation recognition rate when applicable
- ✅ Reasoning coherence score >7/10 (manual evaluation)
- ✅ Can diagnose failure in <30min using reasoning traces

### Task Performance (Secondary)
- ✅ Maintain or improve V4 SWE-bench resolution rate (≥33%)
- ✅ No increase in token usage >20%
- ✅ Time to completion not significantly increased

### Documentation
- ✅ METACOGNITIVE_ARCHITECTURE.md complete and reviewed
- ✅ System prompts include all scaffolding
- ✅ Examples of good/bad thinking in docs
- ✅ Analysis tools documented and usable

---

## Long-term Vision (Beyond Phase 4)

### V6: Self-Improving Reflection
- Agents learn from their own reasoning traces
- Cross-attempt learning enhanced with metacognitive data
- "This approach failed last attempt because..." insights

### V7: Multi-Agent Metacognition
- Agents reason about other agents' thinking
- Collaborative debugging via shared reasoning traces
- Peer review of cognitive quality

### V8: Human-in-the-Loop Cognition
- Human can inject thinking prompts during execution
- "Pause and think about X before proceeding"
- Interactive cognitive oversight

---

## Notes for Devin (Next Session)

**Starting Point:**
- Review `METACOGNITIVE_ARCHITECTURE.md` first
- Understand the philosophy before coding
- V4 evidence-based gating is solid foundation to build on

**Development Approach:**
- Implement Phase 1 completely before moving to Phase 2
- Test each component as you build it
- Use `pytest` to ensure existing functionality still works
- Capture your own reasoning in commit messages

**Communication:**
- If you hit ambiguities in the spec, ask questions
- If you discover issues with the design, propose alternatives
- If you need to deviate from the roadmap, explain why

**Quality Standards:**
- Code should be production-ready (type hints, docstrings, error handling)
- Tests should cover new functionality
- Backward compatibility with existing SWE-bench pipeline
- Trace store schema migrations must be safe

**Success Signal:**
You'll know Phase 1 is complete when you can:
1. Call `think("I'm reasoning about X...")` in a SWE-bench run
2. See the thinking content in SQLite trace store
3. Query cognitive events and get meaningful data
4. Block an action that requires thinking but didn't get it

Good luck! This is important work. We're building the foundation for truly observable AI agents.

---

**Document Version:** 1.0
**Created:** 2025-12-27
**Next Review:** After Phase 1 completion
