# Planning and Termination Control Research

## Overview

This document summarizes research on when agents should stop, detecting "stuckness," and enforcing completion criteria. These techniques are central to CompyMac's "can't declare done until X" principle.

## Key Papers

### 1. CaRT: Teaching LLMs When They Know Enough (arXiv:2510.08517)

**Core Problem**: Models need to know not only how to gather information, but also when to stop gathering and make a decision.

**Solution**: Counterfactuals and Reasoning for Termination (CaRT).

**Approach**:
1. Fine-tune LLMs using counterfactual pairs of trajectories
2. One trajectory where termination is appropriate
3. Minimally modified version where it is not
4. Train LLM to explain rationale for termination decision

**Domains Tested**:
- Interactive medical diagnosis
- Math problem solving

**Results**: CaRT improves both efficiency of information gathering and task success rate.

**Key Insight**: "Strategic information gathering requires models to know not only how to effectively acquire information, but also when to stop gathering information and make a decision, in order to avoid overthinking or getting derailed when acting."

**Relevance to CompyMac**: Our agents often over-gather information or stop too early. CaRT's counterfactual training could teach better termination judgment.

---

### 2. Early-Exit Behavior in Embodied Agents (arXiv:2505.17616)

**Title**: "Runaway is Ashamed, But Helpful"

**Problem**: LLM agents often get trapped in repetitive loops or issue ineffective commands, leading to redundant computational overhead.

**Two Approaches**:
1. **Intrinsic Method**: Inject exit instructions during generation
2. **Extrinsic Method**: Verify task completion to determine when to halt

**Metrics**:
- Reduction of redundant steps (positive effect)
- Progress degradation (negative effect)

**Results**: Significant efficiency improvements with only minor drops in agent performance.

**Key Insight**: "Instead of relying solely on learning from trajectories, we take a first step toward exploring the early-exit behavior for LLM-based agents."

**Relevance to CompyMac**: We could implement both intrinsic (prompt-based) and extrinsic (verification-based) termination controls.

---

### 3. Early Stopping Chain-of-Thought (arXiv:2509.14004)

**Problem**: Long chain-of-thought (CoT) incurs high inference costs.

**Solution**: ES-CoT - detect answer convergence and stop early.

**Mechanism**:
1. At end of each reasoning step, prompt LLM to output current answer
2. Track run length of consecutive identical answers
3. When run length shows sharp increase and exceeds threshold, terminate

**Results**:
- ~41% reduction in inference tokens
- Accuracy comparable to standard CoT

**Key Insight**: "Step answers steadily converge to the final answer, and large run-length jumps reliably mark this convergence."

**Relevance to CompyMac**: We could detect when agent's plan/approach has stabilized and stop unnecessary deliberation.

---

### 4. Learning When to Plan (arXiv:2509.03581)

**Problem**: Efficiently allocating test-time compute for LLM agents.

**Key Question**: When should agents spend more time planning vs. acting?

**Approach**: Learn a policy for when to invoke planning vs. direct action.

**Findings**:
- Not all situations benefit from extensive planning
- Some tasks are better solved with quick actions
- Adaptive planning allocation improves efficiency

**Relevance to CompyMac**: Our agents could learn when to plan extensively vs. when to act directly.

---

### 5. Plan-and-Act: Long-Horizon Task Planning (arXiv:2503.09572)

**Problem**: LLMs are not inherently trained for planning tasks.

**Solution**: Separate high-level planning from low-level execution.

**Architecture**:
- **Planner Model**: Generates structured, high-level plans
- **Executor Model**: Translates plans into environment-specific actions

**Training**: Synthetic data generation that annotates ground-truth trajectories with feasible plans.

**Results**:
- 57.58% success rate on WebArena-Lite (state-of-the-art)
- 81.36% success rate on WebVoyager (text-only SOTA)

**Key Insight**: "Generating accurate plans remains difficult since LLMs are not inherently trained for this task."

**Relevance to CompyMac**: Our Planner agent could benefit from explicit planning training. The separation of planning and execution aligns with our architecture.

