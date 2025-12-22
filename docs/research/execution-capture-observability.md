# Total Execution Capture and Custodial Observability

This document surveys research on complete execution capture, pause/resume capabilities, time-travel debugging, and custodial access patterns for LLM agents. The goal is total visibility into every token, every step, every tool call - stored in a database with the ability to pause, observe overview, and drill into full detail at any point.

## Core Requirements

What we need is NOT "approval gates at key points" but rather:

1. **Total Capture** - Every token generated, every tool call, every intermediate state
2. **Pause/Resume** - Ability to halt execution at any point and resume later
3. **Time Travel** - Navigate backward and forward through execution history
4. **Overview + Detail** - High-level summary view that expands into full detail on demand
5. **Database Storage** - Persistent storage enabling queries, analysis, and replay
6. **Custodial Access** - Complete control over the agent's execution state

## Key Papers and Resources

### 1. AgentOps: Enabling Observability of LLM Agents
**arXiv:** 2411.05285  
**Authors:** Liming Dong, Qinghua Lu, Liming Zhu (CSIRO Data61)  
**Published:** November 2024

**Core Contribution:**
Comprehensive taxonomy of AgentOps identifying artifacts and data that should be traced throughout the entire lifecycle of agents.

**Key Artifacts to Trace:**
- **Agent Workflows** - Complete execution paths and decision trees
- **RAG Pipelines** - Retrieval operations and context assembly
- **Prompt Management** - All prompts sent to LLMs
- **Agent Capabilities** - Tool invocations and results
- **Observability Features** - Metrics, logs, traces

**Lifecycle Coverage:**
- Development phase tracing
- Testing phase tracing
- Production monitoring
- Post-mortem analysis

**Relevance to CompyMac:**
CompyMac's TraceStore already captures spans and events. AgentOps taxonomy suggests we need to expand to cover the full lifecycle, not just execution-time tracing.

---

### 2. Watson: A Cognitive Observability Framework for LLM-Powered Agents
**arXiv:** 2411.03455  
**Authors:** Benjamin Rombaut, Sogol Masoumzadeh, Kirill Vasilevski, Dayi Lin, Ahmed E. Hassan  
**Published:** November 2024

**Core Contribution:**
Framework for observing the *reasoning* of LLM agents, not just their actions.

**Key Concepts:**
- **Cognitive Traces** - Capture the agent's reasoning process, not just outputs
- **Decision Points** - Mark where the agent made choices
- **Confidence Signals** - Track uncertainty in agent decisions
- **Reasoning Chains** - Link thoughts to actions to outcomes

**Relevance to CompyMac:**
CompyMac captures tool calls and results, but Watson suggests we also need to capture the reasoning that led to each decision. The `think` tool is a start, but we need systematic reasoning capture.

---

### 3. AgentRR: Record & Replay for LLM Agents
**arXiv:** 2505.17716  
**Authors:** Erhu Feng et al. (Shanghai Jiao Tong University)  
**Published:** May 2025

**Core Contribution:**
Introduces the classical record-and-replay mechanism into AI agent frameworks.

**Architecture:**
1. **Record** - Capture agent's interaction trace with environment and internal decision process
2. **Summarize** - Convert trace into structured "experience" with workflow and constraints
3. **Replay** - Use experiences to guide agent behavior in similar tasks

**Key Mechanisms:**
- **Multi-level Experience Abstraction** - Balances specificity and generality
- **Check Functions** - Trust anchors ensuring completeness and safety during replay
- **Experience Repository** - Shared storage for reusing experiences

**Application Modes:**
- User-recorded task demonstration
- Large-small model collaboration
- Privacy-aware agent execution

**Relevance to CompyMac:**
AgentRR's record-replay paradigm aligns with our need for total capture. The "experience" abstraction could inform how we summarize execution history for overview views.

---

### 4. Beyond Black-Box Benchmarking: Observability, Analytics, and Optimization
**arXiv:** 2503.06745  
**Authors:** IBM Research  
**Published:** March 2025

**Core Contribution:**
Explores challenges in analyzing agentic systems and proposes taxonomies for analytics outcomes.

**Key Challenges Identified:**
- Natural language variability
- Unpredictable execution flows
- Non-deterministic behavior (79% of users agree this is a major challenge)
- Context-sensitive responses

**Proposed Solution:**
Extend standard observability frameworks (like OpenTelemetry) with agent-specific semantics.

**Relevance to CompyMac:**
CompyMac's TraceStore uses OTel-style spans. This research validates that approach but suggests we need agent-specific extensions for reasoning and decision capture.

---

### 5. Checkpoint/Restore Systems for AI Agents
**Source:** eunomia.dev survey  
**Published:** May 2025

**Core Contribution:**
Comprehensive survey of checkpoint/restore (C/R) technology and its application to AI agents.

**Key Capabilities:**
- **Save State** - Capture complete agent state at any point
- **Resume Execution** - Continue from saved checkpoint
- **Rollback** - Return to previous states
- **Migration** - Move execution between systems
- **Persistence** - Maintain state across sessions

**What to Checkpoint:**
- Message history (all interactions)
- Current execution node
- Input data for current operation
- Timestamp of creation
- Tool state and side effects

**Relevance to CompyMac:**
CompyMac needs checkpoint/restore for pause/resume. This requires capturing not just traces but restorable state.

---

### 6. Time Travel in Agentic AI (LangGraph)
**Source:** LangChain Documentation  
**Published:** 2025

**Core Contribution:**
Practical implementation of time-travel debugging for LLM agents.

