# Tool Reliability and Observability Engineering

## Overview

This document summarizes research on tool failure modes, error handling, and observability for LLM agents. These techniques make tool outputs verifiable artifacts and help agents recover from failures gracefully.

## Key Papers

### 1. Failure Modes in LLM Systems (arXiv:2511.19933)

**Core Contribution**: System-level taxonomy for reliable AI applications.

**Key Insight**: "Large language models (LLMs) are being rapidly integrated into decision-support tools, automation workflows, and AI-enabled software systems. However, their behavior in production environments remains poorly understood."

**Failure Categories**:
1. **Model Failures**: Hallucinations, inconsistency, capability limits
2. **Integration Failures**: API errors, timeout, format mismatches
3. **System Failures**: Resource exhaustion, cascading errors
4. **Semantic Failures**: Correct execution, wrong intent

**Relevance to CompyMac**: We need to handle all four failure categories. Our error envelopes address integration failures, but we need better handling of semantic failures.

---

### 2. PALADIN: Self-Correcting Agents for Tool Failures (arXiv:2509.25238)

**Problem**: Tool-augmented agents frequently fail due to tool malfunctions—timeouts, API exceptions, inconsistent outputs.

**Solution**: Framework for robust failure recovery.

**Architecture**:
1. Train on 50,000+ recovery-annotated trajectories
2. Systematic failure injection during training
3. LoRA-based fine-tuning to retain base capabilities
4. Runtime error detection and recovery action selection

**Recovery Bank**: 55+ failure exemplars aligned with ToolScan taxonomy.

**Results**:
- Recovery Rate improved from 32.76% to 89.68% (+57%)
- Outperforms CRITIC baseline (76.34%) by +13.3%
- 95.2% recovery performance on unseen tool APIs

**Key Insight**: "Existing agent training pipelines optimize only for success trajectories, failing to expose models to the tool failures that dominate real-world usage."

**Relevance to CompyMac**: We should train/prompt agents with failure scenarios, not just success cases. Our error handling should include recovery strategies.

---

### 3. Aegis: Agent-Environment Failure Taxonomy (arXiv:2508.19504)

**Core Contribution**: Taxonomy and optimizations for overcoming agent-environment failures.

**Methodology**:
- Collected 142 agent traces (3,656 turns)
- Analyzed across 5 state-of-the-art benchmarks

**Six Failure Modes**:
1. **Observation Parsing**: Agent misinterprets environment output
2. **Action Formatting**: Agent produces malformed actions
3. **State Tracking**: Agent loses track of environment state
4. **Goal Drift**: Agent pursues wrong objective
5. **Resource Exhaustion**: Agent runs out of tokens/time
6. **Environment Instability**: Environment behaves unexpectedly

**Key Insight**: "Prior research has primarily focused on improving the agents themselves, such as developing strong agentic LLMs, while overlooking the role of the system environment in which the agent operates."

**Relevance to CompyMac**: We should optimize the environment (tool interfaces, error messages) not just the agent. Clear, parseable tool outputs reduce failures.

---

### 4. AgentOps: Enabling Observability (arXiv:2411.05285)

**Core Contribution**: Observability framework for LLM agents.

**Observability Pillars**:
1. **Logging**: Structured logs of all agent actions
2. **Tracing**: End-to-end request tracing
3. **Metrics**: Quantitative performance measures
4. **Alerting**: Automated anomaly detection

**Key Capabilities**:
- Session replay for debugging
- Performance profiling
- Cost tracking
- Error analysis

**Key Insight**: "Large language model (LLM) agents have demonstrated remarkable capabilities across various domains, generating significant interest in deploying them in real-world applications."

**Relevance to CompyMac**: Our TraceStore provides logging and tracing. We should add metrics collection and alerting.

---

### 5. AgentSight: System-Level Observability with eBPF (arXiv:2508.02736)

**Problem**: Semantic gap between high-level intent (LLM prompts) and low-level actions (system calls).

**Solution**: Hybrid observability using eBPF.

**Architecture**:
1. Intercept TLS-encrypted LLM traffic to extract semantic intent
2. Monitor kernel events to observe system-wide effects
3. Causally correlate the two streams
4. Secondary LLM analysis for interpretation

**Key Features**:
- Framework-agnostic
- Less than 3% performance overhead
- Detects prompt injection attacks
- Identifies resource-wasting reasoning loops
- Reveals coordination bottlenecks

**Key Insight**: "This creates a critical semantic gap: existing tools observe either an agent's high-level intent (via LLM prompts) or its low-level actions (e.g., system calls), but cannot correlate these two views."

**Relevance to CompyMac**: We could correlate our high-level traces with system-level observations for deeper debugging.

---

### 6. RAFFLES: Reasoning-based Fault Attribution (arXiv:2509.06822)

**Problem**: Difficult to identify where long-horizon, multi-component LLM systems break down.

**Solution**: Evaluation architecture with reasoning and iterative refinement.

**Architecture**:
- Central Judge for systematic fault investigation
- Specialized Evaluators for specific assessments
- Iterative refinement pipeline

**Key Insight**: "We argue that to match the agentic capabilities, evaluation frameworks must also be able to reason, probe, iterate, and understand the complex logic passing through these systems over long horizons."

