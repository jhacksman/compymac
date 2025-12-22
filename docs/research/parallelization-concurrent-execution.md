# Parallelization and Concurrent Execution in LLM Agents

This document surveys research on parallel and concurrent execution strategies for LLM-based agents, focusing on techniques that can improve latency, throughput, and task completion rates.

## Key Papers

### 1. M1-Parallel: Optimizing Sequential Multi-Step Tasks with Parallel LLM Agents
**arXiv:** 2507.08944  
**Authors:** Enhao Zhang, Erkang (Eric) Zhu, Gagan Bansal, Adam Fourney, Hussein Mozannar, Jack Gerrits  
**Published:** July 2025

**Core Contribution:**
Framework that concurrently runs multiple multi-agent teams in parallel to uncover distinct solution paths, using event-driven communication with asynchronous messaging.

**Key Findings:**
- M1-Parallel with early termination achieves up to 2.2x speedup while preserving accuracy
- M1-Parallel with aggregation yields higher task completion rates
- Strategies aimed at encouraging diverse execution plans showed no additional performance gains over repeated sampling
- Leverages inherent diversity of valid plans to reduce end-to-end latency

**Relevance to CompyMac:**
CompyMac's `ParallelStepExecutor` implements a similar concept at the plan step level. The M1-Parallel finding about early termination suggests CompyMac could benefit from a "first successful rollout wins" strategy in `RolloutOrchestrator`.

---

### 2. GAP: Graph-based Agent Planning with Parallel Tool Use and Reinforcement Learning
**arXiv:** 2510.25320  
**Authors:** Jiaqi Wu, Qinlao Zhao, Zefeng Chen, Kai Qin, Yifei Zhao, Xueqian Wang, Yuhang Yao  
**Published:** October 2025

**Core Contribution:**
Framework that explicitly models inter-task dependencies through graph-based planning to enable adaptive parallel and serial tool execution.

**Architecture:**
- Trains agent foundation models to decompose complex tasks into dependency-aware sub-task graphs
- Autonomously determines which tools can be executed in parallel vs sequential
- Two-stage training: supervised fine-tuning (SFT) followed by reinforcement learning (RL) with correctness-based reward

**Key Findings:**
- Dependency-aware orchestration achieves substantial improvements in both execution efficiency and task accuracy
- Significantly outperforms traditional ReAct baselines on multi-step retrieval tasks
- Graph structure enables principled parallelization decisions

**Relevance to CompyMac:**
CompyMac's `PlanValidator.find_parallel_groups()` already identifies parallelizable steps based on dependencies. GAP suggests this could be enhanced with learned dependency prediction rather than explicit `can_parallelize` flags.

---

### 3. Parallelism Meets Adaptiveness: Scalable Documents Understanding in Multi-Agent LLM Systems
**arXiv:** 2507.17061  
**Authors:** Chengxuan Xia, Qianye Wu, Sixuan Tian, Yilun Hao  
**Published:** July 2025

**Core Contribution:**
Coordination framework enabling adaptiveness through dynamic task routing, bidirectional feedback, and parallel agent evaluation.

**Key Mechanisms:**
1. **Dynamic task routing** - Agents reallocate tasks based on confidence and workload
2. **Bidirectional feedback** - Structured critiques to iteratively improve outputs
3. **Parallel agent evaluation** - Competing agents on high-ambiguity subtasks with evaluator-driven selection

**Key Findings:**
- Substantial improvements in factual coverage, coherence, and efficiency over static baselines
- Structured competition in multi-agent systems improves output quality
- Adaptiveness is key - static workflows underperform

**Relevance to CompyMac:**
CompyMac's multi-agent architecture (Manager/Planner/Executor/Reflector) is currently static. This research suggests adding dynamic task routing based on executor confidence scores and parallel competing executors for ambiguous steps.

---

### 4. Hogwild! Inference: Parallel LLM Generation via Concurrent Attention
**arXiv:** 2504.06261  
**Authors:** Gleb Rodionov, Roman Garipov, Alina Shutova, George Yakushev, Vage Egiazarian, Anton Sinitsin, Denis Kuznedelev, Dan Alistarh  
**Published:** April 2025

**Core Contribution:**
Parallel LLM inference engine where multiple instances run with a shared, concurrently-updated attention cache, allowing "instant" access to each other's generated tokens.

**Architecture:**
- Multiple LLM "workers" run in parallel with same attention cache
- Workers synchronize via concurrently-updated cache
- Uses Rotary Position Embeddings (RoPE) to avoid recomputation
- Workers decide how to collaborate based on problem at hand

**Key Findings:**
- Allows instances to develop their own collaboration strategy
- Workers can "see" each other's partial progress in concurrent cache
- Effective for tasks requiring exploration of multiple strategies

**Relevance to CompyMac:**
This is a lower-level optimization than CompyMac currently targets (CompyMac uses Venice.ai API). However, if self-hosting models in the future, Hogwild! inference could enable more efficient parallel rollouts.

---

### 5. LLM-Tool Compiler for Fused Parallel Function Calling
**Authors:** Simranjit Singh, Andreas Karatzas, Michael Fore, Iraklis Anagnostopoulos, Dimitrios Stamoulis  
**Published:** 2024

**Core Contribution:**
Compiler that selectively fuses similar types of tool operations under a single function at runtime, presenting them as a unified task to the LLM.

**Key Findings:**
- Increases parallel calls by up to 5x when integrated with various prompting schemes
- Inspired by hardware multiply-add (MAD) operations that fuse multiple arithmetic operations
- Reduces round-trips to GPT APIs by batching similar operations

