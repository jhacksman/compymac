# CLaRa Integration Strategy for CompyMac

**Date:** 2026-01-04  
**Paper:** arXiv:2511.18659v2 (November 2025)  
**Source:** Apple Research  
**Purpose:** Evaluate CLaRa for CompyMac's memory/retrieval layer

---

## Executive Summary

CLaRa (Continuous Latent Reasoning) is Apple's unified RAG framework that performs 16x-128x semantic document compression while jointly optimizing retrieval and generation. While CLaRa is not an autonomous agent like Devin or Manus, it directly addresses one of CompyMac's primary failure modes: context pressure in long-horizon tasks.

**Key Insight:** CLaRa-7B is too small for complex reasoning but ideal as a compression/retrieval component working alongside larger reasoning models (Qwen 235B, Grok).

---

## What CLaRa Does

### Core Innovation

CLaRa replaces the traditional RAG pipeline (separate retriever + generator consuming raw text) with a unified system where:

1. Documents are compressed into continuous latent representations (memory tokens)
2. Retrieval operates in the same embedding space as generation
3. Gradients flow end-to-end from generation loss back to retrieval

```
Traditional RAG:
  Documents → Embeddings → Retriever → Raw Text → Generator → Answer
                    ↑                      ↑
              (separate)            (separate)

CLaRa:
  Documents → Compressed Representations → Retriever → Generator → Answer
                         ↑                     ↑            ↑
                    (shared continuous space, joint optimization)
```

### Compression Ratios

| Ratio | Tokens per Document | Use Case |
|-------|---------------------|----------|
| 4x | ~512 tokens → ~128 tokens | High fidelity, moderate compression |
| 16x | ~512 tokens → ~32 tokens | Best performance/compression tradeoff |
| 32x | ~512 tokens → ~16 tokens | Aggressive compression |
| 128x | ~512 tokens → ~4 tokens | Extreme compression, some quality loss |

### Performance Results (from paper)

**QA Benchmarks (F1 scores):**

| Model | NQ | HotpotQA | Musique | 2Wiki | Avg |
|-------|-----|----------|---------|-------|-----|
| DRO-Mistral-7B (text) | 51.01 | 47.87 | 25.32 | 43.65 | 41.96 |
| CLaRa-Mistral-7B (16x) | 50.89 | 47.62 | 18.01 | 44.66 | 40.30 |
| CLaRa-Mistral-7B (Oracle, 4x) | 77.80 | 77.66 | 41.59 | 73.20 | 67.56 |

**Key Finding:** CLaRa with 16x compression matches or exceeds text-based fine-tuned baselines while using 16x fewer tokens.

**Retrieval Performance (Recall@5):**
- CLaRa-Mistral-7B: 96.21% on HotpotQA (4x compression)
- BGE-Reranker (supervised): 85.93%
- CLaRa surpasses fully supervised retrievers using only weak generation supervision

---

## Why CLaRa Matters for CompyMac

### Current CompyMac Memory Architecture

```
CompyMac Memory System:
┌─────────────────────────────────────────────────────────────┐
│               Memory & Knowledge                            │
│  • MemoryManager: Context compression at 80% utilization   │
│  • KnowledgeStore: Factual memory with embeddings          │
│  • HybridRetriever: Sparse+Dense search with RRF merge     │
└─────────────────────────────────────────────────────────────┘
```

**Current Limitations:**
1. MemoryManager uses LLM-generated summaries (lossy, expensive)
2. KnowledgeStore stores text chunks + separate embeddings
3. HybridRetriever retrieves text that must be re-processed by generator
4. No joint optimization between retrieval and generation

### What CLaRa Would Enable

1. **16x-128x Context Reduction**
   - Tool outputs compressed to latent representations
   - More history fits in context window
   - Longer task horizons without context overflow

2. **Better Retrieval-Generation Alignment**
   - Retriever learns what generator actually needs
   - No mismatch between "relevant" and "useful"

3. **Semantic Preservation**
   - Compression trained to preserve answerable facts
   - Not just truncation or summarization

---

## Integration Architecture

### Proposed Design: CLaRa as Compression Layer

