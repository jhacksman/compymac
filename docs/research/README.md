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

### [Automated Testing and Program Repair](automated-testing-program-repair.md)
Research on automated program repair (APR) and test generation for LLM agents. Covers RepairAgent, Meta's Engineering Agent, and test-first verification approaches.

**Key Papers**:
- arXiv:2403.17134 - "RepairAgent: An Autonomous, LLM-Based Agent for Program Repair"
- arXiv:2507.18755 - "Agentic Program Repair from Test Failures at Scale"
- arXiv:2511.01047 - "HAFixAgent: History-Aware Automated Program Repair Agent"
- arXiv:2507.22853 - "Repair-R1: Better Test Before Repair"

### [Specification and Runtime Monitoring](specification-runtime-monitoring.md)
Research on specification languages and runtime monitoring for LLM agents. Covers AgentSpec DSL, proactive enforcement, and formal verification approaches.

**Key Papers**:
- arXiv:2503.18666 - "AgentSpec: Customizable Runtime Enforcement"
- arXiv:2508.00500 - "Pro2Guard: Proactive Runtime Enforcement via Probabilistic Model Checking"
- arXiv:2508.01249 - "AgentArmor: Program Analysis on Agent Runtime Trace"
- arXiv:2503.15547 - "Prompt Flow Integrity to Prevent Privilege Escalation"

### [Security and Sandboxing for Agents](security-sandboxing-agents.md)
Research on security, sandboxing, and capability control for LLM agents. Covers prompt injection defense, privilege control, and trust boundaries.

**Key Papers**:
- arXiv:2506.08837 - "Design Patterns for Securing LLM Agents against Prompt Injections"
- arXiv:2504.11703 - "Progent: Programmable Privilege Control for LLM Agents"
- arXiv:2503.18813 - "Defeating Prompt Injections by Design"
- arXiv:2504.20984 - "ACE: A Security Architecture for LLM-Integrated App Systems"

### [Context and Memory Engineering](context-memory-engineering.md)
Research on codebase indexing, retrieval strategies, code graphs, and long-context handling. Covers RAG for code, context engineering taxonomy, and memory hierarchies.

**Key Papers**:
- arXiv:2510.04905 - "Retrieval-Augmented Code Generation: A Survey"
- arXiv:2507.13334 - "A Survey of Context Engineering for Large Language Models"
- arXiv:2408.03910 - "CodexGraph: Bridging LLMs and Code Repositories via Code Graph Databases"
- arXiv:2406.13121 - "Can Long-Context Language Models Subsume Retrieval, RAG, SQL, and More?"

### [Evaluation Methodology](evaluation-methodology.md)
Research on LLM evaluation methodology, data contamination, benchmark gaming, and reproducibility. Covers dynamic benchmarks and contamination detection.

**Key Papers**:
- arXiv:2502.14425 - "A Survey on Data Contamination for Large Language Models"
- arXiv:2502.17521 - "Benchmarking LLMs Under Data Contamination: Static to Dynamic Evaluation"
- arXiv:2507.11405 - "DCR: Quantifying Data Contamination in LLMs Evaluation"
- arXiv:2503.16402 - "The Emperor's New Clothes in Benchmarking?"

### [Human-Agent Workflow Design](human-agent-workflow.md)
Research on human-agent collaboration, review protocols, handoff points, and interaction patterns. Covers trust building, intervention points, and feedback integration.

**Key Papers**:
- arXiv:2505.00753 - "LLM-Based Human-Agent Collaboration and Interaction Systems: A Survey"
- arXiv:2502.01390 - "Plan-Then-Execute: User Trust and Team Performance Study"
- arXiv:2501.07834 - "Flow: Modularized Agentic Workflow Automation"
- arXiv:2510.02557 - "Orchestrating Human-AI Teams: The Manager Agent Challenge"

### [Tool Reliability and Observability](tool-reliability-observability.md)
Research on tool failure modes, error handling, and observability for LLM agents. Covers failure taxonomies, recovery strategies, and observability frameworks.

**Key Papers**:
- arXiv:2511.19933 - "Failure Modes in LLM Systems: A System-Level Taxonomy"
- arXiv:2509.25238 - "PALADIN: Self-Correcting Agents to Cure Tool-Failure Cases"
- arXiv:2508.19504 - "Aegis: Taxonomy for Overcoming Agent-Environment Failures"
- arXiv:2411.05285 - "AgentOps: Enabling Observability of LLM Agents"

### [Planning and Termination Control](planning-termination-control.md)
Research on when agents should stop, detecting stuckness, and enforcing completion criteria. Covers termination learning, early-exit behavior, and convergence detection.

**Key Papers**:
- arXiv:2510.08517 - "CaRT: Teaching LLM Agents to Know When They Know Enough"
- arXiv:2505.17616 - "Early-Exit Behavior of LLM-based Agents in Embodied Environments"
- arXiv:2509.14004 - "Early Stopping Chain-of-thoughts in Large Language Models"
- arXiv:2503.09572 - "Plan-and-Act: Improving Planning for Long-Horizon Tasks"

## How This Informs CompyMac

| Research Area | CompyMac Implementation |
|---------------|------------------------|
| Agent Hallucination | Guardrailed todo system, two-phase verification |
| Tool Overload | Dynamic tool discovery (`request_tools`) |
| SWE Benchmarks | Multi-agent architecture, TraceStore |
| Devin Patterns | Interactive planning, codebase indexing |
| Automated Testing & Repair | Test-first verification, neuro-symbolic feedback |
| Specification & Monitoring | Runtime constraints, trace analysis |
| Security & Sandboxing | Capability-based access, trust boundaries |
| Context & Memory | Hierarchical retrieval, memory compression |
| Evaluation Methodology | Dynamic benchmarks, contamination awareness |
| Human-Agent Workflow | Intervention points, handoff protocols |
| Tool Reliability | Error envelopes, recovery strategies |
| Planning & Termination | Completion verification, stuckness detection |

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
