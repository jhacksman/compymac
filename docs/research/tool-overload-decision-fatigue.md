# Tool Overload and Decision Fatigue in LLM Agents

## Overview

This document summarizes research on how LLM agents struggle with large tool sets, the cognitive load implications, and mitigation strategies. This is directly relevant to CompyMac's dynamic tool discovery system (`request_tools`).

## The Problem

When LLM agents are presented with many tools simultaneously:
1. **Prompt Bloat**: Tool schemas consume significant context window space
2. **Selection Complexity**: More tools = harder to choose the right one
3. **Decision Fatigue**: Quality of tool selection degrades with more options
4. **Hallucinated Tools**: Agents may "invent" tools or misuse existing ones

## Key Papers

### 1. RAG-MCP: Mitigating Prompt Bloat (arXiv:2505.03275)

**Core Problem**: LLMs struggle to effectively utilize a growing number of external tools due to prompt bloat and selection complexity.

**Quantified Impact**:
- Baseline tool selection accuracy: **13.62%** with all tools in prompt
- RAG-MCP tool selection accuracy: **43.13%** (3x improvement)
- Prompt token reduction: **>50%**

**Solution Architecture**:
```
Query -> Semantic Retrieval -> Select Relevant Tools -> LLM with Reduced Tool Set
```

Instead of including all tool descriptions in every prompt:
1. Index tool descriptions in a vector store
2. For each query, retrieve only semantically relevant tools
3. Pass only selected tools to the LLM

**Key Insight**: "RAG-MCP uses semantic retrieval to identify the most relevant MCP(s) for a given query from an external index before engaging the LLM. Only the selected tool descriptions are passed to the model, drastically reducing prompt size and simplifying decision-making."

**Relevance to CompyMac**: This validates our `request_tools` approach where agents start with a minimal core toolset and explicitly request additional tools. However, RAG-MCP suggests we could go further with automatic semantic retrieval rather than explicit requests.

---

### 2. MSARL: Multi-Small-Agent Reinforcement Learning (arXiv:2508.08882)

**Core Problem**: Single-agent paradigms that interleave reasoning with tool operations lead to "cognitive-load interference and unstable coordination."

**Solution**: Decouple reasoning from tool use with specialized agents:
- **Reasoning Agent**: Decomposes problems, plans tool invocations
- **Tool Agents**: Specialize in specific external tools

**Key Finding**: "Cognitive-role decoupling with small agents is a scalable blueprint for multi-agent AI design."

**Architecture Benefits**:
1. Each agent has a focused, manageable scope
2. Tool agents can be trained specifically for their tool
3. Reasoning agent doesn't need to understand tool implementation details
4. Reduces cognitive load on any single agent

**Relevance to CompyMac**: Our multi-agent architecture (Manager/Planner/Executor/Reflector) partially implements this pattern. The Executor could be further specialized into tool-specific sub-agents.

---

### 3. SMART: Self-Aware Agent for Tool Overuse Mitigation (arXiv:2502.11435)

**Core Problem**: LLM agents often lack self-awareness, failing to balance reasoning with tool use. This leads to **Tool Overuse** - unnecessarily relying on external tools for tasks solvable with parametric knowledge.

**Quantified Results**:
- Tool use reduction: **24%**
- Performance improvement: **>37%**
- 7B models can match 70B counterparts with strategic tool use

**Key Concept - Metacognition**: Inspired by human metacognition, agents should know when they need tools vs. when they can reason directly.

**SMART-ER Dataset**: Training data where each step includes rationales explaining when tools are necessary vs. when parametric knowledge suffices.

**Relevance to CompyMac**: This suggests we should:
1. Train/prompt agents to evaluate whether a tool is actually needed
2. Include "when to use" guidance in tool descriptions
3. Consider a "think before acting" pattern where agents justify tool selection

---

### 4. CoThinker: Cognitive Load Theory for LLM Agents (arXiv:2506.06843)

**Core Framework**: Applies Cognitive Load Theory (CLT) from cognitive science to LLM agents.

**Three Types of Cognitive Load**:
1. **Intrinsic Load**: Inherent complexity of the task
2. **Extraneous Load**: Unnecessary complexity from poor design
3. **Germane Load**: Productive effort toward learning/solving

**Key Insight**: "LLMs have bounded working memory characteristics" similar to humans. When task demands exceed cognitive capacity, performance degrades.

**CoThinker Solution**:
- Distribute intrinsic load through agent specialization
- Manage transactional load via structured communication
- Use collective working memory across agents

**Relevance to CompyMac**: Tool overload is a form of extraneous cognitive load. Our dynamic tool discovery reduces this by not presenting all tools at once.

---

### 5. AutoTool: Efficient Tool Selection (arXiv:2511.14650)

**Core Problem**: "A major bottleneck in current agent frameworks is the inefficient selection of tools from large tool libraries."

