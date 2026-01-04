# CompyMac Feature Roadmap: Prioritized Recommendations

**Date:** 2026-01-04  
**Purpose:** Prioritized feature recommendations based on competitive analysis and arxiv research

---

## Executive Summary

This roadmap synthesizes findings from competitor analysis (Devin, Manus, Claude Code, SWE-agent, AutoCodeRover, Cursor) and arxiv research on agent techniques. Features are ranked by impact on reliability and successful outcomes, with consideration for implementation effort and CompyMac's current state.

CompyMac is further along than expected, with strong foundations in phase-based workflows, evidence-based gating, and observability. The primary gaps are in context engineering (KV-cache optimization), human interaction (interrupt/resume), and production hardening (verification, safety).

---

## Priority Tiers

### Tier 1: Critical (Do First)
High impact on reliability, relatively low effort, validated by multiple sources

### Tier 2: Important (Do Soon)
Significant impact, moderate effort, strong evidence base

### Tier 3: Valuable (Do Later)
Good impact, higher effort or less certain evidence

### Tier 4: Exploratory (Research)
Promising but needs validation, or high effort with uncertain payoff

---

## Tier 1: Critical Features

### 1.1 KV-Cache Optimization

**Priority:** #1  
**Impact:** 10x cost reduction, significant latency improvement  
**Effort:** Low-Medium  
**Evidence:** Manus blog (explicit), all production agents (implicit)

**Problem:** Every token change in the prompt prefix invalidates the KV-cache, forcing full recomputation. With Claude Sonnet, cached tokens cost $0.30/MTok vs $3.00/MTok uncached.

**Current State:** CompyMac's prompt assembly doesn't explicitly optimize for cache stability.

**Implementation:**

1. **Stabilize Prompt Prefix**
   - Move all static content (identity, invariants, security, tools) to front
   - Remove any dynamic content from prefix (timestamps, session IDs)
   - Add explicit cache breakpoint marker after stable prefix

2. **Ensure Deterministic Serialization**
   - Audit JSON serialization for stable key ordering
   - Use `json.dumps(obj, sort_keys=True)` everywhere
   - Test that identical inputs produce identical outputs

3. **Make Context Append-Only**
   - Never modify previous messages or tool results
   - Only append new content
   - Compress old content rather than editing

**Files to Modify:**
- `src/compymac/prompts/assembly.py` - Add cache breakpoint, reorder sections
- `src/compymac/session.py` - Ensure append-only behavior
- `src/compymac/llm.py` - Add cache hit rate logging

**Validation:**
- Log cache hit rates before/after
- Measure cost reduction
- Track latency improvements

---

### 1.2 Tool Masking (Replace Removal)

**Priority:** #2  
**Impact:** Prevents KV-cache invalidation, improves model understanding  
**Effort:** Low  
**Evidence:** Manus blog (explicit), leaked prompts (implicit)

**Problem:** Dynamically adding/removing tools invalidates KV-cache because tool definitions are serialized near the front of context.

**Current State:** ActiveToolset enables/disables tools, which may remove them from context.

**Implementation:**

1. **Always Include All Tools**
   - Keep full tool definitions in every request
   - Never remove tools from schema

2. **Add Availability Markers**
   - Add `available: bool` field to tool definitions
   - Add `unavailable_reason: str` for masked tools
   - Example: "Currently unavailable: Not in FIX phase"

3. **Update Tool Selection Logic**
   - Model sees all tools but knows which are available
   - Clearer error messages for unavailable tool attempts

**Files to Modify:**
- `src/compymac/local_harness.py` - Modify tool schema generation
- `src/compymac/prompts/tools/` - Add availability markers

**Validation:**
- Verify cache hit rates improve
- Test that model respects availability markers
- Check error handling for unavailable tools

---

### 1.3 Human Interrupt/Resume

**Priority:** #3  
**Impact:** Critical for reliability and user trust  
**Effort:** Medium  
**Evidence:** Devin (core feature), Claude Code (supported), user requirement

