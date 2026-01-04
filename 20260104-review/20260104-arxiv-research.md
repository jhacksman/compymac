# Arxiv Research: AI Agent Techniques That Work (2024-2026)

**Date:** 2026-01-04  
**Purpose:** Survey of academic research on AI agent techniques to inform CompyMac development

---

## Executive Summary

This document surveys recent arxiv papers on AI agent techniques, focusing on what works and what doesn't in real-world software engineering tasks. Key findings include: context management is the primary bottleneck for long-horizon tasks, scaffolding significantly improves reliability, reinforcement learning can train effective multi-turn agents, and verification remains an unsolved challenge. The research strongly supports CompyMac's phase-based workflow and evidence-based gating approaches.

---

## 1. Context Management

### CAT: Context as a Tool (arXiv:2512.22087, Dec 2025)

**Problem:** Most agents use append-only context or passive compression, leading to context explosion, semantic drift, and degraded reasoning in long-running interactions.

**Solution:** CAT (Context as a Tool) elevates context maintenance to a callable tool integrated into the agent's decision-making process.

**Architecture:**
```
┌─────────────────────────────────────────────────────────────┐
│              Structured Context Workspace                   │
├─────────────────────────────────────────────────────────────┤
│  Stable Task Semantics    │  Original goal, constraints    │
│  Condensed Long-term      │  Compressed historical data    │
│  High-fidelity Short-term │  Recent interactions           │
└─────────────────────────────────────────────────────────────┘
```

**Key Innovation:** Agents proactively compress historical trajectories into actionable summaries at appropriate milestones.

**CAT-GENERATOR:** Trajectory-level supervision framework using offline data construction pipeline that injects context-management actions.

**Results:**
- Significant improvement on long-horizon SWE tasks
- Reduced context explosion
- Better semantic coherence across sessions

**Implications for CompyMac:**
- MemoryManager already implements compression, but reactively
- Should add proactive compression as a tool
- Consider milestone-based compression triggers
- Structured workspace aligns with phase-based workflow

---

### Confucius Code Agent: Scalable Agent Scaffolding (arXiv:2512.10398, Dec 2025)

**Problem:** Research-grade agents struggle at scale; production systems lack extensibility and interpretability.

**Solution:** Confucius SDK with three perspectives: Agent Experience (AX), User Experience (UX), Developer Experience (DX).

**Key Components:**

1. **Unified Orchestrator with Hierarchical Working Memory**
   - Long-context reasoning support
   - Memory hierarchy for different time scales

2. **Persistent Note-Taking System**
   - Cross-session continual learning
   - Knowledge accumulation over time

3. **Modular Extension System**
   - Reliable tool use
   - Easy capability addition

4. **Meta-Agent for Configuration**
   - Automates synthesis, evaluation, refinement
   - Build-test-improve loop
   - Rapid adaptation to new tasks

**Results:**
- SWE-Bench-Pro Resolve@1: 54.3%
- Exceeds prior research baselines
- Comparable to commercial systems

**Implications for CompyMac:**
- Hierarchical memory aligns with 3-tier memory design
- Note-taking system similar to KnowledgeStore
- Meta-agent for configuration is novel - could automate prompt tuning

---

## 2. Reinforcement Learning for Agents

### Training Long-Context, Multi-Turn SWE Agents with RL (arXiv:2508.03501, Oct 2025)

**Problem:** Most RL research focuses on single-turn problems (math, single-shot code). Real SWE requires multi-turn interaction with stateful environments.

**Methodology:**

1. **Rejection Fine-Tuning (RFT)**
   - Train policy to follow instructions and formatting
   - Uses execution feedback
   - Baseline: 20% Pass@1

2. **Synchronous RL with DAPO**
   - Iterative improvement
   - Direct Advantage Policy Optimization

**Results:**
- Qwen2.5-72B-Instruct: 11% → 39% Pass@1 on SWE-bench Verified
- SWE-rebench May: 35% Pass@1
- SWE-rebench June: 31% Pass@1
- Competitive with DeepSeek-V3-0324 and Qwen3-235B-A22B

**Key Insight:** RL can effectively train multi-turn agents for interactive tasks using open-weight models.