**Relevance to CompyMac**: Our Reflector agent could use similar reasoning to identify failure points in execution traces.

---

### 7. Multi-Agent System Failure Analysis (augmentcode.com)

**Production Statistics**:
- 41-86.7% of multi-agent LLM systems fail in production
- 79% of problems from specification and coordination issues
- Only 16% from infrastructure problems

**Root Causes**:
- Specification problems: 41.77%
- Coordination failures: 36.94%
- Infrastructure issues: ~16%

**Key Insight**: "Nearly 79% of problems originate from specification and coordination issues, not technical implementation."

**Relevance to CompyMac**: We should focus on clear specifications and coordination protocols, not just infrastructure reliability.

---

### 8. Enhancing Reliability in AI Inference (arXiv:2511.07424)

**Context**: Microsoft's production LLM inference incidents.

**Methodology**:
- Analyzed 156 high-severity incidents
- Developed taxonomy with Cohen's K ≈ 0.89 consistency

**Findings**:
- ~60% inference engine failures
- ~40% of those are timeouts
- ~74% auto-detected
- ~28% required hotfix

**Mitigation Strategies**:
- Connection liveness checks
- GPU capacity-aware routing
- Per-endpoint isolation

**Relevance to CompyMac**: Timeout handling and capacity-aware routing could improve our tool reliability.

---

## Implications for CompyMac

### Error Envelope Design

Based on the research, our error envelopes should include:

```python
class ToolError:
    """Structured error from tool execution."""
    
    # Classification
    category: ErrorCategory  # model, integration, system, semantic
    severity: Severity       # recoverable, degraded, fatal
    
    # Context
    tool_name: str
    tool_args: dict
    execution_time: float
    
    # Error details
    error_type: str
    error_message: str
    stack_trace: Optional[str]
    
    # Recovery hints
    suggested_actions: List[str]
    retry_eligible: bool
    fallback_available: bool
```

### Recovery Strategies

| Failure Type | Detection | Recovery Strategy |
|--------------|-----------|-------------------|
| Timeout | Execution time exceeded | Retry with longer timeout, or simplify request |
| API Error | HTTP error code | Retry with backoff, or use fallback |
| Parse Error | Invalid output format | Request reformatted output |
| Resource Exhaustion | Memory/token limit | Chunk request, or summarize context |
| Semantic Error | Output doesn't match intent | Clarify request, or try alternative approach |

### Observability Stack

```yaml
observability:
  logging:
    - All tool calls with args and results
    - LLM prompts and completions
    - State transitions
    
  tracing:
    - Request ID propagation
    - Parent-child relationships
    - Timing information
    
  metrics:
    - Tool success/failure rates
    - Latency percentiles
    - Token usage
    - Cost per task
    
  alerting:
    - Failure rate spikes
    - Latency degradation
    - Cost anomalies
```

### Tool Interface Guidelines

Based on Aegis findings, tool interfaces should:

1. **Return Structured Output**: JSON or typed objects, not free text
2. **Include Status Codes**: Clear success/failure indication
3. **Provide Error Context**: Enough information for recovery
4. **Be Idempotent When Possible**: Safe to retry
5. **Have Predictable Latency**: Timeout-friendly

### Failure Injection Testing

```python
class FailureInjector:
    """Inject failures for testing agent resilience."""
    
    def inject_timeout(self, tool: str, probability: float):
        """Randomly timeout tool calls."""
        
    def inject_error(self, tool: str, error_type: str, probability: float):
        """Randomly return errors."""
        
    def inject_malformed_output(self, tool: str, probability: float):
        """Return unparseable output."""
        
    def inject_semantic_error(self, tool: str, probability: float):
        """Return plausible but incorrect output."""
```

---

## Metrics to Track

1. **Tool Success Rate**: Percentage of tool calls that succeed
2. **Recovery Rate**: Percentage of failures that are recovered
3. **Mean Time to Recovery**: How long until agent recovers from failure
4. **Cascading Failure Rate**: How often one failure causes others
5. **False Positive Rate**: How often agent thinks there's an error when there isn't

---

## Open Questions

1. **Semantic Error Detection**: How do we detect when tool output is wrong but well-formed?

2. **Recovery vs Escalation**: When should agent try to recover vs. ask for help?

3. **Failure Prediction**: Can we predict failures before they happen?

4. **Cost of Reliability**: How much overhead is acceptable for reliability?

---

## References

- arXiv:2511.19933 - "Failure Modes in LLM Systems: A System-Level Taxonomy for Reliable AI Applications"
- arXiv:2509.25238 - "PALADIN: Self-Correcting Language Model Agents to Cure Tool-Failure Cases"
- arXiv:2508.19504 - "Aegis: Taxonomy and Optimizations for Overcoming Agent-Environment Failures"
- arXiv:2411.05285 - "AgentOps: Enabling Observability of LLM Agents"
- arXiv:2508.02736 - "AgentSight: System-Level Observability for AI Agents Using eBPF"
- arXiv:2509.06822 - "RAFFLES: Reasoning-based Attribution of Faults for LLM Systems"
- arXiv:2511.07424 - "Enhancing reliability in AI inference services: An empirical study on real production incidents"