**Problem:** Long-running agents need human oversight and intervention capability.

**Current State:** TraceStore has checkpoint infrastructure, but no user-facing interrupt mechanism.

**Implementation:**

1. **Checkpoint at Phase Boundaries**
   - Automatic checkpoint when advancing phases
   - Store complete state (session, phase, evidence)
   - Enable resume from any checkpoint

2. **User Interrupt Signal**
   - Add interrupt tool/signal
   - Graceful pause at next safe point
   - Preserve state for resume

3. **Plan Review Interface**
   - Show current plan/phase to user
   - Allow plan modification before resume
   - Support "skip to phase" commands

**Files to Modify:**
- `src/compymac/swe_workflow.py` - Add checkpoint triggers
- `src/compymac/agent_loop.py` - Add interrupt handling
- `src/compymac/api/server.py` - Add interrupt/resume endpoints

**Validation:**
- Test interrupt at various points
- Verify state preservation
- Test resume correctness

---

### 1.4 File-Based Memory for Long Sessions

**Priority:** #4  
**Impact:** Enables long-horizon tasks without context overflow  
**Effort:** Low-Medium  
**Evidence:** Manus (core technique), CAT paper (validated)

**Problem:** Context window limits prevent maintaining full history for long sessions.

**Current State:** MemoryManager compresses to facts, but doesn't use filesystem.

**Implementation:**

1. **Scratchpad Files**
   - Create `.compymac/scratchpad/` directory
   - Write intermediate results to files
   - Reference files in context instead of inline content

2. **Todo File Tracking**
   - Maintain `.compymac/todo.md` for task state
   - Update on phase transitions
   - Include in context as reference

3. **Observation Compression**
   - Write verbose tool outputs to files
   - Include summary + file reference in context
   - Enable "read more" pattern

**Files to Modify:**
- `src/compymac/memory.py` - Add file-based storage
- `src/compymac/local_harness.py` - Add scratchpad tools
- `src/compymac/swe_workflow.py` - Add todo file updates

**Validation:**
- Test on long-horizon tasks
- Measure context utilization
- Verify information retrieval

---

## Tier 2: Important Features

### 2.1 Proactive Context Compression Tool

**Priority:** #5  
**Impact:** Prevents context explosion, maintains coherence  
**Effort:** Medium  
**Evidence:** CAT paper (strong), Confucius paper (supporting)

**Problem:** Reactive compression (when context is full) loses information. Proactive compression at milestones preserves critical data.

**Current State:** MemoryManager compresses reactively at 80% utilization.

**Implementation:**

1. **Add compress_context Tool**
   - Callable by agent at appropriate moments
   - Compresses specified range of history
   - Preserves critical information

2. **Milestone-Based Triggers**
   - Suggest compression at phase boundaries
   - Prompt agent to compress after complex operations
   - Track compression history

3. **Structured Compression Output**
   - Stable task semantics (goal, constraints)
   - Condensed long-term memory (facts, decisions)
   - High-fidelity short-term (recent actions)

**Files to Modify:**
- `src/compymac/memory.py` - Add proactive compression
- `src/compymac/local_harness.py` - Register compress tool
- `src/compymac/swe_workflow.py` - Add compression prompts

---

### 2.2 Enhanced Error Messages

**Priority:** #6  
**Impact:** Reduces error recovery time, improves reliability  
**Effort:** Low  
**Evidence:** SWE-agent paper (explicit), ToolFuzz paper (supporting)

**Problem:** Generic error messages don't help agents recover.

**Current State:** Tool errors return raw exception messages.

**Implementation:**

1. **Structured Error Format**
   ```python
   {
     "error_type": "FileNotFound",
     "message": "File '/path/to/file' does not exist",
     "suggestion": "Use glob or grep to find the correct path",
     "related_files": ["/path/to/similar_file"]
   }
   ```

2. **Recovery Suggestions**
   - Add actionable suggestions to each error type
   - Include relevant context (similar files, recent commands)
   - Suggest alternative approaches

