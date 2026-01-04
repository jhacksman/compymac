# CompyMac Memory Architecture for 128GB DGX Spark
## Technical Design Document

**Date:** January 4, 2026
**Hardware:** NVIDIA DGX Spark (128GB unified RAM)
**Objective:** Eliminate context window limitations through hybrid memory system
**Status:** Design Phase (Ready for Implementation)

---

## 1. Problem Statement

### Current Limitations
**From codebase analysis (`src/compymac/context.py`, `src/compymac/memory.py`):**

1. **Naive Truncation:** Context manager drops oldest messages when budget exceeded
   - **Information Loss:** Permanent, irreversible
   - **No Summarization:** Truncation happens without compression
   - **Line 82-164:** Simple "keep messages that fit" algorithm

2. **Unused Memory Infrastructure:**
   - MemoryManager extracts facts but never retrieves them
   - KnowledgeStore stores embeddings but context builder doesn't query it
   - HybridRetriever exists (347 lines) but not in primary execution path

3. **Unbounded Memory Messages:**
   - Compression creates single memory message
   - Message grows on each compression cycle
   - No hierarchical summarization
   - Eventually exhausts context budget itself

4. **No Latent Compression:**
   - Heuristic summarization: "Executed N tool operations"
   - LLM summarization: Optional, rarely used
   - No learned semantic compression

### Impact on Long-Horizon Tasks
**128K token budget = ~32K words = ~512KB text**

Typical SWE-bench task trajectory:
- System prompt: ~8K tokens
- Tool schemas: ~4K tokens
- Average turn: ~2K tokens
- **Effective horizon: ~50-60 turns before truncation**

Complex tasks (debugging, refactoring) require 100-200+ turns → **guaranteed information loss**.

---

## 2. Design Goals

### Functional Requirements
1. **No information loss:** All facts accessible throughout task
2. **Bounded context:** Never exceed 128K token budget
3. **Fast retrieval:** <100ms to fetch relevant memories
4. **Semantic preservation:** Compression maintains answerable queries
5. **Adaptive granularity:** Recent = detailed, old = summarized

### Non-Functional Requirements
1. **Memory efficiency:** Fit within 128GB DGX Spark alongside primary model
2. **Low latency:** Memory operations don't bottleneck agent loop
3. **Fault tolerance:** Crash-safe persistence
4. **Observability:** Full provenance of memory operations

---

## 3. Hybrid Memory Architecture

### Three-Tier Memory System

```
┌──────────────────────────────────────────────────────────────────┐
│                  CompyMac Hybrid Memory System                   │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  TIER 1: Working Context (In-Context Memory)                     │
│  ┌────────────────────────────────────────────────────────┐     │
│  │ Recent Turns (10-20 messages)                          │     │
│  │ - Full fidelity, no compression                        │     │
│  │ - Tool calls + outputs                                 │     │
│  │ - Budget: 24K tokens (leaves 104K for other uses)      │     │
│  └────────────────────────────────────────────────────────┘     │
│                           ↓                                      │
│  TIER 2: Short-Term Memory (Graph-Based Facts)                   │
│  ┌────────────────────────────────────────────────────────┐     │
│  │ Knowledge Graph (A-MEM style)                          │     │
│  │ - Nodes: Entities (files, functions, vars, errors)    │     │
│  │ - Edges: Relations (imports, calls, modifies)         │     │
│  │ - Metadata: Confidence, timestamp, provenance          │     │
│  │ - Storage: SQLite + in-memory index                    │     │
│  │ - Retrieval: Multi-hop graph traversal                │     │
│  │ - Budget: ~5-10GB RAM, unlimited facts                │     │
│  └────────────────────────────────────────────────────────┘     │
│                           ↓                                      │
│  TIER 3: Long-Term Memory (Latent Compression)                   │
│  ┌────────────────────────────────────────────────────────┐     │
│  │ Compressed Representations                             │     │
│  │ - Old task phases: LOCALIZATION → summary vector      │     │
│  │ - Tool outputs: Large files → semantic embedding      │     │
│  │ - Error patterns: Stack traces → compressed signature │     │
│  │ - Model: 7B compressor (Qwen 7B or Llama 7B)          │     │
│  │ - On-demand decompression for drill-down              │     │
│  │ - Budget: 4-8GB RAM for model weights                 │     │
│  └────────────────────────────────────────────────────────┘     │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

### Data Flow

```
Tool Execution
      ↓
