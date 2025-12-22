# Agent Hallucination Research

## Overview

This document summarizes research on LLM agent hallucinations - a distinct phenomenon from traditional LLM hallucinations that affects autonomous agent systems. Agent hallucinations have longer propagation chains, span multiple steps, and have physically consequential outcomes.

## Key Papers

### 1. LLM-based Agents Suffer from Hallucinations: A Survey (arXiv:2509.18970)

**Core Finding**: Agent hallucinations are fundamentally different from traditional LLM hallucinations because they occur within multi-step, tool-augmented workflows where errors propagate and compound.

**Hallucination Taxonomy**:
- **Perception Hallucinations**: Misinterpreting observations from the environment
- **Memory Hallucinations**: Fabricating or distorting information from previous steps
- **Planning Hallucinations**: Creating infeasible or incorrect action plans
- **Action Hallucinations**: Executing actions that don't match the intended plan
- **Reflection Hallucinations**: Incorrectly evaluating task completion or progress

**Key Insight for CompyMac**: The survey emphasizes that agent hallucinations have "physically consequential" outcomes - they affect real-world task execution, not just text generation. This validates our guardrailed todo system design where agents cannot simply "declare victory" without verifiable evidence.

**Mitigation Strategies Identified**:
1. Runtime verification of agent actions
2. Grounding agent outputs in observable environment state
3. Multi-agent verification (one agent checks another)
4. Structured output formats that constrain hallucination space

---

### 2. AgentSpec: Customizable Runtime Enforcement (arXiv:2503.18666)

**Core Contribution**: A framework for defining and enforcing runtime constraints on LLM agents through domain-specific specifications.

**Architecture**:
- **Triggers**: Events that activate constraint checking (tool calls, state changes)
- **Predicates**: Conditions that must hold (pre-conditions, post-conditions, invariants)
- **Enforcement Mechanisms**: Actions taken when constraints are violated (block, warn, rollback)

**Key Patterns**:
```
Constraint = Trigger + Predicate + Enforcement
```

Examples:
- "Before file deletion, verify file exists" (pre-condition)
- "After todo completion, verify acceptance criteria" (post-condition)
- "Never allow bulk state replacement" (invariant)

**Relevance to CompyMac**: This directly informs our guardrail architecture. Our todo state machine (pending -> in_progress -> claimed -> verified) is a form of runtime enforcement where the agent cannot skip transitions or set terminal states directly.

---

### 3. MIRAGE-Bench: Measuring Agent Hallucinations (arXiv:2507.21017)

**Core Contribution**: A benchmark for measuring hallucinations in interactive agent scenarios, with a taxonomy of hallucination types.

**Three Types of Agentic Hallucinations**:

1. **Task Instruction Unfaithfulness**: Actions that deviate from what the user asked
   - Example: User asks to "fix the bug" but agent refactors unrelated code
   
2. **Execution History Unfaithfulness**: Actions inconsistent with previous steps
   - Example: Agent claims to have run tests but no test execution in history
   
3. **Environment Observation Unfaithfulness**: Actions based on misinterpreted observations
   - Example: Agent reads file content but acts on hallucinated content

**Measurement Approach**: Compare agent's claimed actions/observations against ground truth from environment logs.

**Relevance to CompyMac**: Our TraceStore and EventLog provide the ground truth needed to detect all three types of hallucinations. The immutable audit log means we can always verify what actually happened vs. what the agent claims happened.

---

### 4. GuardAgent: Knowledge-Enabled Reasoning (arXiv:2406.09187)

**Core Contribution**: Using a separate "guard" agent to verify the primary agent's actions through knowledge-enabled reasoning.

**Architecture**:
- Primary agent proposes actions
- Guard agent evaluates actions against:
  - Task constraints
  - Safety policies
  - Domain knowledge
- Guard can approve, modify, or reject actions

**Key Insight**: Separation of concerns between "doing" and "verifying" reduces hallucination risk because the verifier has different incentives and context than the actor.

**Relevance to CompyMac**: This validates our two-phase completion design where the agent can only "claim" completion but the harness (acting as guard) verifies. The agent and harness have different roles and the harness doesn't share the agent's potential biases.

---

## Implications for CompyMac

### Design Principles Derived from Research

1. **Immutable Audit Trail**: Every action must be logged with full context (MIRAGE-Bench pattern)

2. **Runtime Enforcement**: Constraints checked at execution time, not just in prompts (AgentSpec pattern)

3. **Two-Phase Verification**: Agent claims, harness verifies (GuardAgent pattern)

4. **State Machine Constraints**: Prevent impossible transitions (AgentSpec invariants)

5. **Evidence-Based Completion**: "Done" requires machine-checkable proof (all papers)

### Current Implementation Status

| Principle | Status | Implementation |
|-----------|--------|----------------|
| Immutable Audit Trail | Implemented | TraceStore, EventLog |
| Runtime Enforcement | Partial | Schema validation, state transitions |
| Two-Phase Verification | Implemented | claimed -> verified states |
| State Machine Constraints | Implemented | Todo status transitions |
| Evidence-Based Completion | Implemented | Acceptance criteria system |

### Open Questions

1. **Harness-Level Enforcement**: How do we prevent the agent loop from terminating while todos are only "claimed" (not "verified")?

2. **Separation of Duties**: Should TodoVerify be callable only by the harness, not the agent?

3. **Acceptance Criteria Gaming**: Can an agent choose trivially-satisfiable criteria to game the system?

---

## References

- arXiv:2509.18970 - "LLM-based Agents Suffer from Hallucinations: A Survey"
- arXiv:2503.18666 - "AgentSpec: Customizable Runtime Enforcement for Safe and Reliable LLM Agents"
- arXiv:2507.21017 - "MIRAGE-Bench: LLM Agent is Hallucinating and Where to Find Them"
- arXiv:2406.09187 - "GuardAgent: Safeguard LLM Agents via Knowledge-Enabled Reasoning"