3. **Error Categorization**
   - Recoverable vs fatal errors
   - User-fixable vs agent-fixable
   - Transient vs permanent

**Files to Modify:**
- `src/compymac/local_harness.py` - Enhance error handling
- `src/compymac/verification.py` - Add error categorization

---

### 2.3 Output Truncation Strategy

**Priority:** #7  
**Impact:** Prevents context overflow from verbose outputs  
**Effort:** Low  
**Evidence:** SWE-agent paper (explicit), all production agents (implicit)

**Problem:** Verbose tool outputs (large files, long command outputs) consume context.

**Current State:** Some truncation exists but not systematic.

**Implementation:**

1. **Configurable Limits**
   - Per-tool output limits
   - Global output budget
   - Priority-based allocation

2. **Smart Truncation**
   - Keep head and tail for logs
   - Keep relevant sections for code
   - Summarize rather than truncate when possible

3. **Overflow Handling**
   - Write full output to file
   - Return summary + file reference
   - Enable "show more" pattern

**Files to Modify:**
- `src/compymac/local_harness.py` - Add truncation logic
- `src/compymac/config.py` - Add truncation config

---

### 2.4 Sub-Agent Spawning

**Priority:** #8  
**Impact:** Enables parallel exploration, specialized subtasks  
**Effort:** Medium-High  
**Evidence:** Claude Code (core feature), Confucius paper (supporting)

**Problem:** Single agent can't explore multiple approaches or delegate specialized work.

**Current State:** Multi-agent system exists but not integrated with main loop.

**Implementation:**

1. **spawn_agent Tool**
   - Create sub-agent with specific goal
   - Isolated context and tools
   - Returns result to parent

2. **Parallel Exploration**
   - Spawn multiple agents for different approaches
   - Compare results
   - Select best outcome

3. **Specialized Delegation**
   - Test-writing sub-agent
   - Documentation sub-agent
   - Review sub-agent

**Files to Modify:**
- `src/compymac/multi_agent.py` - Add spawn capability
- `src/compymac/local_harness.py` - Register spawn tool
- `src/compymac/parallel.py` - Add sub-agent coordination

---

## Tier 3: Valuable Features

### 3.1 Project-Specific Configuration (CLAUDE.md equivalent)

**Priority:** #9  
**Impact:** Better project understanding, customization  
**Effort:** Low  
**Evidence:** Claude Code (core feature), Cursor (similar)

**Implementation:**
- Read `.compymac/config.md` from project root
- Include in system prompt
- Support project-specific rules and context

---

### 3.2 Probabilistic Verification

**Priority:** #10  
**Impact:** More realistic assurance than binary pass/fail  
**Effort:** Medium  
**Evidence:** AgentGuard paper (strong)

**Implementation:**
- Build MDP model of agent behavior
- Calculate probability of success/failure
- Continuous monitoring during execution

---

### 3.3 Documentation Generation (DeepWiki equivalent)

**Priority:** #11  
**Impact:** High-value feature for enterprise adoption  
**Effort:** Medium-High  
**Evidence:** Devin (core feature, high usage)

**Implementation:**
- Codebase analysis and documentation
- Architecture diagrams
- API documentation generation

---

### 3.4 Hybrid LLM + Program Analysis

**Priority:** #12  
**Impact:** Better fault localization, more reliable fixes  
**Effort:** High  
**Evidence:** AutoCodeRover (core approach)

**Implementation:**
- Integrate AST parsing
- Add coverage-based localization
- Combine LLM reasoning with static analysis

---

## Tier 4: Exploratory Features

### 4.1 Natural Language Tool Calling

**Priority:** #13  
**Impact:** May improve open-source model performance  
**Effort:** Medium  
**Evidence:** NLT paper (promising but needs validation)

**Research Questions:**
- Does decoupling selection from response help?
- How does it affect Qwen 235B specifically?
- What's the latency impact?

---

### 4.2 RL Training Pipeline

**Priority:** #14  
**Impact:** Could significantly improve model performance  
**Effort:** Very High  
**Evidence:** Nebius paper (strong results)