Extract Facts (real-time)
      ↓
      ├─→ Short-Term Graph (always)
      ├─→ Working Context (if recent)
      └─→ Long-Term Compression (if old or large)
                ↓
        Context Builder
                ↓
        ┌───────┴───────┐
        ↓               ↓
   Graph Query    Decompress If Needed
        ↓               ↓
   Inject into LLM Context
```

---

## 4. Tier 1: Working Context (In-Context Memory)

### Current Implementation
**File:** `src/compymac/context.py:82-164`

**Algorithm:**
```python
def truncate(messages, budget):
    system_msg = messages[0]
    recent = []
    total = estimate_tokens(system_msg)

    for msg in reversed(messages[1:]):
        msg_tokens = estimate_tokens(msg)
        if total + msg_tokens > budget:
            break
        recent.insert(0, msg)
        total += msg_tokens

    return [system_msg] + recent
```

**Problem:** Drops oldest messages, no memory preservation.

### Proposed Enhancement
**New Algorithm:**
```python
def build_context(messages, budget, memory_graph, compressor):
    system_msg = messages[0]
    recent = messages[-20:]  # Last 20 turns, full fidelity

    # Budget allocation
    system_budget = estimate_tokens(system_msg)
    recent_budget = sum(estimate_tokens(m) for m in recent)
    memory_budget = budget - system_budget - recent_budget - 4096  # reserve for response

    # Query relevant facts from graph
    current_task = extract_task_description(messages)
    relevant_facts = memory_graph.query(
        seed_entities=extract_entities(recent),
        query_text=current_task,
        max_hops=2,
        top_k=50
    )

    # Build memory summary from facts
    memory_summary = format_facts_as_context(relevant_facts, budget=memory_budget)

    # Optionally decompress old phases if needed
    if needs_historical_context(current_task):
        relevant_phases = compressor.search_compressed(current_task, top_k=3)
        phase_summaries = [compressor.decompress(p) for p in relevant_phases]
        memory_summary += format_phases(phase_summaries)

    return [system_msg, memory_summary] + recent
```

**Key Changes:**
1. Always keep last 20 turns (full fidelity)
2. Query graph for relevant facts
3. Allocate remaining budget to memory summary
4. Inject memory before recent turns (temporal ordering)

---

## 5. Tier 2: Graph-Based Short-Term Memory

### Design: A-MEM Inspired Knowledge Graph

**Schema:**
```sql
-- Entities (nodes)
CREATE TABLE entities (
    entity_id TEXT PRIMARY KEY,
    entity_type TEXT NOT NULL,  -- 'file', 'function', 'class', 'variable', 'error', 'tool', 'decision'
    name TEXT NOT NULL,
    content TEXT,  -- Full content if small, hash if large
    embedding BLOB,  -- 1536-dim vector from text-embedding-3-small
    confidence FLOAT DEFAULT 1.0,  -- 0.0-1.0
    created_at TIMESTAMP,
    last_accessed TIMESTAMP,
    source_span_id TEXT,  -- TraceStore provenance
    metadata JSON  -- Flexible attributes
);

-- Relations (edges)
CREATE TABLE relations (
    relation_id TEXT PRIMARY KEY,
    from_entity_id TEXT REFERENCES entities(entity_id),
    to_entity_id TEXT REFERENCES entities(entity_id),
    relation_type TEXT NOT NULL,  -- 'imports', 'calls', 'modifies', 'defines', 'references', 'similar_to'
    confidence FLOAT DEFAULT 1.0,
    created_at TIMESTAMP,
    source_span_id TEXT,
    metadata JSON
);

