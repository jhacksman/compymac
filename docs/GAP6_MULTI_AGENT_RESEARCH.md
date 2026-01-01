# Gap 6: Multi-Agent Orchestration Research

## Executive Summary

Gap 6 addresses multi-agent orchestration - the ability to coordinate multiple specialized agents working together on complex tasks. This research document synthesizes findings from 15+ arxiv papers and competitive analysis of Manus/Devin to inform CompyMac's implementation strategy.

**Key Finding:** CompyMac already has substantial multi-agent infrastructure (Manager/Planner/Executor/Reflector pattern, parallel execution, workspace isolation, hypothesis arbiter). Gap 6 should focus on **inter-agent communication protocols** and **structured artifact handoffs** rather than building from scratch.

**Top 3 Architecture Recommendations:**
1. **Hierarchical Orchestrator + Specialized Sub-Agents** (AgentOrchestra-style) - composes cleanly with existing Gap 3 SWE loop
2. **SOP-Style Structured Outputs** (MetaGPT) - artifact-based handoffs reduce cascading hallucinations
3. **Shared Blackboard Pattern** - use existing ArtifactStore for inter-agent communication

**What Manus/Devin Appear to Do:**
- Cloud-based virtual computing environment with full tool access
- Iterative agent loop: analyze → plan → execute → observe
- File-based memory for progress tracking across operations
- Heavy context engineering (KV-cache optimization, append-only context)
- Multi-model dynamic invocation (Claude for reasoning, GPT-4 for coding, Gemini for knowledge)

---

## 1. Problem Definition and Success Criteria

### What "Multi-Agent Orchestration" Means Operationally

Multi-agent orchestration involves coordinating multiple LLM-powered agents, each with specialized roles, to collaboratively solve complex tasks. Key components include:

1. **Role Specialization**: Agents with distinct responsibilities (planner, coder, tester, reviewer)
2. **Concurrency**: Parallel execution of independent subtasks
3. **Structured Communication**: Typed messages and artifact handoffs between agents
4. **Shared State**: Common workspace/blackboard for coordination
5. **Conflict Resolution**: Mechanisms to resolve disagreements between agents
6. **Verification and Handoff**: Quality gates before passing work between agents

### Success Criteria for CompyMac

| Metric | Target | Rationale |
|--------|--------|-----------|
| Loop stall reduction | 50% fewer stalls | Multi-agent should reduce single-point-of-failure loops |
| Task success rate | +15% on multi-step tasks | Specialized agents should improve complex task handling |
| Parallel exploration | 2-4x hypothesis throughput | Already have ParallelHypothesisExecutor, need better coordination |
| Token efficiency | <20% overhead | Multi-agent shouldn't explode context costs |
| Human intervention rate | -30% | Better self-correction through agent cross-checking |

---

## 2. Taxonomy of Orchestration Patterns

### 2.1 Assembly-Line / SOP-Driven Pipelines (MetaGPT)

**Source:** arXiv:2308.00352 - "MetaGPT: Meta Programming for a Multi-Agent Collaborative Framework"

**Architecture:**
- Encodes Standardized Operating Procedures (SOPs) into prompt sequences
- Assembly line paradigm: each agent produces structured artifacts for the next
- Roles: Product Manager → Architect → Project Manager → Engineer → QA Engineer

**Key Mechanisms:**
- **Structured outputs**: Each agent produces typed artifacts (PRD, system design, task list, code, test report)
- **Verification gates**: Intermediate results are validated before passing downstream
- **Role isolation**: Each agent has a focused system prompt and tool set

