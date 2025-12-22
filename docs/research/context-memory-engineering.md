# Context and Memory Engineering for Codebases

## Overview

This document summarizes research on codebase indexing, retrieval strategies, code graphs, and long-context handling for LLM agents. These techniques reduce hallucinations at the source by ensuring agents have accurate, relevant context.

## Key Papers

### 1. Retrieval-Augmented Code Generation Survey (arXiv:2510.04905)

**Focus**: Repository-level code generation (RLCG) where models must capture long-range dependencies and ensure global semantic consistency.

**Key Challenges**:
1. Long-range dependencies across files
2. Global semantic consistency
3. Coherent code spanning multiple modules

**RAG Taxonomy**:
- **Generation Strategies**: How to produce code from retrieved context
- **Retrieval Modalities**: What to retrieve (code, docs, tests, etc.)
- **Model Architectures**: How to integrate retrieval with generation
- **Training Paradigms**: How to train retrieval-augmented models
- **Evaluation Protocols**: How to measure success

**Key Insight**: "Retrieval-Augmented Generation (RAG) has emerged as a powerful paradigm that integrates external retrieval mechanisms with LLMs, enhancing context-awareness and scalability."

**Relevance to CompyMac**: Our grep, glob, and LSP tools provide retrieval. We could enhance them with semantic search and better ranking.

---

### 2. RAG for Code Completion at WeChat (arXiv:2507.18515)

**Context**: Production deployment at scale with closed-source codebase.

**Key Findings**:
1. **Distribution Shift**: Open-source benchmarks don't reflect closed-source performance
2. **Retrieval Quality**: Retrieval precision is critical for completion quality
3. **Context Window**: More context isn't always better - quality over quantity

**Practical Insights**:
- Retrieval from same file is most valuable
- Cross-file retrieval helps for API usage
- Too much context can confuse the model

**Relevance to CompyMac**: We should prioritize local context (same file, same directory) before expanding to repository-wide search.

---

### 3. Context Engineering Survey (arXiv:2507.13334)

**Definition**: "Context Engineering is a formal discipline that transcends simple prompt design to encompass the systematic optimization of information payloads for LLMs."

**Taxonomy**:

**Components**:
1. **Context Retrieval and Generation**: Prompt-based generation, external knowledge acquisition
2. **Context Processing**: Long sequence processing, self-refinement, structured information integration
3. **Context Management**: Memory hierarchies, compression, optimization

**System Implementations**:
1. **RAG**: Modular, agentic, graph-enhanced architectures
2. **Memory Systems**: Persistent interactions across sessions
3. **Tool-Integrated Reasoning**: Function calling, environmental interaction
4. **Multi-Agent Systems**: Coordination and orchestration

**Key Insight**: Context engineering is not just about what to include, but how to structure, compress, and manage information across the agent lifecycle.

**Relevance to CompyMac**: Our MemoryManager implements some of these patterns. We could enhance it with better compression and hierarchical organization.

---

### 4. CodeRAG-Bench: Retrieval for Code Generation (arXiv:2406.14497)

**Benchmark**: Evaluates whether retrieval actually helps code generation.

**Key Findings**:
1. Retrieval helps most for API-heavy tasks
2. Retrieval can hurt for simple tasks (noise)
3. Retrieval quality matters more than quantity

**Retrieval Strategies Evaluated**:
- BM25 (lexical)
- Dense retrieval (semantic)
- Hybrid approaches

**Relevance to CompyMac**: We should consider when to retrieve vs. when to rely on model knowledge. Not every task benefits from retrieval.

---

### 5. CodexGraph: Code Graph Databases (arXiv:2408.03910)

**Core Contribution**: Integrate LLM agents with graph database interfaces extracted from code repositories.

**Architecture**:
1. Extract code structure into graph database
2. LLM agent constructs and executes graph queries
3. Precise, structure-aware context retrieval

**Graph Schema**:
- Nodes: Files, classes, functions, variables
- Edges: Imports, calls, inherits, references

**Results**:
- Competitive on CrossCodeEval, SWE-bench, EvoCodeBench
- Unified schema works across different tasks

**Key Insight**: "By leveraging the structural properties of graph databases and the flexibility of the graph query language, CodexGraph enables the LLM agent to construct and execute queries, allowing for precise, code structure-aware context retrieval."

**Relevance to CompyMac**: Our LSP tool provides some structural information. A graph database could provide richer queries like "find all callers of this function" or "find all implementations of this interface."

---

### 6. Long-Context vs RAG (arXiv:2406.13121)

**Question**: Can long-context LLMs subsume retrieval, RAG, SQL, and more?