-- Indexes for fast lookup
CREATE INDEX idx_entities_type ON entities(entity_type);
CREATE INDEX idx_entities_name ON entities(name);
CREATE INDEX idx_relations_from ON relations(from_entity_id);
CREATE INDEX idx_relations_to ON relations(to_entity_id);
CREATE INDEX idx_relations_type ON relations(relation_type);
```

### Extraction Rules

**From Tool Outputs:**
```python
# Read tool → File entity
{
    "entity_type": "file",
    "name": "/path/to/file.py",
    "content": file_content[:1000],  # First 1KB
    "embedding": embed(file_content),
    "metadata": {"size_bytes": len(file_content), "language": "python"}
}

# Edit tool → Modifies relation
{
    "from_entity_id": "tool_call_123",
    "to_entity_id": "file:/path/to/file.py",
    "relation_type": "modifies",
    "metadata": {"old_string": "...", "new_string": "..."}
}

# Bash tool with error → Error entity
{
    "entity_type": "error",
    "name": "pytest::test_foo::AssertionError",
    "content": full_stack_trace,
    "embedding": embed(stack_trace),
    "metadata": {"exit_code": 1, "command": "pytest tests/"}
}
```

### Query Algorithms

#### 1. Multi-Hop Graph Traversal
```python
def query_graph(seed_entities, max_hops=2, relation_types=None):
    """
    BFS from seed entities, traversing specified relation types.
    Returns subgraph of connected entities.
    """
    visited = set()
    frontier = set(seed_entities)
    result = []

    for hop in range(max_hops):
        next_frontier = set()
        for entity_id in frontier:
            if entity_id in visited:
                continue
            visited.add(entity_id)
            result.append(get_entity(entity_id))

            # Traverse outgoing edges
            edges = get_relations(from_entity_id=entity_id, types=relation_types)
            next_frontier.update(e.to_entity_id for e in edges)

            # Traverse incoming edges
            edges = get_relations(to_entity_id=entity_id, types=relation_types)
            next_frontier.update(e.from_entity_id for e in edges)

        frontier = next_frontier

    return result
```

#### 2. Semantic Search + Graph Expansion
```python
def hybrid_query(query_text, top_k=20, expand_hops=1):
    """
    1. Semantic search for top-k entities
    2. Expand to connected entities (1-2 hops)
    3. Return ranked subgraph
    """
    query_embedding = embed(query_text)

    # Vector search
    semantic_matches = vector_search(query_embedding, top_k=top_k)

    # Expand graph
    seed_entities = [m.entity_id for m in semantic_matches]
    subgraph = query_graph(seed_entities, max_hops=expand_hops)

    # Re-rank by relevance + recency
    scored = []
    for entity in subgraph:
        score = (
            cosine_sim(query_embedding, entity.embedding) * 0.7 +
            recency_score(entity.last_accessed) * 0.3
        )
        scored.append((entity, score))

    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:top_k]
```

### Memory Budget

**Estimated Memory Usage:**
- 10,000 entities × 1KB metadata = 10MB
- 10,000 entities × 1536 floats × 4 bytes = 60MB (embeddings)
- 50,000 relations × 200 bytes = 10MB
- SQLite overhead: ~20MB
- In-memory indexes: ~50MB

**Total: ~150MB** (well within 128GB budget)

**Scalability:** Supports 100K+ entities before needing to archive or prune.

---

## 6. Tier 3: Long-Term Memory (Latent Compression)

### Design: Learned Semantic Compression

**Model Selection:**
- **Option A:** Qwen 7B (3.5GB Q4 quantized)
- **Option B:** Llama 3.1 7B (3.5GB Q4 quantized)
- **Option C:** Phi-3 Small (1.7GB Q4 quantized, faster but less capable)

**Recommendation:** Start with Qwen 7B (already in ecosystem, good coding performance).

### Compression Strategy

**When to Compress:**
1. **Phase completion:** After LOCALIZATION, UNDERSTANDING phases
2. **Large tool outputs:** File reads >10KB, bash outputs >5KB
3. **Time-based:** Messages >1 hour old
4. **Manual triggers:** User or agent requests compression

**Compression Algorithm:**
```python
def compress_phase(phase_messages, compressor_model):
    """
    Compress a completed phase into latent representation + summary.
    """
    # Extract key information
    prompt = f"""Compress this {phase_name} phase into a concise summary.

    Messages:
    {format_messages(phase_messages)}

    Provide:
    1. High-level summary (2-3 sentences)
    2. Key findings (bullet points)
    3. Important file paths, functions, variables
    4. Decisions made and rationale

    Format as JSON:
    {{
        "summary": "...",
        "findings": ["...", "..."],
        "artifacts": {{"files": [...], "functions": [...]}},
        "decisions": ["..."]
    }}
    """

    # Generate compression
    response = compressor_model.generate(prompt, max_tokens=1000)
    compressed = json.loads(response.content)

    # Generate embedding for retrieval
    summary_text = compressed["summary"] + " ".join(compressed["findings"])
    embedding = embed(summary_text)

    # Store compressed representation
    compressed_memory = {
        "phase_id": generate_id(),
        "phase_name": phase_name,
        "original_message_ids": [m.id for m in phase_messages],
        "compressed_json": compressed,
        "embedding": embedding,
        "original_token_count": sum(estimate_tokens(m) for m in phase_messages),
        "compressed_token_count": estimate_tokens(str(compressed)),
        "compression_ratio": original_token_count / compressed_token_count,
        "created_at": now()
    }

    save_compressed_memory(compressed_memory)
    return compressed_memory