**What It Improves:**
- Reduces cascading hallucinations (errors don't propagate unchecked)
- Clear accountability (each agent owns specific artifacts)
- Predictable workflow (deterministic stage progression)

**Costs:**
- Higher latency (sequential stages)
- Rigid structure (hard to adapt mid-task)
- Token overhead (~30-50% more than single agent)

**Failure Modes:**
- Bottleneck at any stage blocks entire pipeline
- Early-stage errors compound if not caught
- Over-specification can constrain creative solutions

**CompyMac Relevance:** HIGH - Our Gap 3 SWEWorkflow already has stage-based progression. MetaGPT's SOP pattern can inform how we structure inter-stage handoffs.

---

### 2.2 Chat-Chain / Deliberative Communication (ChatDev)

**Source:** arXiv:2307.07924 - "ChatDev: Communicative Agents for Software Development"

**Architecture:**
- Agents communicate through structured "chat chains"
- "Communicative dehallucination" - agents challenge each other's outputs
- Roles engage in multi-turn dialogues to refine solutions

**Key Mechanisms:**
- **Chat chain**: Predefined conversation structure (who talks to whom, in what order)
- **Instructor-Assistant pattern**: One agent guides, another executes
- **Self-reflection**: Agents review their own outputs before handoff

**What It Improves:**
- Natural language is advantageous for system design
- Programming language proves helpful in debugging
- Encourages divergent thinking through debate

**Costs:**
- High token usage (multi-turn conversations)
- Latency from back-and-forth exchanges
- Risk of infinite loops in debates

**Failure Modes:**
- Agents can agree on wrong answers (groupthink)
- Debates can stall without resolution
- Communication overhead scales poorly with agent count

**CompyMac Relevance:** MEDIUM - The Reflector agent in our multi_agent.py already provides some cross-checking. ChatDev's dehallucination patterns could enhance this.

---

### 2.3 Hierarchical Planner-Worker (AgentOrchestra / TEA Protocol)

**Source:** arXiv:2506.12508 - "AgentOrchestra: Orchestrating Hierarchical Multi-Agent Intelligence with the TEA Protocol"

**Architecture:**
- Central planning agent decomposes objectives and coordinates specialized agents
- TEA Protocol: Tool-Environment-Agent as first-class resources
- Sub-agents: Deep Researcher, Browser Use, Deep Analyzer, Tool Manager

**Key Mechanisms:**
- **Hierarchical decomposition**: Planner breaks complex goals into sub-tasks
- **Capability-based routing**: Tasks routed to agents based on their capabilities
- **Tool Manager Agent**: Dynamic tool creation, retrieval, and reuse
- **Environment encapsulation**: Each agent has defined environment access

**What It Improves:**
- 83.39% on GAIA benchmark (state-of-the-art)
- Clean separation of concerns
- Scalable to many specialized agents

**Costs:**
- Planner becomes single point of failure
- Coordination overhead for simple tasks
- Requires careful capability definitions

**Failure Modes:**
- Planner bottleneck with weak LLM
- Sub-optimal task decomposition
- Agent capability mismatch

**CompyMac Relevance:** HIGH - This maps well to our existing ManagerAgent + specialized agents pattern. The TEA Protocol's environment encapsulation aligns with our WorkspaceIsolation.

---

### 2.4 Adaptive/Dynamic Orchestration (Evolving Orchestration "Puppeteer")

**Source:** arXiv:2505.19591 - "Multi-Agent Collaboration via Evolving Orchestration"

**Architecture:**
- Centralized orchestrator ("puppeteer") dynamically directs agents ("puppets")
- Orchestrator trained via reinforcement learning
- Adaptive sequencing based on task state

**Key Mechanisms:**
- **RL-trained routing**: Orchestrator learns optimal agent sequencing
- **Dynamic adaptation**: Routing changes based on intermediate results
- **Cyclic reasoning structures**: Emergent patterns from RL training

**What It Improves:**
- Superior performance with reduced computational costs
- Adapts to task complexity dynamically
- Discovers efficient reasoning patterns

**Costs:**
- Requires RL training infrastructure
- Training data collection overhead
- Less interpretable decisions

**Failure Modes:**
- RL training instability
- Distribution shift in deployment
- Overfitting to training tasks

**CompyMac Relevance:** LOW (for now) - The RL training burden is not worth it early. However, the insight that "dynamic routing helps" is valuable. We can implement lightweight heuristics first.

---

### 2.5 Agile-Role Alignment (ALMAS)

**Source:** arXiv:2510.03463 - "ALMAS: an Autonomous LLM-based Multi-Agent Software Engineering Framework"

**Architecture:**
- Agents aligned with agile software development roles
- Modular integration with human developers
- End-to-end SDLC coverage

**Key Mechanisms:**
- **Role mapping**: Product Owner, Scrum Master, Developer, Tester
- **Sprint-based execution**: Work organized into iterations
- **Human-in-the-loop**: Seamless handoff to human developers

**What It Improves:**
- Natural fit for existing development workflows
- Clear responsibility boundaries
- Supports incremental delivery

**Costs:**
- Overhead of agile ceremonies
- May be overkill for simple tasks
- Requires understanding of agile concepts

**CompyMac Relevance:** MEDIUM - The role alignment concept is useful, but we don't need full agile ceremony overhead. The key insight is mapping agents to familiar developer roles.

---

## 3. Core Mechanisms That Work (Cross-Paper Synthesis)

Based on analysis of 15+ papers and Manus architecture, these mechanisms consistently improve multi-agent performance:

### 3.1 Standardized Intermediate Artifacts

**Pattern:** Each agent produces typed, structured outputs that serve as inputs to downstream agents.

**Evidence:**
- MetaGPT: PRD → System Design → Task List → Code → Tests
- Manus: Plan events, Knowledge events, Data events in context
- AgentOrchestra: Capability cards, task specifications

**Implementation for CompyMac:**
```
Artifact Types:
- ProblemStatement: Structured understanding of the issue
- Plan: Ordered steps with dependencies and parallelization hints
- FileTargets: List of files to modify with rationale
- PatchPlan: Specific changes per file in search-replace format
- TestPlan: Tests to run and expected outcomes
- FailureAnalysis: Structured error analysis with suggested fixes
- PRDescription: Summary of changes for review
```

**Why It Works:** Structured artifacts prevent drift, enable verification, and provide clear handoff points.

---

### 3.2 Explicit Task Decomposition + Progress Tracking

**Pattern:** A planner module breaks high-level goals into ordered steps with status tracking.

**Evidence:**
- Manus: Planner module generates enumerated steps with status
- MetaGPT: Task decomposition with dependency tracking
- Our multi_agent.py: PlanStep with dependencies, priority, can_parallelize

**Implementation for CompyMac:**
Already implemented in `multi_agent.py`:
```python
@dataclass
class PlanStep:
    index: int
    description: str
    expected_outcome: str
    tools_hint: list[str]
    dependencies: list[int]
    priority: int
    can_parallelize: bool
    estimated_complexity: str
```

**Enhancement Needed:** Better integration with Gap 3 SWEWorkflow stages.

---

### 3.3 Verification Loops and Cross-Checking

**Pattern:** Reviewer/tester roles verify outputs before handoff, gated by objective signals.

**Evidence:**
- ChatDev: Communicative dehallucination
- MetaGPT: QA Engineer role
- Our multi_agent.py: ReflectorAgent

**Implementation for CompyMac:**
Already implemented:
```python
class ReflectorAgent(BaseAgent):
    """Reviews results and suggests improvements or replanning."""
    
class ReflectionAction(Enum):
    CONTINUE = "continue"
    RETRY_SAME = "retry_same"
    RETRY_WITH_CHANGES = "retry_with_changes"
    GATHER_INFO = "gather_info"
    REPLAN = "replan"
    COMPLETE = "complete"
    STOP = "stop"
```

**Enhancement Needed:** Gate verification with objective signals (test failures, lint errors, uncertainty scores) to control cost.

---

### 3.4 Context Management as First-Class Constraint

**Pattern:** Treat context as an engineering budget with explicit optimization.

**Evidence (Manus Blog):**
- **KV-cache hit rate** is the single most important metric for production agents
- Keep prompt prefix stable (avoid timestamps at start)
- Make context append-only (don't modify previous actions/observations)
- Mark cache breakpoints explicitly
- **Mask tools, don't remove** - dynamic tool changes kill cache

**Implementation for CompyMac:**
```python
# Context engineering principles:
1. Stable system prompt prefix (no timestamps)
2. Append-only event log
3. Pass artifact pointers, not full content
4. Tool masking instead of removal
5. Explicit cache breakpoints for long sessions
```

**Why It Works:** With Claude Sonnet, cached tokens cost 0.30 USD/MTok vs 3 USD/MTok uncached - 10x difference.

---

### 3.5 Tool/Environment Encapsulation

**Pattern:** Each agent has defined boundaries for what tools/environments it can access.

**Evidence:**
- AgentOrchestra TEA Protocol: Environments as first-class resources
- Manus: Sandboxed Ubuntu environment with explicit tool access
- Our parallel.py: ToolConflictModel with resource locks

**Implementation for CompyMac:**
Already implemented:
```python
class ToolConflictModel:
    DEFAULT_CLASSES = {
        "Read": ConflictClass.PARALLEL_SAFE,
        "Write": ConflictClass.EXCLUSIVE,
        "Bash": ConflictClass.EXCLUSIVE,
        "browser.*": ConflictClass.EXCLUSIVE,
    }
```

**Enhancement Needed:** Per-agent tool allowlists to enforce role boundaries.

---

## 4. What Manus Does (Best-Effort from Public Sources)

**Sources:** Manus technical report (GitHub Gist), Manus blog on context engineering

### Architecture

1. **Foundation Model Backbone:**
   - Claude 3.5/3.7 Sonnet as primary reasoning engine
   - Alibaba Qwen for supplementary tasks
   - Multi-model dynamic invocation (different models for different sub-tasks)

2. **Cloud Agent with Tool Sandbox:**
   - Full Ubuntu Linux workspace in the cloud
   - Shell (with sudo), web browser, file system, Python/Node interpreters
   - Continues working even if user's device is off

3. **Agent Loop:**
   - Analyze → Plan → Execute → Observe (iterative)
   - One tool action per iteration (await result before next step)
   - Event stream tracks all interactions

4. **Planner Module:**
   - Breaks high-level objectives into ordered steps
   - Plan injected as "Plan" event in context
   - Can be updated on the fly

5. **Knowledge Module:**
   - Provides reference information from knowledge base
   - Appears as "Knowledge" events in context

6. **File-Based Memory:**
   - Progress tracked in files for persistence
   - Enables cross-session continuity

### Context Engineering (from Manus Blog)

1. **Design Around KV-Cache:**
   - Input-to-output ratio ~100:1 in agents
   - Cache hit rate is critical for cost/latency
   - Keep prefix stable, context append-only

2. **Mask, Don't Remove:**
   - Dynamic tool changes break cache
   - Mask unavailable tools instead of removing
   - Constrain via system prompt, not tool list changes

3. **Append-Only Context:**
   - Never modify previous actions/observations
   - Deterministic serialization (stable JSON key ordering)

---

## 5. What Devin Does (Inferred Patterns)

**Note:** Limited public technical details available. These are inferred patterns from product behavior and general SWE-agent research.

### Inferred Architecture

1. **Background Execution:**
   - Tasks continue running without user presence
   - Persistent workspace across sessions

2. **Multiple Internal Roles:**
   - Planning, coding, testing, debugging capabilities
   - Likely specialized prompts/modes rather than separate agents

3. **Tight Tool Loop:**
   - Rapid iteration between code changes and test execution
   - Automated feedback from linters, tests, builds

4. **Artifact Persistence:**
   - Code changes, test results, logs preserved
   - Enables review and debugging

5. **Human Handoff:**
   - Clear points for human review (PR creation)
   - Ability to pause and resume

---

## 6. Design Recommendations for CompyMac

### Recommended Architecture

Based on the research, CompyMac should adopt a **Hierarchical Orchestrator + Specialized Sub-Agents** pattern that builds on existing infrastructure:

```
┌─────────────────────────────────────────────────────────────┐
│                    Orchestrator (Manager)                    │
│  - Task decomposition                                        │
│  - Agent routing based on capabilities                       │
│  - Progress tracking                                         │
│  - Conflict resolution                                       │
└─────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        ▼                     ▼                     ▼
┌───────────────┐    ┌───────────────┐    ┌───────────────┐
│   Planner     │    │   Coder       │    │   Reviewer    │
│   Agent       │    │   Agent       │    │   Agent       │
│               │    │               │    │               │
│ - Understand  │    │ - Locate      │    │ - Validate    │
│ - Plan        │    │ - Modify      │    │ - Debug       │
│ - Decompose   │    │ - Implement   │    │ - Verify      │
└───────────────┘    └───────────────┘    └───────────────┘
        │                     │                     │
        └─────────────────────┼─────────────────────┘
                              ▼
                    ┌───────────────────┐
                    │   ArtifactStore   │
                    │   (Blackboard)    │
                    │                   │
                    │ - Shared state    │
                    │ - Typed artifacts │
                    │ - History         │
                    └───────────────────┘
```

### Specific Recommendations

#### 6.1 Use SOP-Style Structured Outputs Between Agents

**Rationale:** MetaGPT shows that artifact-based handoffs reduce cascading hallucinations.

**Implementation:**
```python
class AgentArtifact(Enum):
    PROBLEM_STATEMENT = "problem_statement"
    EXECUTION_PLAN = "execution_plan"
    FILE_TARGETS = "file_targets"
    PATCH_PLAN = "patch_plan"
    TEST_PLAN = "test_plan"
    FAILURE_ANALYSIS = "failure_analysis"
    PR_DESCRIPTION = "pr_description"

@dataclass
class StructuredHandoff:
    from_agent: AgentRole
    to_agent: AgentRole
    artifact_type: AgentArtifact
    content: dict[str, Any]
    validation_passed: bool
```

#### 6.2 Make Reviewer/Verifier a First-Class Sub-Agent

**Rationale:** ChatDev/MetaGPT show cross-checking reduces errors.

**Implementation:**
- Gate verification with objective signals (tests failing, lint failing, uncertainty)
- Don't verify every step (cost control)
- Trigger verification on: stage transitions, error recovery, before PR

#### 6.3 Treat Context as Engineering Budget

**Rationale:** Manus shows 10x cost difference between cached/uncached tokens.

**Implementation:**
```python
class ContextBudget:
    max_tokens: int = 128000
    cache_prefix_tokens: int = 0
    
    def should_summarize(self) -> bool:
        return self.current_tokens > self.max_tokens * 0.8
    
    def get_cache_hit_rate(self) -> float:
        return self.cache_prefix_tokens / self.current_tokens
```

#### 6.4 Keep Inter-Agent Communication Minimal and Structured

**Rationale:** Avoid "chatty" debates that explode token usage.

**Implementation:**
- Shared blackboard (ArtifactStore) + short typed messages
- No multi-turn debates between agents
- Pass artifact pointers, not full content

#### 6.5 Design for Future Protocol Compatibility

**Rationale:** MCP/A2A/ACP/ANP are emerging standards for agent interoperability.

**Implementation:**
- Internal agent messaging should be protocol-agnostic
- Design interfaces that could map to A2A Agent Cards
- Keep tool definitions MCP-compatible

---

## 7. Implementation Roadmap (Phased)

### Phase 0: Single-Process Multi-Agent with Shared Artifact Store (CURRENT STATE)

**What We Have:**
- `multi_agent.py`: Manager, Planner, Executor, Reflector agents
- `parallel.py`: ParallelExecutor, WorkspaceIsolation, HypothesisArbiter
- `workflows/artifact_store.py`: Artifact storage and retrieval
- `workflows/swe_loop.py`: SWEWorkflow state machine

**Gap:** Agents don't communicate through structured artifacts; they share raw workspace state.

### Phase 1: Structured Artifact Handoffs

**Goal:** Implement SOP-style structured outputs between agents.

**Tasks:**
1. Define AgentArtifact types for each handoff point
2. Modify ManagerAgent to route based on artifact types
3. Add validation gates between stages
4. Integrate with ArtifactStore for persistence

**Success Metric:** Artifact-based handoffs reduce error propagation by 30%.

### Phase 2: Parallel Workstreams with Merge/Review

**Goal:** Enable parallel hypothesis exploration with intelligent merging.

**Tasks:**
1. Enhance ParallelHypothesisExecutor with structured result comparison
2. Add HypothesisArbiter integration with Reviewer agent
3. Implement workspace merge strategies (git-based)
4. Add conflict detection and resolution

**Success Metric:** 2x hypothesis throughput with <10% merge conflicts.

### Phase 3: Dynamic Orchestration Heuristics

**Goal:** Lightweight dynamic routing without RL training.

**Tasks:**
1. Implement capability-based agent routing
2. Add task complexity estimation
3. Create routing heuristics based on task type
4. Add feedback loop to improve routing over time

**Success Metric:** 20% reduction in unnecessary agent invocations.

### Phase 4: Interoperability Protocols (Future)

**Goal:** Support external agents/tools via standard protocols.

**Tasks:**
1. Implement MCP server for tool exposure
2. Add A2A Agent Card generation
3. Create protocol adapters for external agents
4. Add discovery and capability negotiation

**Success Metric:** Successfully integrate with at least one external MCP/A2A agent.

---

## 8. Evaluation Plan

### Ablation Studies

| Configuration | Description |
|---------------|-------------|
| Single-agent baseline | Current AgentLoop without multi-agent |
| Multi-agent (no artifacts) | Manager + agents, raw state sharing |
| Multi-agent (with artifacts) | Full structured handoffs |
| Multi-agent (parallel) | With parallel hypothesis exploration |

### Task Categories Where Multi-Agent Helps

1. **Ambiguous bugs**: Multiple hypotheses benefit from parallel exploration
2. **Broad refactors**: Specialized agents for different file types
3. **Multi-step features**: Clear handoffs between planning and implementation
4. **Complex debugging**: Reviewer agent catches issues early

### Metrics

| Metric | Measurement |
|--------|-------------|
| Success rate | % of tasks completed correctly |
| Iterations | Number of agent loop iterations |
| Wall time | Total time to completion |
| Tool calls | Number of tool invocations |
| Token usage | Total tokens consumed |
| Human interventions | Number of times human input needed |
| Error propagation | % of errors caught before downstream stages |

---

## 9. References

### Primary Papers

1. **MetaGPT** (arXiv:2308.00352) - Meta Programming for Multi-Agent Collaborative Framework
2. **ChatDev** (arXiv:2307.07924) - Communicative Agents for Software Development
3. **AgentOrchestra** (arXiv:2506.12508) - TEA Protocol for Hierarchical Multi-Agent Intelligence
4. **ALMAS** (arXiv:2510.03463) - Autonomous LLM-based Multi-Agent Software Engineering
5. **Evolving Orchestration** (arXiv:2505.19591) - Puppeteer Paradigm for Multi-Agent Collaboration
6. **LMA Systems Survey** (arXiv:2404.04834) - Literature Review for SE Applications
7. **Agent Protocols Survey** (arXiv:2505.02279) - MCP, A2A, ACP, ANP Comparison
8. **MAGIS** (arXiv:2403.17927) - Multi-Agent Framework for GitHub Issue Resolution
9. **Cross-Team Orchestration** (arXiv:2406.08979) - Multi-Agent Software Development
10. **HyperAgent** (arXiv:2409.16299) - Generalist Software Engineering Agents
11. **OpenHands** (arXiv:2407.16741) - Open Platform for AI Software Developers
12. **RTADev** (ACL 2025) - Intention Aligned Multi-Agent Framework
13. **Think-on-Process** (arXiv:2409.06568) - Dynamic Process Generation
14. **Anemoi** (arXiv:2508.17068) - Semi-Centralized Multi-Agent with A2A MCP
15. **MCP x A2A Framework** (arXiv:2506.01804) - Enhancing Agent Interoperability

### Industry Sources

- Manus Technical Report (GitHub Gist: renschni/Manus_report.md)
- Manus Blog: "Context Engineering for AI Agents"
- Devin product documentation and public demos

---

## 10. Appendix: Existing CompyMac Multi-Agent Infrastructure

### multi_agent.py (1435 lines)

**Classes:**
- `AgentRole`: MANAGER, PLANNER, EXECUTOR, REFLECTOR
- `ManagerState`: FSM states (INITIAL → PLANNING → EXECUTING → REFLECTING → REPLANNING → COMPLETED/FAILED)
- `PlanStep`: Step with dependencies, priority, parallelization hints
- `StepResult`: Execution result with artifacts and errors
- `ReflectionAction`: CONTINUE, RETRY_SAME, RETRY_WITH_CHANGES, GATHER_INFO, REPLAN, COMPLETE, STOP
- `Workspace`: Shared state between agents
- `PlanValidator`: Dependency validation, parallel group detection
- `BaseAgent`: LLM chat capabilities
- `PlannerAgent`: Creates and revises plans
- `ReflectorAgent`: Reviews results, suggests improvements
- `ExecutorAgent`: Executes steps using AgentLoop
- `ManagerAgent`: FSM orchestrator

### parallel.py (1143 lines)

**Classes:**
- `ConflictClass`: PARALLEL_SAFE, EXCLUSIVE
- `ForkedTraceContext`: Independent span stacks for parallel workers
- `ToolConflictModel`: Tool conflict classification
- `ParallelExecutor`: ThreadPoolExecutor-based parallel tool execution
- `JoinSpan`: Aggregates parallel results
- `ParallelStepExecutor`: Parallel plan step execution
- `WorkspaceIsolation`: Git worktree-based isolation
- `HypothesisResult`: Result of hypothesis execution
- `HypothesisArbiter`: Selects best hypothesis (consensus or LLM judge)
- `ParallelHypothesisExecutor`: Executes multiple hypotheses in parallel

### workflows/artifact_store.py (423 lines)

**Classes:**
- `ArtifactType`: CODE_DIFF, TEST_OUTPUT, ERROR_ANALYSIS, PLAN, NOTE, etc.
- `Artifact`: Typed artifact with metadata
- `ArtifactStore`: Storage and retrieval with indexing by stage/type

---

*Document created: 2025-12-27*
*Last updated: 2025-12-27*
*Author: Devin AI*
*Session: https://app.devin.ai/sessions/234de3dfe246485287aecc3462c7ff8e*
