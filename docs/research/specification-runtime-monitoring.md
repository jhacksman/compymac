# Specification and Runtime Monitoring Research

## Overview

This document summarizes research on specification languages and runtime monitoring for LLM agents. These techniques extend CompyMac's two-phase verification beyond todos to tool use, session behavior, and termination conditions.

## Key Papers

### 1. AgentSpec: Customizable Runtime Enforcement (arXiv:2503.18666)

**Core Contribution**: A lightweight domain-specific language (DSL) for specifying and enforcing runtime constraints on LLM agents.

**Architecture**:
- Users define structured rules with triggers, predicates, and enforcement mechanisms
- Rules ensure agents operate within predefined safety boundaries
- Computationally lightweight (millisecond overhead)

**Rule Structure**:
```
TRIGGER: <event that activates rule>
PREDICATE: <condition to check>
ENFORCEMENT: <action if predicate fails>
```

**Results**:
- 90%+ prevention of unsafe code executions
- 100% elimination of hazardous actions in embodied agent tasks
- 100% compliance enforcement for autonomous vehicles

**Key Insight**: "By combining interpretability, modularity, and efficiency, AgentSpec provides a practical and scalable solution for enforcing LLM agent safety."

**Relevance to CompyMac**: This DSL approach could formalize our guardrail rules. Instead of implicit constraints in prompts, we could have explicit, verifiable specifications.

---

### 2. Pro2Guard: Proactive Runtime Enforcement (arXiv:2508.00500)

**Problem**: Reactive safety rules (like AgentSpec) respond only when unsafe behavior is imminent or has already occurred. They lack foresight for long-horizon dependencies.

**Solution**: Proactive enforcement via probabilistic reachability analysis.

**Architecture**:
1. Abstract agent behaviors into symbolic states
2. Learn Discrete-Time Markov Chain (DTMC) from execution traces
3. At runtime, estimate probability of reaching unsafe states
4. Trigger interventions BEFORE violations occur

**Key Innovation**: "Pro2Guard anticipates future risks by estimating the probability of reaching unsafe states, triggering interventions before violations occur when the predicted risk exceeds a user-defined threshold."

**Relevance to CompyMac**: Our TraceStore captures execution traces that could train such a model. Proactive intervention could prevent agents from going down paths that historically lead to failures.

---

### 3. VeriGuard: Verified Code Generation for Agent Safety (OpenReview)

**Core Contribution**: Formal safety guarantees through dual-stage architecture.

**Stage 1 - Offline Validation**:
1. Clarify user intent to establish precise safety specifications
2. Synthesize behavioral policy
3. Test in simulated environments
4. Formal verification to mathematically prove compliance
5. Iterate until policy is correct

**Stage 2 - Online Monitoring**:
- Validate each proposed action against pre-verified policy
- Lightweight runtime checks (heavy work done offline)

**Key Insight**: Separation of exhaustive offline validation from lightweight online monitoring enables formal guarantees to be practically applied.

**Relevance to CompyMac**: We could pre-verify common tool sequences offline, then use lightweight checks at runtime. This is similar to our "known good patterns" approach.

---

### 4. AgentArmor: Program Analysis on Agent Traces (arXiv:2508.01249)

**Core Insight**: Treat agent runtime traces as structured programs with analyzable semantics.

**Architecture**:
1. **Graph Constructor**: Reconstruct agent traces as graph-based intermediate representations (CFG, DFG, PDG)
2. **Property Registry**: Attach security-relevant metadata to tools and data
3. **Type System**: Perform static inference and checking over the IR

**Results on AgentDojo Benchmark**:
- 95.75% True Positive Rate
- Only 3.66% False Positive Rate

**Key Insight**: "By representing agent behavior as structured programs, AgentArmor enables program analysis over sensitive data flow, trust boundaries, and policy violations."

**Relevance to CompyMac**: Our TraceStore already captures structured traces. We could apply program analysis techniques to detect policy violations, data flow issues, and trust boundary crossings.

---

### 5. Prompt Flow Integrity (arXiv:2503.15547)

