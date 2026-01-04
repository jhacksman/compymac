# CompyMac Implementation Roadmap
## 12-Month Technical Plan (2026)

**Date:** January 4, 2026
**Timeline:** Q1 2026 - Q4 2026
**Team Size:** 2-3 engineers
**Budget:** $200K-300K (salaries + compute)

---

## Overview

This roadmap transforms CompyMac from a research prototype to a production-ready autonomous coding agent through four strategic priorities:

1. **Activate Existing Infrastructure** (Q1 2026)
2. **Hybrid Memory System** (Q1-Q2 2026)
3. **Tool Ecosystem Enhancement** (Q2-Q3 2026)
4. **Long-Horizon Reasoning** (Q3-Q4 2026)

---

## Q1 2026: Foundation (Weeks 1-13)

### Priority 1A: Activate Multi-Agent Orchestration
**Duration:** 3 weeks
**Owner:** Senior Engineer
**Dependencies:** None

**Current State:**
- `multi_agent.py`: 1,508 lines of unused code
- Four-agent architecture implemented but dormant
- AgentLoop is current execution path

**Tasks:**

**Week 1: Configuration + Routing**
- [ ] Add `EXECUTION_MODE` config: `"single"` | `"multi_agent"`
- [ ] Create routing logic: simple tasks → AgentLoop, complex → ManagerAgent
- [ ] Define complexity heuristics:
  - Multi-file changes → complex
  - >50 tool budget → complex
  - Requires planning → complex
- [ ] **Deliverable:** Config-driven execution mode selection

**Week 2: Agent Initialization + Testing**
- [ ] Wire ManagerAgent into main entry point
- [ ] Pass TraceStore, MemoryManager, Harness to all agents
- [ ] Unit tests for agent coordination
- [ ] Integration test: One complex SWE-bench task
- [ ] **Deliverable:** Working multi-agent execution on 1 task

**Week 3: Evaluation + Rollout**
- [ ] A/B test: 20 tasks with AgentLoop vs ManagerAgent
- [ ] Measure: success rate, steps taken, tool calls, latency
- [ ] Fix bugs found during testing
- [ ] **Deliverable:** Decision to enable multi-agent by default

**Success Criteria:**
- Multi-agent mode completes ≥1 complex task successfully
- No regressions on simple tasks
- Code path fully tested

---

### Priority 1B: Activate Memory Retrieval
**Duration:** 2 weeks
**Owner:** Mid-Level Engineer
**Dependencies:** None

**Current State:**
- MemoryManager extracts facts but never retrieves them
- KnowledgeStore exists with hybrid retrieval
- ContextManager doesn't query memories

**Tasks:**

**Week 1: Integration**
- [ ] Modify `ContextManager.build_context()`:
  - Query KnowledgeStore for relevant facts
  - Allocate 4K tokens for memory summary
  - Inject before recent turns
- [ ] Wire MemoryManager fact extraction to KnowledgeStore:
  - Extract facts from tool outputs
  - Store in KnowledgeStore with embeddings
  - Update retrieval stats
- [ ] **Deliverable:** Memory injection in context

**Week 2: Testing + Tuning**
- [ ] Test on long tasks (>50 turns)
- [ ] Measure fact recall accuracy
- [ ] Tune top-k parameter (default: 10)
- [ ] **Deliverable:** Evaluation report

**Success Criteria:**
- Facts retrieved and injected in context
- Recall accuracy >70% on synthetic queries
- No significant latency increase (<50ms overhead)

---

### Priority 1C: Metacognitive Reflection Loop
**Duration:** 3 weeks
**Owner:** Senior Engineer
**Dependencies:** Priority 1A (multi-agent)

**Current State:**
- `thinking_events` tracked but never analyzed
- No learning from failures
- No strategy adaptation

**Tasks:**

**Week 1: Design + Failure Detection**
- [ ] Design reflection trigger points:
  - After phase failure (SWE-bench)
  - After tool error (bash exit_code != 0)
  - After budget exhaustion
  - Manual trigger via `reflect` tool
- [ ] Implement failure detection:
  - Parse error messages
  - Extract failure patterns
  - **Deliverable:** Failure taxonomy

**Week 2: Reflection Agent**
- [ ] Create `ReflectorAgent` subclass (or enhance existing)
- [ ] Reflection prompt:
  - Input: Recent trajectory, error, context
  - Output: Root cause, alternative strategies, learned heuristic