```
┌─────────────────────────────────────────────────────────────┐
│                   CompyMac Agent Loop                       │
│                                                             │
│  User Query → Reasoning Model (Qwen 235B / Grok)           │
│                         ↓                                   │
│                   Tool Execution                            │
│                         ↓                                   │
│              Tool Output (raw text)                         │
│                         ↓                                   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │           CLaRa-7B Compression Layer                │   │
│  │                                                     │   │
│  │  Raw Output → Compressor → Latent Representation   │   │
│  │                    (16x-32x compression)            │   │
│  │                                                     │   │
│  │  Latent Reps → KnowledgeStore (for retrieval)      │   │
│  └─────────────────────────────────────────────────────┘   │
│                         ↓                                   │
│         Compressed Context → Reasoning Model               │
│                         ↓                                   │
│                   Next Action                               │
└─────────────────────────────────────────────────────────────┘
```

### Model Roles

| Model | Role | Size | Memory |
|-------|------|------|--------|
| Qwen 235B (Q4) | Primary reasoning, tool selection, code generation | ~60GB | Main model |
| Grok (API) | Fallback reasoning when Qwen fails | API | N/A |
| CLaRa-7B | Compression, retrieval, memory management | ~4GB (Q8) | Auxiliary |

**Total Local Memory:** ~64GB of 128GB unified RAM budget, leaving headroom for:
- KV cache for long contexts
- Tool execution overhead
- Browser automation (OmniParser if needed)

### Integration Points

1. **Tool Output Compression**
   ```python
   # After tool execution
   raw_output = harness.execute(tool_call)
   
   # Compress for storage and future retrieval
   compressed = clara.compress(raw_output.content)
   knowledge_store.store(compressed, metadata=tool_call.metadata)
   
   # Include compressed representation in context
   context.append(compressed)
   ```

2. **Memory Retrieval**
   ```python
   # When context is full, retrieve relevant compressed memories
   query_embedding = clara.encode_query(current_task)
   relevant_memories = knowledge_store.retrieve(query_embedding, top_k=10)
   
   # Memories are already in latent space, directly usable
   context = build_context(recent_turns, relevant_memories)
   ```

3. **Proactive Compression (CAT-style)**
   ```python
   # At phase boundaries or milestones
   if phase_transition or context_utilization > 0.7:
       old_context = context[:-recent_turns]
       compressed_history = clara.compress_batch(old_context)
       context = [compressed_history] + context[-recent_turns:]
   ```

---

## Implementation Plan

### Phase 1: Evaluation (1 week)

**Goal:** Validate CLaRa compression quality for SWE-agent outputs

1. Download CLaRa-7B-Instruct (has apple-amlr license)
2. Test compression on sample tool outputs:
   - File contents (code, configs)
   - Command outputs (test results, logs)
   - Search results (grep, glob)
3. Measure:
   - Compression ratio achieved
   - Information preservation (can compressed output answer questions about original?)
   - Latency overhead

**Success Criteria:**
- 16x compression with <10% information loss on SWE-relevant queries
- <100ms compression latency per document
- Model loads within 8GB memory (Q8 quantization)

### Phase 2: Integration (2 weeks)

**Goal:** Replace MemoryManager compression with CLaRa

1. Create `ClaraCompressor` class wrapping CLaRa-7B
2. Modify `MemoryManager.compress_messages()` to use CLaRa
3. Update `KnowledgeStore` to store/retrieve latent representations
4. Add compression at tool output boundaries

**Files to Modify:**
- `src/compymac/memory.py` - Add CLaRa compression option
- `src/compymac/knowledge_store.py` - Support latent storage
- `src/compymac/local_harness.py` - Compress tool outputs
- `src/compymac/config.py` - Add CLaRa configuration

### Phase 3: Joint Training (Future)

**Goal:** Fine-tune CLaRa for SWE-specific compression

1. Collect SWE-agent trajectories with tool outputs
2. Create QA pairs from trajectories (what questions can be answered from this output?)
3. Fine-tune CLaRa compressor on SWE data
4. Evaluate on held-out SWE-bench tasks

**This phase requires:**
- Sufficient training data (100+ trajectories)
- Fine-tuning infrastructure
- Evaluation framework

---