**Problem**: LLM agents are vulnerable to privilege escalation attacks. User prompts can be interpreted insecurely, creating non-deterministic behaviors.

**Solution**: Three mitigation techniques:
1. **Untrusted Data Identification**: Mark data sources by trust level
2. **Least Privilege Enforcement**: Limit agent capabilities to minimum required
3. **Unsafe Data Flow Validation**: Detect when untrusted data flows to privileged operations

**Key Insight**: "Analyzing the architectural characteristics of LLM agents, PFI features three mitigation techniques—untrusted data identification, enforcing least privilege on LLM agents, and validating unsafe data flows."

**Relevance to CompyMac**: Our tool permission system could implement least privilege. We could track data provenance through our trace system to detect unsafe flows.

---

### 6. LTL-Based Safety Constraints for Robots (Brown University)

**Core Contribution**: Queryable safety constraint module based on Linear Temporal Logic (LTL).

**Capabilities**:
1. Natural language to temporal constraints encoding
2. Safety violation reasoning and explaining
3. Unsafe action pruning

**Key Insight**: LTL provides formal semantics for temporal constraints like "never do X after Y" or "always do Z before W".

**Relevance to CompyMac**: Our todo system has implicit temporal constraints (dependencies, ordering). LTL could formalize these and enable automated verification.

---

## Implications for CompyMac

### Specification Language Design

Based on the research, a specification language for CompyMac should support:

1. **Triggers**: Events that activate rules (tool calls, state changes, completions)
2. **Predicates**: Conditions to check (permissions, data flow, temporal constraints)
3. **Enforcement**: Actions when predicates fail (block, warn, require confirmation)
4. **Temporal Logic**: Ordering constraints (before, after, never, always)

### Example Specifications

```yaml
# Prevent file deletion without backup
rule: safe_delete
  trigger: tool_call(name="bash", command_contains="rm")
  predicate: 
    - previous_action_contains("backup") OR
    - previous_action_contains("git commit")
  enforcement: block_with_message("Create backup before deletion")

# Require verification before claiming completion
rule: verified_completion
  trigger: todo_status_change(to="completed")
  predicate:
    - evidence_attached(todo_id) AND
    - evidence_verified(todo_id)
  enforcement: revert_to("in_progress")

# Least privilege for file operations
rule: file_scope
  trigger: tool_call(name="Edit" OR name="Write")
  predicate:
    - file_path IN allowed_paths(current_task)
  enforcement: require_confirmation("File outside task scope")
```

### Integration Points

| Monitoring Capability | CompyMac Component | Status |
|----------------------|-------------------|--------|
| Rule specification | Guardrail config | Planned |
| Trace analysis | TraceStore | Implemented |
| Trust boundaries | Tool permissions | Partial |
| Temporal constraints | Todo dependencies | Partial |
| Proactive intervention | Agent loop | Planned |

### Metrics to Track

1. **Rule Violations**: Count and categorize blocked actions
2. **False Positives**: Actions blocked that were actually safe
3. **Intervention Latency**: Time from detection to enforcement
4. **Coverage**: Percentage of agent actions covered by rules

---

## Open Questions

1. **Specification Complexity**: How complex can rules be before they become unmaintainable?

2. **Learning Rules**: Can we learn specifications from successful traces rather than writing them manually?

3. **Proactive vs Reactive**: When is proactive intervention worth the computational cost?

4. **User Override**: How do we handle cases where users want to override safety rules?

---

## References

- arXiv:2503.18666 - "AgentSpec: Customizable Runtime Enforcement for Safe and Reliable LLM Agents"
- arXiv:2508.00500 - "Pro2Guard: Proactive Runtime Enforcement of LLM Agent Safety via Probabilistic Model Checking"
- OpenReview - "VeriGuard: Enhancing LLM Agent Safety via Verified Code Generation"
- arXiv:2508.01249 - "AgentArmor: Enforcing Program Analysis on Agent Runtime Trace"
- arXiv:2503.15547 - "Prompt Flow Integrity to Prevent Privilege Escalation in LLM Agents"
- Brown University - "Plug in the Safety Chip: Enforcing Constraints for LLM-driven Robot Agents"