**Relevance to CompyMac:**
CompyMac's `ToolConflictModel.partition_by_conflicts()` groups non-conflicting tools for parallel execution. The LLM-Tool Compiler suggests an additional optimization: fusing similar tool calls (e.g., multiple file reads) into batch operations.

---

### 6. Parallelized Planning-Acting for Efficient LLM-based Multi-Agent Systems
**arXiv:** 2503.03505  
**Authors:** Yaoru Li, Shunyu Liu, Tongya Zheng, Mingli Song  
**Published:** March 2025

**Core Contribution:**
Framework that parallelizes planning and acting phases in multi-agent systems, rather than the traditional sequential plan-then-act approach.

**Key Findings:**
- Overlapping planning and execution reduces total latency
- Speculative execution of likely next steps while planning continues
- Requires careful rollback mechanisms for incorrect speculations

**Relevance to CompyMac:**
CompyMac's `ManagerAgent` currently follows sequential states (PLANNING -> EXECUTING -> REFLECTING). This research suggests overlapping these phases - starting execution of early plan steps while later steps are still being planned.

---

### 7. DynTaskMAS: Dynamic Task Graph-driven Framework for Asynchronous and Parallel LLM-based Multi-Agent Systems
**arXiv:** 2503.07675  
**Published:** March 2025

**Core Contribution:**
Framework using dynamic task graphs for asynchronous and parallel execution in multi-agent systems.

**Architecture:**
- Tasks represented as nodes in a dynamic graph
- Edges represent dependencies
- Graph updates as execution progresses
- Asynchronous execution of ready tasks

**Key Findings:**
- Dynamic graphs adapt better than static plans
- Asynchronous execution improves resource utilization
- Task graph visualization aids debugging

**Relevance to CompyMac:**
CompyMac's `PlanStep.dependencies` field enables static dependency graphs. DynTaskMAS suggests making this dynamic - updating dependencies as execution reveals new information.

---

### 8. Flash-Searcher: Fast and Effective Web Agents via DAG-Based Parallel Execution
**arXiv:** 2509.25301  
**Published:** September 2025

**Core Contribution:**
Web agent framework using Directed Acyclic Graphs (DAGs) for parallel execution of web search and browsing tasks.

**Key Findings:**
- DAG structure naturally captures search dependencies
- Parallel execution of independent search branches
- Significant speedup for multi-hop question answering

**Relevance to CompyMac:**
CompyMac's browser tools currently execute sequentially. For multi-tab workflows, a DAG-based approach could enable parallel page loads and data extraction.

---

## Implications for CompyMac

### Current CompyMac Parallelization Capabilities

CompyMac already has sophisticated parallel execution support in `parallel.py`:

1. **ForkedTraceContext** - Independent span stacks for parallel workers sharing trace_store/trace_id
2. **ToolConflictModel** - Classifies tools as PARALLEL_SAFE vs EXCLUSIVE with resource-based locking
3. **ParallelExecutor** - ThreadPoolExecutor-based parallel tool execution with conflict partitioning
4. **ParallelStepExecutor** - Parallel plan step execution for multi-agent workflows
5. **JoinSpan** - Fan-in aggregation for parallel results with proper trace linking

### Recommended Enhancements Based on Research

| Research Finding | Current CompyMac State | Enhancement Opportunity |
|-----------------|----------------------|------------------------|
| Early termination (M1-Parallel) | RolloutOrchestrator runs all rollouts | Add "first success wins" mode |
| Graph-based dependencies (GAP) | Static `can_parallelize` flags | Learn dependency prediction |
| Dynamic task routing | Static agent roles | Add confidence-based routing |
| Parallel agent competition | Single executor per step | Competing executors for ambiguous steps |
| Tool fusion (LLM-Tool Compiler) | Individual tool calls | Batch similar operations |
| Overlapping plan-act | Sequential FSM states | Speculative execution |
| Dynamic task graphs | Static plan steps | Update dependencies during execution |

### Implementation Priorities

**High Priority (Immediate Impact):**
1. Early termination in `RolloutOrchestrator` - Simple change, 2.2x potential speedup
2. Tool call batching for similar operations (multiple reads, multiple greps)

**Medium Priority (Architecture Changes):**
3. Dynamic dependency updates during execution
4. Confidence-based task routing between executors

**Lower Priority (Future Work):**
5. Learned dependency prediction (requires training data)
6. Parallel competing executors (increases cost)
7. Speculative execution with rollback (complex state management)

### Metrics to Track

- **Latency reduction**: Wall-clock time for task completion
- **Parallelization ratio**: Concurrent tool calls / total tool calls
- **Speculation accuracy**: Correct speculative executions / total speculations
- **Resource utilization**: Active workers / max workers over time

## References

1. Zhang et al. "Optimizing Sequential Multi-Step Tasks with Parallel LLM Agents" (2507.08944)
2. Wu et al. "GAP: Graph-based Agent Planning with Parallel Tool Use and Reinforcement Learning" (2510.25320)
3. Xia et al. "Parallelism Meets Adaptiveness: Scalable Documents Understanding in Multi-Agent LLM Systems" (2507.17061)
4. Rodionov et al. "Hogwild! Inference: Parallel LLM Generation via Concurrent Attention" (2504.06261)
5. Singh et al. "An LLM-Tool Compiler for Fused Parallel Function Calling"
6. Li et al. "Parallelized Planning-Acting for Efficient LLM-based Multi-Agent Systems" (2503.03505)
7. "DynTaskMAS: Dynamic Task Graph-driven Framework for Asynchronous and Parallel LLM-based Multi-Agent Systems" (2503.07675)
8. "Flash-Searcher: Fast and Effective Web Agents via DAG-Based Parallel Execution" (2509.25301)