---

### 6. Parallel LLM Agents for Multi-Step Tasks (arXiv:2507.08944)

**Problem**: Multi-agent systems incur high latency due to iterative reasoning cycles.

**Solution**: M1-Parallel - run multiple agent teams in parallel.

**Strategies**:
1. **Early Termination**: Stop when first team succeeds (2.2x speedup)
2. **Aggregation**: Combine results for higher completion rates

**Key Insight**: "By leveraging an event-driven communication model with asynchronous messaging, M1-Parallel efficiently capitalizes on the inherent diversity of valid plans."

**Relevance to CompyMac**: Our parallel rollouts (best-of-N) implement similar ideas. Early termination could improve efficiency.

---

### 7. Task Reasoning via Single-Turn RL (arXiv:2509.20616)

**Problem**: Training LLM agents for multi-turn task planning faces challenges:
- Sparse episode-wise rewards
- Credit assignment across long horizons
- Computational overhead

**Solution**: Transform multi-turn planning into single-turn reasoning problems.

**Key Finding**: "GRPO improvement on single-turn task reasoning results in higher multi-turn success probability under the minimal turns."

**Results**: 1.5B parameter model achieves 70% success rate on 30+ step tasks, outperforming 14B baselines.

**Relevance to CompyMac**: We could train/prompt agents to reason about entire task trajectories in single turns, then execute.

---

### 8. Encouraging Good Processes (arXiv:2508.19598)

**Focus**: Reinforcement learning for LLM agent planning without requiring "good answers."

**Key Insight**: We can train agents to follow good processes even when we can't easily verify final answers.

**Relevance to CompyMac**: Our verification approach focuses on process (evidence of completion) rather than just outcomes.

---

## Implications for CompyMac

### Termination Criteria Framework

Based on the research, termination should be based on:

1. **Completion Evidence**: Verifiable proof that task is done
2. **Convergence Detection**: Agent's approach has stabilized
3. **Resource Limits**: Time/token budget exhausted
4. **Stuckness Detection**: Agent is making no progress
5. **Human Override**: User explicitly terminates

### Termination Decision Tree

```
Is task complete?
├── Yes (with evidence) → TERMINATE_SUCCESS
└── No
    ├── Is agent making progress?
    │   ├── Yes → CONTINUE
    │   └── No (stuck)
    │       ├── Can we try alternative approach?
    │       │   ├── Yes → RETRY_DIFFERENT
    │       │   └── No → ESCALATE_TO_HUMAN
    │       └── Have we exceeded retry limit?
    │           ├── Yes → TERMINATE_FAILURE
    │           └── No → RETRY_SAME
    └── Have we exceeded resource limits?
        ├── Yes → TERMINATE_PARTIAL
        └── No → CONTINUE
```

### Stuckness Detection

Signs that agent is stuck:

1. **Repetitive Actions**: Same action attempted multiple times
2. **Circular Reasoning**: Returning to previously visited states
3. **No State Change**: Actions don't change environment
4. **Increasing Uncertainty**: Agent's confidence decreasing
5. **Error Loops**: Same errors recurring

```python
class StucknessDetector:
    """Detect when agent is stuck."""
    
    def __init__(self, window_size: int = 10):
        self.action_history = []
        self.state_history = []
        
    def is_stuck(self) -> bool:
        """Check if agent appears stuck."""
        return (
            self._has_repetitive_actions() or
            self._has_circular_states() or
            self._has_no_progress()
        )
    
    def _has_repetitive_actions(self) -> bool:
        """Check for repeated identical actions."""
        recent = self.action_history[-5:]
        return len(set(recent)) == 1 and len(recent) == 5
    
    def _has_circular_states(self) -> bool:
        """Check for returning to previous states."""
        if len(self.state_history) < 3:
            return False
        return self.state_history[-1] in self.state_history[:-2]
    
    def _has_no_progress(self) -> bool:
        """Check if state hasn't changed."""
        if len(self.state_history) < 3:
            return False
        return all(s == self.state_history[-1] for s in self.state_history[-3:])
```