- [ ] Store reflections in KnowledgeStore as "lessons_learned" entities
- [ ] **Deliverable:** Working reflection agent

**Week 3: Integration + Learning**
- [ ] Wire reflection into ManagerAgent failure handling
- [ ] Query past reflections when similar failure occurs
- [ ] Inject learned heuristics into planner prompt
- [ ] **Deliverable:** Reflection loop integrated

**Success Criteria:**
- Reflection triggered on failures
- Learned heuristics stored and retrieved
- Demonstrable improvement on repeated failure patterns

---

### Priority 1D: Modularize LocalHarness
**Duration:** 2 weeks
**Owner:** Mid-Level Engineer
**Dependencies:** None (can run in parallel)

**Current State:**
- `local_harness.py`: 6,449 lines (26% of codebase)
- Monolithic file, hard to maintain
- All 50+ tools in one place

**Tasks:**

**Week 1: Module Design + Scaffolding**
- [ ] Design module structure:
  ```
  src/compymac/tools/
    ├── __init__.py
    ├── core.py (Read, Write, Edit, bash)
    ├── git.py (git_* tools)
    ├── browser.py (browser_* tools)
    ├── search.py (web_search, web_get_contents)
    ├── lsp.py (lsp_tool)
    ├── todo.py (Todo* tools)
    ├── ai.py (ask_smart_friend, visual_checker)
    └── registry.py (tool registration logic)
  ```
- [ ] Create module files with stubs
- [ ] **Deliverable:** Module scaffolding

**Week 2: Migration + Testing**
- [ ] Move tool implementations to modules
- [ ] Update imports in `local_harness.py` (becomes thin wrapper)
- [ ] Run full test suite
- [ ] Fix broken imports/dependencies
- [ ] **Deliverable:** Modularized tools, all tests passing

**Success Criteria:**
- No file >2000 lines
- All tools working (no regressions)
- Clear module boundaries

---

### Q1 Summary
**Duration:** 10 weeks total (some parallel work)
**Deliverables:**
- Multi-agent orchestration activated
- Memory retrieval integrated
- Metacognitive reflection loop working
- Modularized tool system

**Outcomes:**
- Improved task success rate (estimated +10-15%)
- Better code maintainability
- Foundation for Q2 work

---

## Q2 2026: Memory System (Weeks 14-26)

### Priority 2A: Graph-Based Short-Term Memory
**Duration:** 6 weeks
**Owner:** Senior Engineer
**Dependencies:** Priority 1B (memory retrieval)

**Tasks:**

**Week 1-2: Schema + Database**
- [ ] Design entity/relation schema (see MEMORY_ARCHITECTURE doc)
- [ ] Implement `GraphMemoryStore` class:
  - `add_entity(entity)`, `add_relation(relation)`
  - `get_entity(entity_id)`, `get_relations(filters)`
  - `query(seed_entities, max_hops, relation_types)`
- [ ] Create SQLite tables with indexes
- [ ] **Deliverable:** Graph database layer

**Week 3-4: Fact Extraction**
- [ ] Implement extraction rules for top 10 tools:
  - Read → File entity
  - Edit → Modifies relation
  - Bash (error) → Error entity
  - grep → Function/Class entities
  - git_diff → Modifies relation
- [ ] Real-time extraction: hook into tool result processing
- [ ] Unit tests for each extraction rule
- [ ] **Deliverable:** Automated fact extraction

**Week 5: Query Engine**
- [ ] Implement multi-hop graph traversal (BFS)
- [ ] Implement hybrid query (vector search + graph expansion)
- [ ] Benchmark query performance (<100ms target)
- [ ] **Deliverable:** Query API

**Week 6: Integration + Evaluation**
- [ ] Wire MemoryManager → GraphMemoryStore
- [ ] Wire ContextManager → graph queries
- [ ] Test on 10 SWE-bench tasks
- [ ] Measure: fact extraction accuracy, query recall, latency
- [ ] **Deliverable:** Evaluation report + decision to merge

**Success Criteria:**
- Facts extracted from 90%+ of tool outputs
- Query recall >80% for relevant entities
- Query latency <100ms (95th percentile)
- Graph supports 10K+ entities without slowdown

---

### Priority 2B: Latent Compression (Long-Term Memory)
**Duration:** 6 weeks
**Owner:** ML Engineer (can overlap with 2A)
**Dependencies:** Priority 2A (graph memory)

**Tasks:**

