# V5 Metacognitive Architecture Iteration Guide

This guide documents how to analyze cognitive compliance data and iterate on the V5 metacognitive scaffolding based on insights from validation experiments.

## Overview

Phase 4.3 of the V5 implementation focuses on using reasoning traces to improve the system. This document provides guidelines for:

1. Analyzing cognitive compliance patterns
2. Identifying areas for improvement
3. Making targeted adjustments to the scaffolding

## Analysis Workflow

### Step 1: Run Validation Experiments

Use the V5 validation experiments script to run SWE-bench tasks:

```bash
# Run 5 tasks with recommended selection
python scripts/v5_validation_experiments.py --num-tasks 5

# Run a specific task
python scripts/v5_validation_experiments.py --task-id pylint-dev__pylint-5859

# Dry run to see what would be executed
python scripts/v5_validation_experiments.py --num-tasks 10 --dry-run
```

### Step 2: Analyze Results with Dashboard

Open the Jupyter notebook for detailed analysis:

```bash
cd notebooks
jupyter notebook cognitive_analysis_dashboard.ipynb
```

Set the `TRACE_ID` variable to analyze a specific task run.

### Step 3: Use CLI Analysis Script

For quick compliance checks:

```bash
python scripts/analyze_cognitive_compliance.py <trace_id>
```

## Common Patterns to Look For

### Thinking Scenario Patterns

| Pattern | Indicator | Action |
|---------|-----------|--------|
| Low trigger rate for scenario X | `scenario_counts[X] < expected` | Add more explicit prompts for scenario X |
| Missing required scenarios | `required_scenario_compliance[X] = False` | Strengthen gating for scenario X |
| Excessive thinking | `total_thinking_events > 50` | Review if thinking is productive or rambling |
| No thinking in phase Y | `by_phase[Y] = 0` | Add phase-specific thinking triggers |

### Temptation Patterns

| Pattern | Indicator | Action |
|---------|-----------|--------|
| High T1 (claiming victory) | `by_type["T1_claiming_victory"] > 3` | Strengthen evidence-based gating |
| Low recognition rate | `recognition_rate < 0.5` | Improve temptation awareness in prompts |
| Low resistance rate | `resistance_rate < 0.7` | Add stronger prevention guidance |
| New temptation type | Repeated failures not in catalog | Add to temptation catalog |

### Reasoning Quality Patterns

| Pattern | Indicator | Action |
|---------|-----------|--------|
| Rambling thinking | Long content with no clear conclusion | Add structure requirements to prompts |
| Shallow thinking | Very short content (<50 chars) | Require minimum reasoning depth |
| Off-topic thinking | Content unrelated to task | Improve scenario-specific guidance |
| Repetitive thinking | Same content across events | Add novelty requirements |

## Adjustment Guidelines

### Adding New Required Thinking Scenarios

If analysis reveals gaps in thinking coverage:

1. Identify the critical action that needs thinking
2. Add scenario to `get_required_thinking_scenarios()` in `swe_workflow.py`
3. Add trigger validation in the appropriate tool handler
4. Update the V5 system prompt with guidance for the new scenario

Example:
```python
# In swe_workflow.py
def get_required_thinking_scenarios(phase: SWEPhase) -> list[str]:
    scenarios = {
        SWEPhase.LOCALIZATION: [
            "before_narrowing_search",  # NEW: Think before focusing on specific files
        ],
        # ...
    }
```

### Refining Temptation Definitions

If agents are falling for temptations not in the catalog:

1. Document the new temptation pattern observed
2. Add to `Temptation` enum in `temptations.py`
3. Add definition to `TEMPTATION_CATALOG`
4. Update system prompt with awareness guidance

Example:
```python
# In temptations.py
class Temptation(Enum):
    # ... existing temptations ...
    T9_PATTERN_MATCHING = "T9_pattern_matching"  # NEW

TEMPTATION_CATALOG[Temptation.T9_PATTERN_MATCHING] = TemptationDefinition(
    name="Pattern Matching Without Understanding",
    description="Applying a fix pattern without understanding the root cause",
    why_tempting="Patterns from similar bugs seem like quick solutions",
    prevention="Always verify the root cause matches the pattern's assumptions",
    evidence="Fix applied but tests still fail in unexpected ways",
)
```

### Improving Prompt Guidance

If thinking content is low quality:

1. Review samples in the dashboard
2. Identify specific quality issues
3. Add targeted guidance to `prompts/swe_bench_v5.md`

Example additions:
```markdown
## Thinking Quality Guidelines

When using <think>, ensure your reasoning:
- States the specific question you're answering
- Lists relevant evidence from your exploration
- Considers at least 2 alternative approaches
- Concludes with a clear decision and rationale
```

### Tuning Validation Thresholds

If gating is too strict or too lenient:

1. Review false positive/negative rates
2. Adjust `within_seconds` parameter in `has_recent_thinking()`
3. Adjust required scenario lists

Example:
```python
# In swe_workflow.py - make thinking requirement more lenient
def validate_completion_reasoning(self) -> tuple[bool, str]:
    # Changed from 600 to 900 seconds based on analysis
    if not self.has_recent_thinking("before_claiming_completion", within_seconds=900):
        # ...
```

## Success Metrics

After iteration, validate improvements by checking:

### Cognitive Quality (Primary)
- 100% compliance with required thinking scenarios in successful runs
- >80% temptation recognition rate when applicable
- Reasoning coherence score >7/10 (manual evaluation)
- Can diagnose failure in <30min using reasoning traces

### Task Performance (Secondary)
- Maintain or improve V4 SWE-bench resolution rate (>=33%)
- No increase in token usage >20%
- Time to completion not significantly increased

## Iteration Checklist

Before each iteration cycle:

- [ ] Run validation experiments (5-10 tasks)
- [ ] Analyze compliance reports
- [ ] Review thinking samples for coherence
- [ ] Identify top 3 improvement areas
- [ ] Make targeted adjustments
- [ ] Re-run validation to measure impact
- [ ] Document changes and results

## Example Iteration Log

```
## Iteration 1 - 2025-01-XX

### Analysis
- Ran 5 tasks: 2 resolved, 1 partial, 2 failed
- Compliance rate: 67%
- Missing scenario: before_advancing_to_fix in 3/5 tasks
- T1_claiming_victory encountered 4 times, resisted 1 time

### Changes Made
1. Added stronger gating for UNDERSTANDING -> FIX transition
2. Updated prompt with explicit T1 awareness section
3. Reduced thinking timeout from 600s to 300s

### Results After Changes
- Ran 5 tasks: 3 resolved, 1 partial, 1 failed
- Compliance rate: 100%
- T1 resistance rate improved to 75%
```

## Related Documentation

- [METACOGNITIVE_ARCHITECTURE.md](../METACOGNITIVE_ARCHITECTURE.md) - Full V5 design specification
- [ROADMAP.md](../ROADMAP.md) - Implementation roadmap
- [prompts/swe_bench_v5.md](../src/compymac/prompts/swe_bench_v5.md) - V5 system prompt template