**Key Features:**
- **State Snapshots** - Automatic checkpoints at each step
- **Replay from Any Point** - Resume execution from any historical state
- **Branch Exploration** - Fork execution to explore alternatives
- **Human-in-the-Loop** - Pause, inspect, modify, resume

**Implementation Pattern:**
```
1. Every state transition creates a checkpoint
2. Checkpoints are stored with unique IDs
3. User can list all checkpoints
4. User can resume from any checkpoint
5. Resuming creates a new branch of execution
```

**Relevance to CompyMac:**
LangGraph's time-travel is exactly what we need. CompyMac should implement similar checkpoint-based pause/resume with branch exploration.

---

### 7. AgentSight: System-Level Observability Using eBPF
**arXiv:** 2508.02736  
**Authors:** UC Santa Cruz, ShanghaiTech  
**Published:** September 2025

**Core Contribution:**
Bridges the semantic gap between high-level intent (LLM prompts) and low-level actions (system calls).

**Key Innovation:**
- **Boundary Tracing** - Monitor at stable system interfaces using eBPF
- **TLS Interception** - Extract semantic intent from encrypted LLM traffic
- **Causal Correlation** - Link intent to effects across process boundaries
- **Real-time Engine** - Correlate streams as they happen

**Use Cases:**
- Detect prompt injection attacks
- Identify resource-wasting reasoning loops
- Reveal coordination bottlenecks in multi-agent systems

**Relevance to CompyMac:**
AgentSight's approach of correlating high-level intent with low-level effects is valuable. CompyMac should link reasoning traces to actual system effects.

---

### 8. Deterministic Replay for Trustworthy AI Agents
**Source:** Sakura Sky blog series  
**Published:** November 2025

**Core Contribution:**
Argues that deterministic replay is a missing primitive for trustworthy AI agents.

**Key Requirements:**
- **Complete State Capture** - All inputs, outputs, and internal state
- **Deterministic Execution** - Same inputs produce same outputs
- **Audit Trail** - Verifiable record of what happened
- **Reproducibility** - Ability to recreate any execution

**Challenges:**
- Non-determinism in LLM outputs (temperature, sampling)
- External API calls with changing responses
- Time-dependent operations
- Concurrent execution

**Solutions:**
- Record all external inputs (including LLM responses)
- Timestamp all operations
- Capture random seeds
- Serialize concurrent operations

**Relevance to CompyMac:**
For true replay capability, CompyMac needs to capture LLM responses verbatim, not just tool calls. This enables deterministic replay even with non-deterministic LLMs.

---

## Implications for CompyMac

### Current State

CompyMac's TraceStore provides:
- OTel-style spans with parent-child relationships
- Event logging (START, END, ERROR)
- Artifact storage (content-addressed)
- Tool provenance tracking
- PROV-style lineage relations

### What's Missing for Total Custodial Capture

| Requirement | Current State | Gap |
|-------------|---------------|-----|
| Every token captured | Tool outputs captured | LLM responses not fully captured |
| Pause/Resume | No checkpoint system | Need state serialization |
| Time Travel | Traces are append-only | Need checkpoint-based navigation |
| Overview + Detail | Flat event log | Need hierarchical summarization |
| Database Storage | File-based | Need queryable database |
| Custodial Access | Read-only traces | Need pause/modify/resume |

### Recommended Architecture

**Layer 1: Total Capture**
- Capture every LLM request and response (full tokens)
- Capture every tool call with arguments and results
- Capture every state transition
- Capture reasoning/thinking steps
- Timestamp everything with monotonic clock

**Layer 2: Checkpoint System**
- Automatic checkpoints at configurable intervals
- Manual checkpoint triggers (pause button)
- Checkpoint contains: message history, current step, tool state, workspace state
- Checkpoints stored with unique IDs and metadata

**Layer 3: Storage Backend**
- SQLite for local development
- PostgreSQL for production
- Schema supports:
  - Sessions (top-level container)
  - Checkpoints (restorable states)
  - Events (individual operations)
  - Artifacts (large blobs, content-addressed)
  - Summaries (hierarchical rollups)

**Layer 4: Query Interface**
- List all sessions
- List checkpoints for a session
- Get events between checkpoints
- Get summary at any granularity
- Search across sessions

**Layer 5: Control Interface**
- Pause execution (creates checkpoint)
- Resume from checkpoint
- Fork from checkpoint (explore alternatives)
- Rollback to checkpoint
- Modify state and continue

### Implementation Priorities

1. **Capture LLM responses** - Currently missing, critical for replay
2. **Checkpoint serialization** - Define what state needs to be saved
3. **Database schema** - Design queryable storage
4. **Pause/Resume API** - Control interface for operators
5. **Overview generation** - Summarize execution for quick review
6. **Time-travel UI** - Navigate through execution history

### Metrics to Track

- Checkpoint size (bytes)
- Checkpoint frequency (per minute)
- Storage growth rate
- Query latency for common operations
- Resume time from checkpoint
- Replay fidelity (determinism)

## References

1. Dong et al. "AgentOps: Enabling Observability of LLM Agents" (2411.05285)
2. Rombaut et al. "Watson: A Cognitive Observability Framework" (2411.03455)
3. Feng et al. "AgentRR: Record & Replay for LLM Agents" (2505.17716)
4. IBM Research "Beyond Black-Box Benchmarking" (2503.06745)
5. eunomia.dev "Checkpoint/Restore Systems for AI Agents"
6. LangChain "Time Travel in LangGraph"
7. Zheng et al. "AgentSight: System-Level Observability Using eBPF" (2508.02736)
8. Sakura Sky "Deterministic Replay for Trustworthy AI Agents"