## Technical Considerations

### Memory Budget (128GB Unified RAM)

```
Model Loading:
- Qwen 235B (Q4): ~60GB
- CLaRa-7B (Q8): ~8GB
- Subtotal: ~68GB

Runtime:
- KV Cache (200K context): ~20GB
- Tool execution overhead: ~5GB
- Browser/OmniParser: ~10GB (if needed)
- Subtotal: ~35GB

Total: ~103GB / 128GB available
Headroom: ~25GB for spikes
```

### Latency Considerations

| Operation | Expected Latency | Notes |
|-----------|------------------|-------|
| Compress single document | 50-100ms | Batch for efficiency |
| Retrieve top-10 | 10-20ms | Cosine similarity |
| Decompress (if needed) | N/A | CLaRa generates directly from latents |

**Mitigation:** Compress tool outputs asynchronously while reasoning model processes.

### License Considerations

| Model | License | Commercial Use |
|-------|---------|----------------|
| CLaRa-7B-E2E | Unknown (HuggingFace shows "unknown") | Unclear |
| CLaRa-7B-Instruct | apple-amlr | Check terms |

**Recommendation:** Use CLaRa-7B-Instruct which has explicit license. Review apple-amlr terms before production deployment.

### Quantization Options

| Quantization | Memory | Quality | Recommended |
|--------------|--------|---------|-------------|
| FP16 | ~14GB | Best | No (too large) |
| Q8 | ~8GB | Excellent | Yes |
| Q4 | ~4GB | Good | Fallback |

---

## Alternative Approaches

If CLaRa integration proves too complex, consider:

### Option A: PISCO (Predecessor)

- Simpler architecture (compression only, no joint training)
- May be easier to integrate
- Lower performance than CLaRa

### Option B: LLMLingua-2

- Hard compression (text-based, not latent)
- Easier to integrate with existing text-based retrieval
- Lower compression ratios (2-4x vs 16-128x)

### Option C: Custom Compression

- Train small model specifically for SWE outputs
- Full control over compression behavior
- Requires significant training data and effort

---

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| CLaRa doesn't preserve SWE-relevant info | Medium | High | Phase 1 evaluation before integration |
| Memory pressure with both models | Low | Medium | Quantization, model swapping |
| Latency overhead unacceptable | Low | Medium | Async compression, batching |
| License issues for production | Medium | High | Review apple-amlr terms, consider alternatives |
| Integration complexity | Medium | Medium | Phased approach, fallback to existing system |

---

## Success Metrics

### Phase 1 (Evaluation)

- [ ] CLaRa-7B loads in <8GB memory
- [ ] 16x compression achieves >90% information preservation on SWE outputs
- [ ] Compression latency <100ms per document

### Phase 2 (Integration)

- [ ] Context utilization reduced by 50%+ for long tasks
- [ ] No regression in task completion rate
- [ ] Memory retrieval accuracy maintained or improved

### Phase 3 (Joint Training)

- [ ] SWE-bench performance improvement with compressed context
- [ ] Retrieval recall >95% for relevant tool outputs
- [ ] Cost reduction >50% (fewer tokens processed)

---

## Conclusion

CLaRa represents a significant opportunity to address CompyMac's context pressure problem. The 7B model size makes it practical as a compression layer alongside larger reasoning models, and the 16x-128x compression ratios could dramatically extend task horizons.

**Recommended Next Steps:**
1. Download CLaRa-7B-Instruct and run Phase 1 evaluation
2. If evaluation succeeds, proceed with Phase 2 integration
3. Monitor license situation for production deployment

The key insight is that CLaRa should be used for what it's good at (compression, retrieval) while leaving complex reasoning to larger models (Qwen 235B, Grok). This division of labor maximizes the value of the 128GB unified RAM budget.

---

## References

1. He et al. "CLaRa: Bridging Retrieval and Generation with Continuous Latent Reasoning." arXiv:2511.18659v2, November 2025.
2. Apple ML-CLaRa GitHub: https://github.com/apple/ml-clara
3. HuggingFace Models:
   - https://huggingface.co/apple/CLaRa-7B-E2E
   - https://huggingface.co/apple/CLaRa-7B-Instruct