**Findings**:
1. Long context helps but doesn't eliminate need for retrieval
2. RAG still wins for very large corpora
3. Hybrid approaches (long context + RAG) work best

**Trade-offs**:
- Long context: Simpler, but expensive and limited
- RAG: Scalable, but requires good retrieval
- Hybrid: Best of both, but more complex

**Relevance to CompyMac**: We should use long context for immediate task context, RAG for repository-wide knowledge.

---

### 7. LaRA: Benchmarking RAG vs Long-Context (arXiv:2502.09977)

**Key Finding**: "No Silver Bullet for LC or RAG Routing"

**Insights**:
1. Task type determines optimal approach
2. Some tasks need retrieval, others need full context
3. Routing between approaches is an open problem

**Relevance to CompyMac**: We need adaptive context strategies that choose the right approach based on task characteristics.

---

### 8. In-Context Retrieval and Reasoning (arXiv:2501.08248)

**Focus**: Eliciting retrieval and reasoning capabilities from long-context LLMs.

**Key Techniques**:
1. **Explicit Retrieval Prompts**: Ask model to find relevant information first
2. **Reasoning Chains**: Connect retrieved information to task
3. **Self-Verification**: Model checks its own retrieval

**Relevance to CompyMac**: Our agents could be prompted to explicitly retrieve and cite relevant context before acting.

---

## Implications for CompyMac

### Context Hierarchy

```
Level 1: Immediate Context (current file, current function)
    - Always included
    - Highest relevance
    
Level 2: Local Context (same directory, imported files)
    - Included when relevant
    - Medium relevance
    
Level 3: Repository Context (related files, similar code)
    - Retrieved on demand
    - Lower relevance, higher noise risk
    
Level 4: External Context (documentation, web search)
    - Retrieved when local context insufficient
    - Lowest relevance, highest noise risk
```

### Retrieval Strategy

| Task Type | Primary Strategy | Fallback |
|-----------|-----------------|----------|
| Bug fix | Local context + LSP | Grep for similar patterns |
| New feature | Related files + docs | Web search for examples |
| Refactoring | All usages (LSP refs) | Grep for string matches |
| API usage | Documentation | Web search |

### Memory Management

Based on the research, our MemoryManager should implement:

1. **Hierarchical Storage**: Different retention for different importance levels
2. **Compression**: Summarize old context rather than discarding
3. **Relevance Scoring**: Prioritize context based on current task
4. **Forgetting**: Actively remove irrelevant information

### Code Graph Integration

Future enhancement: Build code graph from repository

```python
class CodeGraph:
    """Graph representation of codebase structure."""
    
    def find_callers(self, function: str) -> List[Location]:
        """Find all locations that call this function."""
        
    def find_implementations(self, interface: str) -> List[Location]:
        """Find all implementations of this interface."""
        
    def find_dependencies(self, file: str) -> List[str]:
        """Find all files this file depends on."""
        
    def find_dependents(self, file: str) -> List[str]:
        """Find all files that depend on this file."""
```

---

## Metrics to Track

1. **Retrieval Precision**: How often is retrieved context actually used?
2. **Context Utilization**: What percentage of context is referenced in output?
3. **Hallucination Rate**: How often does agent reference non-existent code?
4. **Token Efficiency**: Context tokens per successful action

---

## Open Questions

1. **Optimal Context Size**: How much context is too much? When does noise outweigh signal?

2. **Dynamic Retrieval**: Should agents decide when to retrieve, or should retrieval be automatic?

3. **Graph vs Text**: When is structural (graph) retrieval better than textual (grep) retrieval?

4. **Cross-Repository**: How do we handle context from external repositories (dependencies)?

---

## References

- arXiv:2510.04905 - "Retrieval-Augmented Code Generation: A Survey with Focus on Repository-Level Approaches"
- arXiv:2507.18515 - "A Deep Dive into Retrieval-Augmented Generation for Code Completion: Experience on WeChat"
- arXiv:2507.13334 - "A Survey of Context Engineering for Large Language Models"
- arXiv:2406.14497 - "CodeRAG-Bench: Can Retrieval Augment Code Generation?"
- arXiv:2408.03910 - "CodexGraph: Bridging Large Language Models and Code Repositories via Code Graph Databases"
- arXiv:2406.13121 - "Can Long-Context Language Models Subsume Retrieval, RAG, SQL, and More?"
- arXiv:2502.09977 - "LaRA: Benchmarking Retrieval-Augmented Generation and Long-Context LLMs"
- arXiv:2501.08248 - "Eliciting In-context Retrieval and Reasoning for Long-context Large Language Models"