**Week 1-2: Model Setup**
- [ ] Deploy Qwen 7B Q4 with vLLM
- [ ] Memory budget profiling (ensure <4GB)
- [ ] Design compression prompts (see MEMORY_ARCHITECTURE doc)
- [ ] Implement `LatentCompressor` class:
  - `compress_phase(phase_name, messages)`
  - `decompress(compressed_id, detail_level)`
  - `search(query_text, top_k)`
- [ ] **Deliverable:** Compression model API

**Week 3-4: Phase Compression**
- [ ] Hook into SWE workflow phase transitions
- [ ] Compress LOCALIZATION, UNDERSTANDING outputs automatically
- [ ] Store compressed representations in SQLite
- [ ] Create compression quality metrics:
  - Token reduction ratio
  - Information preservation (synthetic Q&A)
- [ ] **Deliverable:** Automated phase compression

**Week 5: Retrieval + Decompression**
- [ ] Implement search over compressed memories (vector sim)
- [ ] Integrate with ContextManager (query when needed)
- [ ] Test decompression levels (summary, findings, full, original)
- [ ] **Deliverable:** Retrieval working

**Week 6: Evaluation**
- [ ] A/B test: baseline vs graph vs graph+compression
- [ ] Metrics:
  - Context truncation rate (should drop 80%)
  - Fact recall accuracy
  - Task success rate
  - Storage efficiency (compression ratios)
- [ ] **Deliverable:** Performance report + decision to productionize

**Success Criteria:**
- Compression ratio: 10x or better
- Information preservation: >85% Q&A accuracy
- Compression latency: <5s per phase
- Retrieval latency: <500ms

---

### Q2 Summary
**Duration:** 10 weeks (some parallel work)
**Deliverables:**
- Graph-based short-term memory operational
- Latent compression for long-term memory
- Full hybrid memory system integrated

**Outcomes:**
- 80% reduction in context truncation
- Support for multi-hour tasks
- Improved long-horizon task success rate

---

## Q3 2026: Tool Optimization (Weeks 27-39)

### Priority 3A: Codebase Indexing (Devin-Style)
**Duration:** 8 weeks
**Owner:** Senior Engineer
**Dependencies:** Priority 2A (graph memory)

**Tasks:**

**Week 1-2: Design + Indexing Strategy**
- [ ] Research DeepWiki approach (Devin)
- [ ] Design index schema:
  - Module/file structure
  - Import graphs
  - Function/class definitions
  - Call graphs
  - Documentation snippets
- [ ] Choose indexing tool: LSP + tree-sitter + custom
- [ ] **Deliverable:** Design doc

**Week 3-5: Index Builder**
- [ ] Implement `CodebaseIndexer` class:
  - `index_repository(repo_path)`
  - `update_index(changed_files)` (incremental)
  - `query_index(query, index_type)` (structure, definitions, calls, docs)
- [ ] Parse Python, JavaScript, TypeScript, Go, Rust
- [ ] Build call graphs, import graphs
- [ ] Extract docstrings, comments
- [ ] **Deliverable:** Indexing engine

**Week 6-7: Semantic Search Integration**
- [ ] Replace grep with semantic code search:
  - Query natural language: "find the function that handles authentication"
  - Return ranked results with context
- [ ] Index embeddings (function/class summaries)
- [ ] Hybrid search: keyword + semantic + graph
- [ ] **Deliverable:** Semantic code search API

**Week 8: Integration + Testing**
- [ ] Add `codebase_search` tool to harness
- [ ] Wire into SWE workflow (LOCALIZATION phase)
- [ ] A/B test: grep vs semantic search
- [ ] Measure: precision, recall, latency
- [ ] **Deliverable:** Evaluation report

**Success Criteria:**
- Index 100K LOC repository in <5 minutes
- Incremental updates in <10 seconds
- Search precision >80%, recall >70%
- Query latency <500ms

---

### Priority 3B: Confidence Scoring (Devin-Style)
**Duration:** 4 weeks
**Owner:** ML Engineer
**Dependencies:** None

**Tasks:**

**Week 1-2: Design + Metrics**
- [ ] Research uncertainty estimation techniques:
  - Token probability distributions
  - Self-consistency (sample multiple outputs)
  - Verifier models
- [ ] Design confidence scoring API:
  - `score_tool_output(tool_name, output) → float [0, 1]`
  - `should_request_clarification(confidence) → bool`
- [ ] **Deliverable:** Design doc