**Research Questions:**
- Can we apply RFT + DAPO to Qwen 235B?
- What training data do we need?
- What infrastructure is required?

---

### 4.3 Meta-Agent Configuration

**Priority:** #15  
**Impact:** Automated prompt optimization  
**Effort:** High  
**Evidence:** Confucius paper (promising)

**Research Questions:**
- Can we automate prompt tuning?
- What's the build-test-improve loop?
- How do we measure improvement?

---

### 4.4 Multi-Model Orchestration

**Priority:** #16  
**Impact:** Cost optimization, capability matching  
**Effort:** High  
**Evidence:** Manus (uses multiple models)

**Research Questions:**
- Which tasks benefit from which models?
- How do we route dynamically?
- What's the latency/cost tradeoff?

---

## Implementation Paths

Based on user priorities, here are three recommended paths:

### Path A: Reliability Focus

**Goal:** Maximize successful task completion rate

**Sequence:**
1. KV-Cache Optimization (#1.1)
2. Tool Masking (#1.2)
3. Human Interrupt/Resume (#1.3)
4. Enhanced Error Messages (#2.2)
5. Proactive Context Compression (#2.1)

**Timeline:** 2-3 weeks  
**Expected Impact:** 30-50% improvement in task completion

---

### Path B: Scale Focus

**Goal:** Enable long-horizon, complex tasks

**Sequence:**
1. File-Based Memory (#1.4)
2. Proactive Context Compression (#2.1)
3. Output Truncation (#2.3)
4. Sub-Agent Spawning (#2.4)
5. KV-Cache Optimization (#1.1)

**Timeline:** 3-4 weeks  
**Expected Impact:** Enable 10x longer task horizons

---

### Path C: Production Focus

**Goal:** Enterprise-ready deployment

**Sequence:**
1. Human Interrupt/Resume (#1.3)
2. KV-Cache Optimization (#1.1)
3. Project Configuration (#3.1)
4. Probabilistic Verification (#3.2)
5. Documentation Generation (#3.3)

**Timeline:** 4-6 weeks  
**Expected Impact:** Production-ready for enterprise use

---

## Quick Wins (< 1 day each)

These can be done immediately with minimal risk:

1. **Add cache breakpoint marker** to prompt assembly
2. **Ensure deterministic JSON serialization** with sort_keys=True
3. **Add availability field** to tool schemas
4. **Improve error messages** for common failures
5. **Add output truncation** for verbose tools

---

## Metrics to Track

### Reliability Metrics
- Task completion rate (overall, by phase)
- Error recovery rate
- Regression rate (pass-to-pass failures)

### Efficiency Metrics
- KV-cache hit rate
- Token usage per task
- Cost per successful task
- Time to completion

### Quality Metrics
- Patch correctness (SWE-bench)
- Test coverage of fixes
- Human intervention rate

---

## Dependencies and Risks

### Dependencies
- KV-cache optimization depends on LLM provider support
- Sub-agent spawning depends on multi-agent system maturity
- RL training depends on infrastructure and data

### Risks
- Tool masking may confuse some models
- File-based memory adds filesystem complexity
- Sub-agents increase cost and latency

### Mitigations
- A/B test changes before full rollout
- Add feature flags for new capabilities
- Monitor metrics closely during rollout

---

## Conclusion

CompyMac has strong foundations that align with industry best practices. The primary gaps are in context engineering and human interaction, both of which are addressable with moderate effort. The recommended starting point is Path A (Reliability Focus), beginning with KV-cache optimization and tool masking, as these provide the highest impact with lowest risk.

The research strongly validates CompyMac's phase-based workflow and evidence-based gating approaches. These should be preserved and enhanced rather than replaced. The main additions needed are around context management (proactive compression, file-based memory) and human oversight (interrupt/resume, plan review).

For the user's goal of using open-source models (Qwen 235B) with fallback to closed models (Grok), the natural language tool calling research (Tier 4) is worth exploring, as it showed the largest gains for open-weight models.