```

**Decompression:**
```python
def decompress_phase(compressed_memory, detail_level="summary"):
    """
    Reconstruct context from compressed memory.

    detail_level:
    - "summary": Just the high-level summary (50-100 tokens)
    - "findings": Summary + findings (200-300 tokens)
    - "full": All compressed JSON (500-1000 tokens)
    - "original": Fetch original messages from TraceStore (full fidelity)
    """
    if detail_level == "summary":
        return compressed_memory["compressed_json"]["summary"]
    elif detail_level == "findings":
        return format_summary_and_findings(compressed_memory["compressed_json"])
    elif detail_level == "full":
        return json.dumps(compressed_memory["compressed_json"], indent=2)
    elif detail_level == "original":
        # Fetch from TraceStore artifacts
        message_ids = compressed_memory["original_message_ids"]
        return fetch_original_messages(message_ids)
```

### Memory Budget

**Model Weights:**
- Qwen 7B Q4: ~3.5GB
- KV cache (4K context): ~500MB

**Storage:**
- 1000 compressed phases × 1KB JSON = 1MB
- 1000 embeddings × 1536 floats × 4 bytes = 6MB

**Total: ~4GB** (well within budget)

---

## 7. Integration with Existing Components

### Modified Context Builder
**File:** `src/compymac/context.py`

**Changes:**
```python
class ContextManager:
    def __init__(self, config, memory_graph, compressor):
        self.config = config
        self.memory_graph = memory_graph  # NEW
        self.compressor = compressor      # NEW

    def build_context(self, messages, tool_schemas):
        # Existing logic for system message + tool schemas
        system_msg = self._build_system_message()
        tool_msg = self._build_tool_message(tool_schemas)

        # NEW: Query memory graph
        recent_turns = messages[-20:]
        memory_facts = self._query_memory(recent_turns)
        memory_msg = self._format_memory_message(memory_facts)

        # Assemble context
        return [system_msg, tool_msg, memory_msg] + recent_turns

    def _query_memory(self, recent_turns):
        # Extract entities mentioned in recent turns
        entities = self.memory_graph.extract_entities(recent_turns)

        # Multi-hop query
        relevant_facts = self.memory_graph.query(
            seed_entities=entities,
            max_hops=2,
            top_k=50
        )

        # Check if we need historical context
        task_description = extract_task(recent_turns[0])
        if self._needs_historical_context(task_description):
            compressed = self.compressor.search(task_description, top_k=3)
            for c in compressed:
                relevant_facts.append(self.compressor.decompress(c, "findings"))

        return relevant_facts