**Week 3: Implementation**
- [ ] Implement confidence scoring for key tools:
  - Edit: Check if old_string exists in file
  - Bash: Parse exit codes, stderr
  - grep: Validate results match pattern
- [ ] Add `confidence` field to ToolResult
- [ ] **Deliverable:** Confidence scores in tool outputs

**Week 4: Integration + Calibration**
- [ ] Wire into agent loop: flag low-confidence results
- [ ] Add clarification prompt: "I'm uncertain about X. Should I Y or Z?"
- [ ] Calibrate thresholds (what confidence triggers clarification?)
- [ ] Test on 20 tasks
- [ ] **Deliverable:** Confidence-aware execution

**Success Criteria:**
- Confidence scores correlate with actual correctness (>0.7 correlation)
- Clarification requests reduce errors by 30%
- No false positives (don't ask on high-confidence correct outputs)

---

### Priority 3C: Async Execution Optimization
**Duration:** 3 weeks
**Owner:** Mid-Level Engineer
**Dependencies:** None

**Tasks:**

**Week 1: Async TraceStore Writes**
- [ ] Convert TraceStore writes to async:
  - `asyncio.create_task(store.write_span(...))`
  - Batching: collect writes, flush every 100ms
- [ ] Ensure durability: flush on phase boundaries
- [ ] **Deliverable:** Async tracing

**Week 2: Async Artifact Storage**
- [ ] Batch artifact storage (content-addressed blobs)
- [ ] Async compression (gzip artifacts in background)
- [ ] **Deliverable:** Async artifacts

**Week 3: Profiling + Optimization**
- [ ] Profile agent loop latency (before/after)
- [ ] Identify remaining bottlenecks
- [ ] Optimize hot paths (context building, token estimation)
- [ ] **Deliverable:** Performance report

**Success Criteria:**
- TraceStore writes no longer block execution (<5ms overhead)
- Overall turn latency reduced by 20%

---

### Q3 Summary
**Duration:** 12 weeks (some parallel work)
**Deliverables:**
- Codebase indexing and semantic search
- Confidence scoring for tool outputs
- Async execution optimization

**Outcomes:**
- Faster localization phase (semantic search)
- Reduced errors via confidence-aware clarification
- 20-30% reduction in turn latency

---

## Q4 2026: Long-Horizon Reasoning (Weeks 40-52)

### Priority 4A: Test-Time Compute Scaling
**Duration:** 4 weeks
**Owner:** ML Engineer
**Dependencies:** Priority 1C (metacognition)

**Tasks:**

**Week 1-2: Extended Thinking**
- [ ] Remove think tool loop limits (currently max 3)
- [ ] Implement budget-aware thinking:
  - Allocate "thinking budget" per phase
  - Think until confident or budget exhausted
- [ ] Add self-verification:
  - After generating solution, use think to verify
  - Check for logical flaws, edge cases
- [ ] **Deliverable:** Extended thinking capability

**Week 3: Chain-of-Thought Prompting**
- [ ] Enhance system prompts with CoT instructions:
  - "Think step-by-step"
  - "Verify your reasoning"
  - "Consider alternatives"
- [ ] Test on complex reasoning tasks (multi-hop, planning)
- [ ] **Deliverable:** CoT prompts

**Week 4: Evaluation**
- [ ] A/B test: baseline vs extended thinking
- [ ] Measure: success rate, thinking steps used, cost
- [ ] Find optimal thinking budget per phase
- [ ] **Deliverable:** Performance report

**Success Criteria:**
- Complex tasks show >15% improvement with extended thinking
- Thinking budget prevents runaway costs
- Self-verification catches >50% of errors before execution

---

### Priority 4B: Skills Packaging (Anthropic-Style)
**Duration:** 4 weeks
**Owner:** Senior Engineer
**Dependencies:** None

**Tasks:**

**Week 1-2: Skills Format Design**
- [ ] Adopt Anthropic's Agent Skills standard:
  - Folder structure: `/skills/{skill_name}/`
  - `instructions.md`: Step-by-step procedure
  - `resources/`: Files, templates, examples
  - `scripts/`: Executable tools
- [ ] Design skill discovery:
  - `list_skills()` tool
  - `activate_skill(skill_name)` tool
- [ ] **Deliverable:** Skills format spec

**Week 3: Implement Core Skills**
- [ ] Create 5 reusable skills:
  - `debug_python_test_failure`: Analyze pytest failures
  - `refactor_extract_function`: Extract code into function
  - `add_logging`: Add comprehensive logging
  - `optimize_performance`: Profile and optimize
  - `update_dependencies`: Upgrade package versions safely
- [ ] Each skill: instructions + examples + tests
- [ ] **Deliverable:** 5 packaged skills

**Week 4: Integration + Testing**
- [ ] Wire skills into LocalHarness
- [ ] Test skill activation and execution
- [ ] Measure: skill success rate, reusability
- [ ] **Deliverable:** Skills system working

**Success Criteria:**
- Skills successfully execute on new tasks (no hardcoding)
- 5/5 skills demonstrate reusability across 10+ tasks
- Clear format for community contributions

---

### Priority 4C: Multi-Hour Task Orchestration
**Duration:** 4 weeks
**Owner:** Senior Engineer
**Dependencies:** Priority 2B (compression), Priority 4A (thinking)

**Tasks:**

**Week 1-2: Checkpoint/Resume**
- [ ] Design checkpoint format:
  - Session state (messages, phase, memory)
  - Tool execution state (open shells, browser sessions)
  - Graph memory snapshot
- [ ] Implement checkpoint save/load
- [ ] Test: crash recovery, manual pause/resume
- [ ] **Deliverable:** Checkpoint system

**Week 3: Progressive Summarization**
- [ ] Hierarchical compression:
  - Phase → summary
  - Multiple phases → epic summary
  - Task → final report
- [ ] Context builder uses hierarchical summaries
- [ ] **Deliverable:** Hierarchical summarization

**Week 4: Long-Horizon Evaluation**
- [ ] Design multi-hour tasks (5-10 hour budgets):
  - Full feature implementation (backend + frontend + tests)
  - Complex debugging (reproduce + localize + fix + verify)
  - Large refactoring (migrate framework, upgrade dependencies)
- [ ] Run 5 long-horizon tasks
- [ ] Measure: completion rate, context management, checkpoints used
- [ ] **Deliverable:** Long-horizon benchmark

**Success Criteria:**
- Complete ≥3/5 multi-hour tasks successfully
- Checkpoint/resume works without data loss
- Context never exhausted (compression handles it)

---

### Q4 Summary
**Duration:** 10 weeks (some parallel work)
**Deliverables:**
- Test-time compute scaling (extended thinking)
- Skills packaging system
- Multi-hour task orchestration

**Outcomes:**
- Handle complex, long-horizon tasks reliably
- Reusable procedural knowledge (skills)
- Production-ready autonomous coding agent

---

## Resource Allocation

### Team Structure

**Q1 2026:**
- 1 Senior Engineer (multi-agent, metacognition): 40 hrs/week
- 1 Mid-Level Engineer (memory, modularization): 30 hrs/week
- Total: 70 hrs/week

**Q2 2026:**
- 1 Senior Engineer (graph memory): 40 hrs/week
- 1 ML Engineer (latent compression): 30 hrs/week
- Total: 70 hrs/week

**Q3 2026:**
- 1 Senior Engineer (codebase indexing): 40 hrs/week
- 1 ML Engineer (confidence scoring): 20 hrs/week
- 1 Mid-Level Engineer (async optimization): 20 hrs/week
- Total: 80 hrs/week

**Q4 2026:**
- 1 Senior Engineer (skills, checkpointing): 40 hrs/week
- 1 ML Engineer (test-time compute): 30 hrs/week
- Total: 70 hrs/week

**Average:** 72.5 hrs/week = ~1.8 FTE

### Budget Breakdown

| Category | Q1 | Q2 | Q3 | Q4 | Total |
|----------|----|----|----|----|-------|
| Salaries (2 engineers @ $75K/quarter avg) | $50K | $50K | $60K | $50K | $210K |
| Compute (DGX Spark + API calls) | $5K | $10K | $10K | $10K | $35K |
| Infrastructure (DB, storage, monitoring) | $2K | $3K | $3K | $3K | $11K |
| Contingency (15%) | $8.5K | $9.5K | $11K | $9.5K | $38.5K |
| **Total** | **$65.5K** | **$72.5K** | **$84K** | **$72.5K** | **$294.5K** |

**Total Budget:** ~$295K for 12-month roadmap

---

## Risk Management

### Technical Risks

| Risk | Likelihood | Impact | Mitigation | Owner |
|------|------------|--------|------------|-------|
| Memory system doesn't improve metrics | Medium | High | Incremental rollout, A/B testing, rollback plan | Senior Eng |
| 128GB memory pressure | Low | Medium | Profiling, model swapping, cloud fallback | ML Eng |
| Integration breaks existing workflows | Low | High | Feature flags, comprehensive tests, staged rollout | All |
| Performance regressions | Medium | Medium | Continuous benchmarking, profiling, optimization budget | Mid Eng |
| Dependencies on external models (Qwen 7B) | Low | Medium | Multiple model options, API fallback | ML Eng |

### Schedule Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Q1 slips due to complexity | Medium | Medium | Prioritize P1A (multi-agent), defer P1D (modularization) |
| ML engineer availability | Medium | High | Hire ML contractor, use Senior Eng for implementation |
| Evaluation bottlenecks | High | Low | Automate benchmarks, parallelize testing |
| Scope creep | Medium | Medium | Strict prioritization, defer nice-to-haves to 2027 |

---

## Success Metrics (12-Month Targets)

### Quantitative Metrics

| Metric | Baseline (Jan 2026) | Target (Dec 2026) | Measurement |
|--------|---------------------|-------------------|-------------|
| SWE-bench Verified | TBD (run baseline) | 60% | Monthly evaluation |
| Context truncation rate | ~80% of tasks | <15% of tasks | TraceStore logs |
| Average turn latency | 3-5s | 2.5-4s | Profiling data |
| Multi-hour task success | 0% (not supported) | 60% | Long-horizon benchmark |
| Memory recall accuracy | N/A (no retrieval) | 85% | Synthetic Q&A |
| Tool error rate | TBD | -30% | Error logs |

### Qualitative Metrics

| Metric | Target | Assessment Method |
|--------|--------|-------------------|
| Code maintainability | No file >2000 lines, clear modules | Code review |
| Observability | Full trace reconstruction, memory provenance | Inspection |
| Developer experience | Clear errors, confidence scores, fast feedback | User feedback |
| Research velocity | 2x faster experiment iteration | Team survey |

---

## Milestone Timeline

```
2026
│
Q1 ├── Week 3:  Multi-agent working
   ├── Week 5:  Memory retrieval integrated
   ├── Week 8:  Metacognition loop operational
   └── Week 10: Modularization complete

Q2 ├── Week 16: Graph memory deployed
   ├── Week 20: Latent compression working
   └── Week 22: Hybrid memory system evaluated

Q3 ├── Week 30: Codebase indexing operational
   ├── Week 34: Confidence scoring integrated
   └── Week 36: Async optimization complete

Q4 ├── Week 44: Extended thinking deployed
   ├── Week 48: Skills system operational
   └── Week 52: Long-horizon orchestration complete
```

---

## Post-2026: Future Roadmap

### Q1 2027: Refinement
- Fine-tune compressor model on CompyMac data
- RL-based tool learning (Cursor-style)
- Multi-repository support
- Shared memory across tasks

### Q2 2027: Scale
- 256GB Spark configuration (2x linked)
- Parametric memory (fine-tune primary model)
- Multi-modal memory (images, diagrams)
- Collaborative multi-agent workflows

### Q3 2027: Productionize
- SaaS deployment architecture
- User-facing features (confidence UI, memory inspection)
- Enterprise features (audit logs, compliance)
- API for external integrations

### Q4 2027: Research
- Memory consolidation (offline refinement)
- Episodic learning (replay trajectories)
- Meta-learning (learn memory strategies)
- Open-source community engagement

---

## Conclusion

This roadmap transforms CompyMac into a world-class autonomous coding agent in 12 months through:

1. **Activating dormant infrastructure** (multi-agent, memory, metacognition)
2. **Solving the context window problem** (hybrid memory system)
3. **Optimizing the tool ecosystem** (indexing, confidence, async)
4. **Enabling long-horizon reasoning** (thinking, skills, checkpoints)

**Total Investment:** $295K, 1.8 FTE-years

**Expected Outcomes:**
- 60% SWE-bench Verified (competitive with Devin, Cursor)
- Multi-hour task capability (unique differentiator)
- Production-ready codebase (maintainable, observable)
- Open-source leadership (comprehensive architecture, full tracing)

**Recommendation:** Approve for immediate execution. Q1 can start with existing team.

---

**Document Version:** 1.0
**Author:** Claude Code Analysis Team
**Review Date:** January 4, 2026
**Next Steps:** Secure budget, assign engineers, kick off Q1 work