**Implications for CompyMac:**
- Open-source models can achieve competitive performance with RL
- Qwen 235B (user's preferred model) is viable base
- RFT + RL pipeline could improve CompyMac's model performance
- Execution feedback is critical training signal

---

## 3. Benchmarking and Evaluation

### SWE-Bench Pro: Long-Horizon Software Engineering Tasks (arXiv:2509.16941, Sep 2025)

**Problem:** Existing benchmarks don't capture realistic, complex, enterprise-level problems.

**Dataset:**
- 1,865 problems from 41 repositories
- 123 unique programming languages
- Public set: 11 repositories
- Held-out set: 12 repositories
- Commercial set: 18 proprietary repositories

**Task Characteristics:**
- Long-horizon (hours to days for human engineers)
- Multi-file patches
- Substantial code modifications
- Human-verified and context-augmented

**Evaluation Findings:**
- Current agents struggle with long-horizon tasks
- Multi-file coordination is a major challenge
- Enterprise codebases present unique difficulties

**Implications for CompyMac:**
- SWE-bench Verified is insufficient for production readiness
- Need to evaluate on longer-horizon tasks
- Multi-file coordination is critical capability gap

---

### Beyond Task Completion: Assessment Framework for Agentic AI (arXiv:2512.12791, Dec 2025)

**Problem:** Binary task-completion metrics fail to capture behavioral uncertainty from non-determinism.

**Proposed Dimensions:**
1. Tool invocation capability
2. Memory ingestion and retrieval
3. Agent collaboration
4. Environment interaction effectiveness

**Key Insight:** Evaluating agentic systems requires examining multiple dimensions beyond just "did it work?"

**Implications for CompyMac:**
- Current SWE-bench evaluation is incomplete
- Should add metrics for tool usage patterns
- Memory effectiveness should be measured
- Multi-agent coordination needs evaluation

---

## 4. Verification and Safety

### AgentGuard: Runtime Verification of AI Agents (arXiv:2509.23864, Sep 2025)

**Problem:** Autonomous agents are inherently unpredictable with emergent behaviors. Traditional verification is inadequate.

**Solution:** Dynamic Probabilistic Assurance - continuous, quantitative assurance through runtime verification.

**Architecture:**
```
┌─────────────────────────────────────────────────────────────┐
│                    AgentGuard Framework                     │
├─────────────────────────────────────────────────────────────┤
│  Inspection Layer     │  Observes agent raw I/O            │
│  Event Abstraction    │  Maps to formal state transitions  │
│  MDP Construction     │  Online learning of behavior model │
│  Probabilistic Check  │  Real-time property verification   │
└─────────────────────────────────────────────────────────────┘
```

**Key Innovation:** Uses online learning to dynamically build Markov Decision Process (MDP) modeling agent behavior.

**Implications for CompyMac:**
- TraceStore provides raw I/O observation
- Could add formal state model
- Probabilistic verification is more realistic than binary
- Runtime monitoring aligns with evidence-based gating

---

### VerifiAgent: Unified Verification Agent (arXiv:2504.00406, Apr 2025)

**Problem:** LLMs demonstrate reasoning capabilities but lack verification.

**Solution:** Unified verification agent that validates reasoning steps.

**Approach:**
- Separate verification from generation
- Explicit validation of intermediate steps
- Cross-checking against known facts

**Implications for CompyMac:**
- Verification should be separate from execution
- VerificationEngine is on right track
- Could add reasoning step validation

---

### SAFEFLOW: Trustworthy Autonomous Agent Systems (arXiv:2506.07564, Jun 2025)

**Problem:** Autonomous agents need trustworthy, transactional execution.

**Solution:** Principled protocol for safe agent operation.

**Key Principles:**
1. Transactional semantics (rollback on failure)
2. Trust boundaries between components
3. Audit trails for all actions
4. Approval gates for critical operations

**Implications for CompyMac:**
- TraceStore provides audit trail
- Should add transactional semantics
- Trust boundaries align with phase restrictions
- Approval gates needed for production

---

## 5. Tool Calling and Reliability

### ToolRM and FC-RewardBench (IBM Research, Sep 2025)

**Problem:** Tool-calling reliability is critical bottleneck for AI agents.

**Solution:** Specialized reward model and benchmark for tool-calling evaluation.

**Key Findings:**
- Tool selection errors cascade through execution
- Reward models can improve tool-calling accuracy
- Benchmark enables systematic evaluation

**Implications for CompyMac:**
- Tool selection is critical
- Could add reward model for tool selection
- Need tool-calling benchmark

---

### ToolFuzz: Automated Agent Tool Testing (arXiv:2503.04479, Mar 2025)

**Problem:** Tool documentation is often over-, under-, or ill-specified, impeding agent accuracy.

**Solution:** Automated testing of tool documentation.

**Approach:**
1. Generate diverse natural inputs
2. Detect runtime errors
3. Identify incorrect agent responses
4. Low false positive rate

**Results:**
- Many publicly available tools suffer from underspecification
- ToolFuzz identifies 20x more erroneous inputs than prompt-engineering approaches

**Implications for CompyMac:**
- Tool documentation quality matters
- Should test tool specifications
- Automated testing can find issues

---

### Natural Language Tools (arXiv:2510.14453, Oct 2025)

**Problem:** Programmatic JSON tool calling creates task interference and format constraints.

**Solution:** Replace JSON tool calls with natural language outputs.

**Results:**
- 18.4 percentage point improvement in tool calling accuracy
- 70% reduction in output variance
- Open-weight models see largest gains

**Key Insight:** Decoupling tool selection from response generation eliminates interference.

**Implications for CompyMac:**
- Current JSON tool calling may be suboptimal
- Natural language tool selection worth exploring
- Could improve open-source model performance

---

### OctoTools: Extensible Tools for Complex Reasoning (arXiv:2502.11271, Feb 2025)

**Problem:** Existing tool-augmented agents are restricted to specialized domains or require training.

**Solution:** Training-free, extensible agentic framework.

**Key Components:**

1. **Tool Cards**
   - Define tool-usage metadata
   - Encapsulate tools
   - Training-free integration

2. **Planner**
   - High-level and low-level planning
   - Global objective and step refinement

3. **Executor**
   - Instantiates tool calls
   - Generates executable commands
   - Saves structured results

4. **Task-Specific Toolset Optimization**
   - Learns beneficial tool subsets
   - Adapts to downstream tasks

**Implications for CompyMac:**
- Tool cards similar to RegisteredTool
- Planner aligns with SWEPhaseState
- Toolset optimization could improve tool selection

---

## 6. Agent-Computer Interfaces

### SWE-agent: Agent-Computer Interfaces (NeurIPS 2024)

**Core Thesis:** LM agents need specially-built interfaces, just as humans benefit from IDEs.

**ACI Design Principles:**

1. **Limit Output Length**
   - Prevent context overflow
   - Truncate verbose outputs

2. **Provide Clear Error Messages**
   - Actionable feedback
   - Specific failure reasons

3. **Support Incremental Operations**
   - Small, verifiable steps
   - Undo/redo capabilities

4. **Enable State Inspection**
   - Current file contents
   - Execution state

**Results:**
- SWE-bench Pass@1: 12.5%
- HumanEvalFix: 87.7%
- Interface design significantly impacts performance

**Implications for CompyMac:**
- LocalHarness tool design is critical
- Output truncation already implemented
- Error messages could be improved
- State inspection tools valuable

---

## 7. Comprehensive Surveys

### Benchmarks and Solutions in LLM-Empowered Agentic Systems (arXiv:2510.09721, Oct 2025)

**Taxonomy:**

**Solutions:**
1. Prompt-based paradigms
2. Fine-tuning-based paradigms
3. Agent-based paradigms

**Benchmarks:**
- Code generation
- Code translation
- Code repair

**Evolution:**
- Simple prompt engineering → Sophisticated agentic systems
- Planning, reasoning, memory, tool augmentation

**Unified Pipeline:**
```
Task Specification → Agent Architecture → Tool Use → Evaluation
```

**Key Findings:**
- Agent-based paradigms outperform prompt-only approaches
- Memory mechanisms critical for long-horizon tasks
- Tool augmentation enables real-world capability

**Implications for CompyMac:**
- Agent-based approach is correct direction
- Memory and tools are essential
- Evaluation methodology matters

---

## 8. What Works: Synthesis

Based on the research surveyed, the following techniques have strong empirical support:

### Strongly Supported

1. **Phase-Based Workflows**
   - Prevents runaway execution
   - Enables budget enforcement
   - Supports evidence gating

2. **Context Management**
   - Proactive compression
   - Structured workspaces
   - Milestone-based triggers

3. **Evidence-Based Verification**
   - Test execution as ground truth
   - Exit code validation
   - Regression checking

4. **Hierarchical Memory**
   - Working memory for recent context
   - Episodic memory for session history
   - Long-term memory for facts

5. **Tool Documentation Quality**
   - Clear specifications
   - Error handling
   - Output truncation

### Moderately Supported

6. **Reinforcement Learning**
   - RFT + RL improves performance
   - Execution feedback as reward
   - Works with open-source models

7. **Multi-Agent Coordination**
   - Planner/Executor separation
   - Specialized agents for subtasks
   - Parallel exploration

8. **Runtime Verification**
   - Probabilistic assurance
   - Continuous monitoring
   - Formal state models

### Emerging/Uncertain

9. **Natural Language Tool Calling**
   - Promising results
   - Needs more validation
   - May improve open-source models

10. **Meta-Agent Configuration**
    - Automated prompt tuning
    - Build-test-improve loops
    - Limited production evidence

---

## 9. What Doesn't Work: Anti-Patterns

### Documented Failures

1. **Append-Only Context Without Compression**
   - Context explosion
   - Semantic drift
   - Degraded reasoning

2. **Dynamic Tool Addition/Removal**
   - KV-cache invalidation
   - Model confusion
   - Better to mask

3. **Binary Task Completion Metrics**
   - Miss behavioral uncertainty
   - Don't capture partial success
   - Need multi-dimensional evaluation

4. **Single-Shot Approaches**
   - Insufficient for complex tasks
   - No error recovery
   - No learning from failures

5. **Hardcoded Constraints**
   - Maintenance burden
   - Inflexible
   - Better in prompts

---

## 10. Research Gaps

### Unsolved Problems

1. **Long-Horizon Reliability**
   - Agents degrade over many steps
   - Error accumulation
   - Context drift

2. **Ambiguous Requirements**
   - All agents struggle
   - Need clarification mechanisms
   - Human-in-the-loop helps

3. **Multi-File Coordination**
   - Complex dependencies
   - Consistency maintenance
   - Atomic changes

4. **Verification at Scale**
   - Test generation is hard
   - Coverage is incomplete
   - Regression detection

5. **Cost Optimization**
   - Token efficiency
   - Model selection
   - Caching strategies

---

## 11. Recommendations for CompyMac

### Based on Strong Evidence

1. **Implement Proactive Context Compression**
   - Add compress_context as callable tool
   - Trigger at phase boundaries
   - Preserve critical information

2. **Add Milestone-Based Checkpointing**
   - Checkpoint at phase transitions
   - Enable rollback on failure
   - Support resume from checkpoint

3. **Improve Tool Documentation**
   - Test tool specifications
   - Add clear error messages
   - Truncate verbose outputs

4. **Enhance Verification**
   - Add probabilistic assurance
   - Continuous monitoring
   - Formal state tracking

### Based on Moderate Evidence

5. **Explore RL Training**
   - RFT on execution feedback
   - DAPO for improvement
   - Target Qwen 235B

6. **Add Meta-Agent Configuration**
   - Automated prompt tuning
   - Build-test-improve loop
   - Task-specific optimization

### Based on Emerging Research

7. **Experiment with Natural Language Tools**
   - Decouple selection from response
   - May improve open-source models
   - Needs validation

---

## References

1. Liu et al. "Context as a Tool: Context Management for Long-Horizon SWE-Agents." arXiv:2512.22087, Dec 2025.
2. Wang et al. "Confucius Code Agent: Scalable Agent Scaffolding for Real-World Codebases." arXiv:2512.10398, Dec 2025.
3. Golubev et al. "Training Long-Context, Multi-Turn Software Engineering Agents with Reinforcement Learning." arXiv:2508.03501, Oct 2025.
4. Deng et al. "SWE-Bench Pro: Can AI Agents Solve Long-Horizon Software Engineering Tasks?" arXiv:2509.16941, Sep 2025.
5. Akshathala et al. "Beyond Task Completion: An Assessment Framework for Evaluating Agentic AI Systems." arXiv:2512.12791, Dec 2025.
6. Koohestani. "AgentGuard: Runtime Verification of AI Agents." arXiv:2509.23864, Sep 2025.
7. Han et al. "VerifiAgent: a Unified Verification Agent in Language Model Reasoning." arXiv:2504.00406, Apr 2025.
8. Li et al. "SAFEFLOW: A Principled Protocol for Trustworthy and Transactional Autonomous Agent Systems." arXiv:2506.07564, Jun 2025.
9. Milev et al. "ToolFuzz - Automated Agent Tool Testing." arXiv:2503.04479, Mar 2025.
10. Johnson et al. "Natural Language Tools: A Natural Language Approach to Tool Calling." arXiv:2510.14453, Oct 2025.
11. Lu et al. "OctoTools: An Agentic Framework with Extensible Tools for Complex Reasoning." arXiv:2502.11271, Feb 2025.
12. Yang et al. "SWE-agent: Agent-Computer Interfaces Enable Automated Software Engineering." NeurIPS 2024.
13. Guo et al. "A Comprehensive Survey on Benchmarks and Solutions in Software Engineering of LLM-Empowered Agentic System." arXiv:2510.09721, Oct 2025.