```

### Modified Memory Manager
**File:** `src/compymac/memory.py`

**Changes:**
```python
class MemoryManager:
    def __init__(self, config, llm_client, memory_graph, compressor):
        self.config = config
        self.llm_client = llm_client
        self.memory_graph = memory_graph  # NEW
        self.compressor = compressor      # NEW

    def process_tool_result(self, tool_name, tool_args, tool_result):
        """Extract facts and update graph in real-time."""
        # Extract entities
        entities = self._extract_entities(tool_name, tool_args, tool_result)
        for entity in entities:
            self.memory_graph.add_entity(entity)

        # Extract relations
        relations = self._extract_relations(tool_name, tool_args, tool_result)
        for relation in relations:
            self.memory_graph.add_relation(relation)

    def compress_phase(self, phase_name, phase_messages):
        """Compress completed phase for long-term storage."""
        compressed = self.compressor.compress_phase(phase_name, phase_messages)

        # Also extract graph facts before compression
        for msg in phase_messages:
            if msg.role == "tool":
                self.process_tool_result(msg.tool_name, msg.tool_args, msg.content)

        return compressed
```

### Modified Agent Loop
**File:** `src/compymac/agent_loop.py`

**Changes:**
```python
class AgentLoop:
    def run(self, goal):
        for turn in range(self.max_turns):
            # Build context with memory
            context = self.context_manager.build_context(
                self.session.messages,
                self.harness.get_tool_schemas()
            )

            # LLM call
            response = self.llm_client.chat(context, tools=schemas)

            # Execute tools
            for tool_call in response.tool_calls:
                result = self.harness.execute(tool_call)

                # NEW: Update memory graph in real-time
                self.memory_manager.process_tool_result(
                    tool_call.name,
                    tool_call.args,
                    result
                )

            # Check for phase completion (SWE-bench)
            if self.swe_phase_state.phase_completed():
                # NEW: Compress completed phase
                phase_msgs = self.swe_phase_state.get_phase_messages()
                compressed = self.memory_manager.compress_phase(
                    self.swe_phase_state.current_phase,
                    phase_msgs
                )