### Completion Verification

Based on our "can't declare done until X" principle:

```python
class CompletionVerifier:
    """Verify that task is actually complete."""
    
    def verify_completion(self, task: Task, claimed_result: Result) -> VerificationResult:
        """Verify claimed completion against acceptance criteria."""
        
        evidence = []
        
        # Check each acceptance criterion
        for criterion in task.acceptance_criteria:
            check_result = self._check_criterion(criterion, claimed_result)
            evidence.append(check_result)
        
        # All criteria must pass
        all_passed = all(e.passed for e in evidence)
        
        return VerificationResult(
            verified=all_passed,
            evidence=evidence,
            missing=[e for e in evidence if not e.passed]
        )
    
    def _check_criterion(self, criterion: Criterion, result: Result) -> CheckResult:
        """Check a single criterion."""
        # Different verification strategies based on criterion type
        if criterion.type == "test_passes":
            return self._run_tests(criterion.tests)
        elif criterion.type == "file_exists":
            return self._check_file(criterion.path)
        elif criterion.type == "output_matches":
            return self._check_output(criterion.pattern, result.output)
        # ... etc
```

### Adaptive Planning

When to plan extensively vs. act quickly:

| Situation | Planning Level | Rationale |
|-----------|---------------|-----------|
| Novel task | High | Need to explore solution space |
| Familiar pattern | Low | Can apply known approach |
| High stakes | High | Mistakes are costly |
| Time pressure | Low | Speed matters more |
| Uncertain environment | High | Need contingency plans |
| Clear requirements | Low | Path is obvious |

### Early Termination Signals

Based on ES-CoT research, we can detect convergence:

```python
class ConvergenceDetector:
    """Detect when agent's approach has converged."""
    
    def __init__(self, threshold: int = 3):
        self.answer_history = []
        self.threshold = threshold
        
    def add_answer(self, answer: str):
        """Record current answer."""
        self.answer_history.append(answer)
        
    def has_converged(self) -> bool:
        """Check if answers have converged."""
        if len(self.answer_history) < self.threshold:
            return False
        
        recent = self.answer_history[-self.threshold:]
        return len(set(recent)) == 1
    
    def run_length(self) -> int:
        """Get current run length of identical answers."""
        if not self.answer_history:
            return 0
        
        current = self.answer_history[-1]
        count = 0
        for answer in reversed(self.answer_history):
            if answer == current:
                count += 1
            else:
                break
        return count
```

---

## Metrics to Track

1. **Termination Accuracy**: How often does agent terminate at the right time?
2. **Premature Termination Rate**: How often does agent stop too early?
3. **Over-Execution Rate**: How often does agent continue past completion?
4. **Stuckness Detection Latency**: How quickly do we detect stuck agents?
5. **Recovery Success Rate**: How often do stuck agents recover?

---

## Open Questions

1. **Optimal Termination Threshold**: How do we set thresholds for convergence detection?

2. **Partial Completion**: How do we handle tasks that are partially complete?

3. **Subjective Completion**: How do we verify tasks with subjective success criteria?

4. **Learning Termination**: Can agents learn better termination policies from experience?

---

## References

- arXiv:2510.08517 - "CaRT: Teaching LLM Agents to Know When They Know Enough"
- arXiv:2505.17616 - "Runaway is Ashamed, But Helpful: On the Early-Exit Behavior of LLM-based Agents"
- arXiv:2509.14004 - "Early Stopping Chain-of-thoughts in Large Language Models"
- arXiv:2509.03581 - "Learning When to Plan: Efficiently Allocating Test-Time Compute for LLM Agents"
- arXiv:2503.09572 - "Plan-and-Act: Improving Planning of Agents for Long-Horizon Tasks"
- arXiv:2507.08944 - "Optimizing Sequential Multi-Step Tasks with Parallel LLM Agents"
- arXiv:2509.20616 - "Training Task Reasoning LLM Agents for Multi-turn Task Planning via Single-turn RL"
- arXiv:2508.19598 - "Encouraging Good Processes Without the Need for Good Answers"