**Solution Approach**: Automated tool selection that:
1. Analyzes the task requirements
2. Matches against tool capabilities
3. Selects minimal sufficient toolset

**Relevance to CompyMac**: Reinforces the value of our `request_tools` meta-tool approach, but suggests we could add more intelligence to tool selection.

---

### 6. ToolOrchestra: Model and Tool Orchestration (arXiv:2511.21689)

**Core Contribution**: Framework for orchestrating both models and tools efficiently.

**Key Insight**: The right tool selection depends not just on the task but also on the model being used. Different models have different tool-use capabilities.

**Relevance to CompyMac**: When using different Venice.ai models, we may need to adjust which tools are available based on model capabilities.

---

## Implications for CompyMac

### Current Implementation: Hierarchical Menu System

CompyMac implements a **2-level hierarchical menu system** based on the Manus "Mask, Don't Remove" pattern. Instead of exposing 60+ tools at once (causing decision fatigue), the agent starts with 6 meta-tools at ROOT and drills into specific modes.

```python
# At ROOT level: only 6 meta-tools visible
META_TOOLS = ["menu_list", "menu_enter", "menu_exit", "complete", "think", "message_user"]

# Agent enters a mode to access domain-specific tools
menu_enter("swe")  # Now has 30 SWE tools + 6 meta-tools = 36 tools
```

**9 Tool Modes** (see `MENU_SYSTEM_DESIGN.md` for full details):

| Mode | Tools | Purpose |
|------|-------|---------|
| swe | 30 | Software engineering (file ops, git, LSP, cross-cutting research) |
| library | 4 | Document library (librarian, web search) |
| browser | 16 | Browser automation (all browser_* tools, recording, visual_checker) |
| search | 7 | Web research (web_search, browser subset, librarian) |
| git | 19 | Full version control (local + remote git operations) |
| data | 10 | File management (fs_* tools, grep, glob) |
| deploy | 5 | Deployment (deploy, CI tools, bash) |
| ai | 9 | AI assistance (ask_smart_friend, visual_checker, todos) |
| integrations | 3 | External integrations (mcp_tool, list_secrets, request_tools) |

**Cross-cutting Tools**: General-purpose tools appear in multiple modes where semantically appropriate:
- `librarian`/`librarian_search`: swe, library, search
- `web_search`/`web_get_contents`: swe, library, search, ai
- `ask_smart_friend`: swe, search, ai
- `bash`/`grep`/`glob`: swe, data, deploy

**Key Design Principles**:
1. **"Mask, Don't Remove"**: All tools are always registered; visibility is controlled by mode
2. **Cross-cutting placement**: General tools appear in multiple modes where users expect them
3. **Mechanical validation**: `validate_tool_coverage()` ensures every registered tool is in at least one mode
4. **Mode ordering**: Most common modes first (swe, library, browser, search)

### Recommended Future Enhancements

Based on the research, we should consider:

1. **Semantic Tool Retrieval** (from RAG-MCP)
   - Index tool descriptions in a vector store
   - Auto-suggest relevant modes based on task context
   - Could replace explicit `menu_enter` with automatic mode selection

2. **Tool Use Justification** (from SMART)
   - Require agents to justify why a tool is needed
   - Track tool use efficiency metrics
   - Identify patterns of tool overuse

3. **Cognitive Load Monitoring** (from CoThinker)
   - Track active tool count per agent
   - Warn when tool set becomes too large (SWE mode has 36 tools - near the threshold)
   - Suggest mode switching when appropriate

4. **Tool Specialization** (from MSARL)
   - Consider tool-specific sub-agents for complex tools
   - Browser agent, Git agent, etc.

### Metrics to Track

| Metric | Description | Target |
|--------|-------------|--------|
| Tools per mode | Tools visible in each mode | 7-15 ideal, <20 acceptable |
| Mode switches per task | How often agents change modes | Minimize |
| Tool selection accuracy | Correct tool chosen on first try | Maximize |
| Prompt token overhead | Tokens used for tool schemas | Minimize |
| Cross-cutting tool usage | How often cross-cutting tools are used | Monitor |

---

## References

- arXiv:2505.03275 - "RAG-MCP: Mitigating Prompt Bloat in LLM Tool Selection via Retrieval-Augmented Generation"
- arXiv:2508.08882 - "MSARL: Decoupling Reasoning and Tool Use with Multi-Small-Agent Reinforcement Learning"
- arXiv:2502.11435 - "SMART: Self-Aware Agent for Tool Overuse Mitigation"
- arXiv:2506.06843 - "CoThinker: Exploring Coordination of LLMs under Cognitive Load Theory"
- arXiv:2511.14650 - "AutoTool: Efficient Tool Selection for Large Language Model Agents"
- arXiv:2511.21689 - "ToolOrchestra: Elevating Intelligence via Efficient Model and Tool Orchestration"
