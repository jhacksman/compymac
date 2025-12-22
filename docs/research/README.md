# CompyMac Research Knowledge Base

This folder contains summaries of arxiv papers and industry research relevant to CompyMac's design and implementation.

## Documents

### [Agent Hallucination](agent-hallucination.md)
Research on LLM agent hallucinations - a distinct phenomenon from traditional LLM hallucinations that affects autonomous agent systems. Covers hallucination taxonomy, runtime enforcement, and verification patterns.

**Key Papers**:
- arXiv:2509.18970 - "LLM-based Agents Suffer from Hallucinations: A Survey"
- arXiv:2503.18666 - "AgentSpec: Customizable Runtime Enforcement"
- arXiv:2507.21017 - "MIRAGE-Bench: Measuring Agent Hallucinations"
- arXiv:2406.09187 - "GuardAgent: Knowledge-Enabled Reasoning"

### [Tool Overload and Decision Fatigue](tool-overload-decision-fatigue.md)
Research on how LLM agents struggle with large tool sets, cognitive load implications, and mitigation strategies. Directly relevant to CompyMac's dynamic tool discovery system.

**Key Papers**:
- arXiv:2505.03275 - "RAG-MCP: Mitigating Prompt Bloat"
- arXiv:2508.08882 - "MSARL: Multi-Small-Agent Reinforcement Learning"
- arXiv:2502.11435 - "SMART: Self-Aware Agent for Tool Overuse Mitigation"
- arXiv:2506.06843 - "CoThinker: Cognitive Load Theory for LLM Agents"

### [SWE Agents and Benchmarks](swe-agents-benchmarks.md)
Research on software engineering agents and the benchmarks used to evaluate them. Covers SWE-bench variants, agent architectures (MASAI, OpenHands), and evaluation methodologies.

**Key Papers**:
- arXiv:2509.16941 - "SWE-Bench Pro: Long-Horizon Software Engineering Tasks"
- arXiv:2406.11638 - "MASAI: Modular Architecture for Software-engineering AI Agents"
- arXiv:2407.16741 - "OpenHands: Open Platform for AI Software Developers"
- arXiv:2509.06216 - "Agentic Software Engineering: Foundational Pillars"

### [Devin Architecture](devin-architecture.md)
Compilation of publicly available information about Cognition's Devin AI software engineer. Covers architecture, design principles, and lessons for CompyMac.

**Sources**:
- Cognition Blog posts (2024-2025)
- Devin Documentation
- LangChain Interrupt talks
- Third-party analysis

## How This Informs CompyMac

| Research Area | CompyMac Implementation |
|---------------|------------------------|
| Agent Hallucination | Guardrailed todo system, two-phase verification |
| Tool Overload | Dynamic tool discovery (`request_tools`) |
| SWE Benchmarks | Multi-agent architecture, TraceStore |
| Devin Patterns | Interactive planning, codebase indexing |

## Adding New Research

When adding new research documents:
1. Create a new markdown file in this folder
2. Include paper citations with arxiv IDs
3. Summarize key findings
4. Add "Relevance to CompyMac" section
5. Update this README with the new document

## Cross-References

- [Guardrail Architecture](../guardrail-architecture.md) - Uses findings from agent hallucination research
- [Tool Semantics Spec](../tool-semantics-spec.md) - Implements patterns from tool overload research
- [Vision Models Roadmap](../vision-models-roadmap.md) - References OmniParser (arXiv:2408.00203)