```

---

## 8. Memory Budget for 128GB DGX Spark

### Full System Memory Layout

```
┌─────────────────────────────────────────────────────────────┐
│              128GB DGX Spark Allocation                     │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Primary Reasoning Model: 60-70GB                           │
│  ├─ Option A: Qwen 235B Q4 (~60GB) + KV cache (10GB)       │
│  ├─ Option B: Claude API (0GB local, API only)             │
│  └─ Option C: Qwen 72B Q4 (~40GB) + KV cache (5GB)         │
│                                                             │
│  Memory Compression Model: 4GB                              │
│  ├─ Qwen 7B Q4: 3.5GB weights                              │
│  └─ KV cache: 500MB                                        │
│                                                             │
│  Embedding Model: 1GB                                       │
│  ├─ text-embedding-3-small via API (0GB local)             │
│  └─ OR local BGE-large: ~1GB                               │
│                                                             │
│  Memory Graph Storage: 5-10GB                               │
│  ├─ Entity database: 100MB                                 │
│  ├─ Embedding cache: 5GB (for 100K entities)               │
│  ├─ Relation database: 50MB                                │
│  └─ In-memory indexes: 2GB                                 │
│                                                             │
│  TraceStore + Artifacts: 5-10GB                             │
│  ├─ SQLite database: 2GB                                   │
│  └─ Artifact blobs: 5GB                                    │
│                                                             │
│  Tool Execution Overhead: 10-15GB                           │
│  ├─ Browser sessions (Playwright): 3GB                     │
│  ├─ LSP servers (Python, TypeScript): 2GB                  │
│  ├─ Git operations: 1GB                                    │
│  └─ Shell sessions: 1GB                                    │
│                                                             │
│  System + Python Runtime: 10-15GB                           │
│  ├─ OS kernel: 2GB                                         │
│  ├─ Python interpreter: 1GB                                │
│  ├─ PyTorch/vLLM: 5GB                                      │
│  └─ Other libraries: 2GB                                   │
│                                                             │
│  Reserved Headroom: 20-30GB                                 │
│  ├─ Temporary allocations                                  │
│  ├─ Memory spikes during inference                         │
│  └─ Safety margin for OOM prevention                       │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│  TOTAL: ~128GB (fits within budget)                         │
└─────────────────────────────────────────────────────────────┘
```

### Memory Optimization Strategies

**If memory pressure occurs:**

1. **Swap to smaller primary model**
   - Qwen 235B → Qwen 72B saves 30-40GB
   - Or use Claude API (saves 60GB, adds latency)

2. **Reduce embedding cache**
   - Cap at 50K entities (saves 2.5GB)
   - Use LRU eviction policy

3. **Compress artifacts**
   - gzip artifact blobs (5x compression)
   - Lazy decompression on access

4. **Offload tools**
   - Run browser/LSP on separate machine
   - Communicate via RPC

---

## 9. Performance Characteristics

### Latency Analysis

| Operation | Current | Projected | Notes |
|-----------|---------|-----------|-------|
| Context building | 10-50ms | 50-150ms | +graph query overhead |
| Fact extraction | N/A (unused) | 5-10ms | Real-time entity extraction |
| Graph query (2-hop) | N/A | 20-80ms | Depends on subgraph size |
| Memory compression | N/A | 2-5s | 7B model inference |
| Memory decompression | N/A | 100ms-2s | Summary: fast, full: slower |
| Total turn overhead | 0ms | 50-200ms | Acceptable (<10% of LLM latency) |

### Storage Scalability

| Duration | Entities | Relations | Graph Size | Compressed Phases | Total Storage |
|----------|----------|-----------|------------|-------------------|---------------|
| 1 hour task | 1,000 | 5,000 | 15MB | 10 | 100MB |
| 1 day operation | 10,000 | 50,000 | 150MB | 100 | 1GB |
| 1 week | 50,000 | 250,000 | 750MB | 500 | 5GB |
| 1 month | 200,000 | 1,000,000 | 3GB | 2,000 | 20GB |

**Archiving Strategy:** After 1 month, archive to cold storage (S3, disk), keep hot index.

---

## 10. Implementation Roadmap

### Phase 1: Graph-Based Memory (4-6 weeks)

**Week 1-2: Schema + Extraction**
- Design entity/relation schema
- Implement extraction rules for 10 most common tools
- Unit tests for extraction logic
- **Deliverable:** `src/compymac/memory/graph.py` (500 lines)

**Week 3-4: Query Engine**
- Implement multi-hop graph traversal
- Implement semantic search + graph expansion
- Benchmark query performance
- **Deliverable:** Query API with <100ms latency

**Week 5-6: Integration**
- Wire MemoryManager → Graph updates
- Wire ContextManager → Graph queries
- Integration tests on sample SWE-bench tasks
- **Deliverable:** End-to-end working prototype

### Phase 2: Latent Compression (4-6 weeks)

**Week 1-2: Model Setup**
- Deploy Qwen 7B with vLLM
- Design compression prompts
- Implement compress/decompress functions
- **Deliverable:** Compression model API

**Week 3-4: Phase Compression**
- Integrate with SWE workflow phase transitions
- Compress LOCALIZATION, UNDERSTANDING outputs
- Store compressed representations
- **Deliverable:** Phase compression working

**Week 5-6: Retrieval + Decompression**
- Implement search over compressed memories
- Integrate with context builder
- A/B test: with vs without long-term memory
- **Deliverable:** Performance evaluation report

### Phase 3: Optimization + Tuning (2-4 weeks)

**Week 1-2: Performance**
- Profile memory operations
- Optimize query performance (indexing, caching)
- Reduce compression latency (batching, async)
- **Deliverable:** <100ms average memory overhead

**Week 3-4: Evaluation**
- Run on 50 SWE-bench tasks
- Measure: context truncation rate, fact recall, task success
- Compare: baseline vs. graph vs. graph+compression
- **Deliverable:** Benchmark results, decision to productionize

---

## 11. Success Metrics

### Quantitative Metrics
1. **Context Truncation Rate:** Reduce by 80% (from frequent to rare)
2. **Fact Recall Accuracy:** >85% on synthetic retrieval queries
3. **Memory Overhead:** <10% increase in turn latency
4. **Storage Efficiency:** 10x compression ratio on old phases
5. **Long-Horizon Success:** Complete 5+ hour tasks without context loss

### Qualitative Metrics
1. **Code Maintainability:** Modular memory system, clear APIs
2. **Observability:** Can inspect graph state, compressed memories
3. **Debuggability:** Provenance from facts → tool calls → spans
4. **User Experience:** Agent remembers earlier context without prompting

---

## 12. Risk Mitigation

### Technical Risks

**Risk 1: Graph query latency exceeds budget**
- **Likelihood:** Medium
- **Mitigation:**
  - Implement aggressive caching
  - Limit max_hops to 2
  - Pre-compute common queries
  - Fallback to vector search only if graph is slow

**Risk 2: Compression loses critical information**
- **Likelihood:** Medium
- **Mitigation:**
  - Keep original messages in TraceStore (always retrievable)
  - Decompression levels (summary → findings → full → original)
  - Compression quality metrics (perplexity, BLEU)
  - Human-in-loop review for critical tasks

**Risk 3: Memory pressure on 128GB Spark**
- **Likelihood:** Low
- **Mitigation:**
  - Memory profiling during development
  - Swap to smaller models if needed (Qwen 72B, Claude API)
  - Reduce embedding cache size
  - Monitor with `/proc/meminfo`, alerts at 90% usage

**Risk 4: Integration breaks existing workflows**
- **Likelihood:** Low
- **Mitigation:**
  - Feature flag: `ENABLE_HYBRID_MEMORY=false` (default off)
  - A/B testing on non-critical tasks first
  - Comprehensive integration tests
  - Rollback plan: revert to truncation-only

### Operational Risks

**Risk 1: Dependency on 7B compressor model**
- **Likelihood:** Low
- **Mitigation:**
  - Make compression optional (graph-only mode)
  - API fallback (use primary model for compression)
  - Multiple model options (Qwen, Llama, Phi)

**Risk 2: Storage growth unbounded**
- **Likelihood:** Medium
- **Mitigation:**
  - Implement archival policy (>1 month → cold storage)
  - Pruning heuristics (low-confidence entities, unused facts)
  - Storage monitoring and alerts

---

## 13. Future Enhancements

### Short-Term (3-6 months)
1. **Learned Entity Extraction:** Fine-tune small model on tool outputs
2. **Graph Pruning:** Remove low-value facts automatically
3. **Multi-Repository Support:** Separate graphs per codebase
4. **Shared Memory:** Cross-task fact reuse (learned patterns)

### Medium-Term (6-12 months)
1. **RL-Based Memory Management:** Learn what to remember/forget (Memory-R1 style)
2. **Hierarchical Compression:** Compress compressed memories (recursive)
3. **Cross-Modal Memory:** Images, diagrams, PDFs in graph
4. **Collaborative Memory:** Multi-agent shared knowledge base

### Long-Term (12+ months)
1. **Parametric Memory:** Fine-tune primary model on task history
2. **Memory Consolidation:** Offline batch processing to refine graph
3. **Episodic Memory:** Replay successful trajectories for learning
4. **Meta-Learning:** Learn memory strategies from task outcomes

---

## 14. Conclusion

The proposed **Hybrid Memory Architecture** addresses CompyMac's critical limitation (context window exhaustion) while fitting comfortably within the 128GB DGX Spark budget.

**Key Benefits:**
1. **No information loss:** Graph + compression preserves all facts
2. **Scalable:** Supports multi-hour tasks without degradation
3. **Fast:** <100ms memory overhead per turn
4. **Observable:** Full provenance from facts to tool calls
5. **Flexible:** Modular design, graceful degradation

**Implementation Effort:** 10-16 weeks (2.5-4 months) for full system

**Risk:** Low-Medium, mitigated by feature flags, A/B testing, rollback plan

**Recommendation:** **Approve for implementation.** This is the highest-impact improvement to CompyMac's long-horizon capabilities.

---

**Document Version:** 1.0
**Author:** Claude Code Analysis Team
**Review Date:** January 4, 2026
**Approvals Required:** Engineering Lead, Product Manager
**Next Steps:** Kick-off meeting, assign engineers, set milestones
