# SWE Agents and Benchmarks Research

## Overview

This document summarizes research on software engineering (SWE) agents and the benchmarks used to evaluate them. SWE-bench has become the de facto standard for measuring AI agent performance on real-world software engineering tasks.

## Key Benchmarks

### 1. SWE-bench (Original)

**Source**: Princeton NLP Group
**Dataset**: 2,294 GitHub issues from 12 popular Python repositories
**Task**: Given an issue description, produce a patch that resolves the issue

**Evaluation**:
- Patches are applied to the repository
- Existing test suites are run
- Success = all relevant tests pass

**Key Insight**: Unlike code generation benchmarks (HumanEval, MBPP), SWE-bench requires understanding entire codebases, not just writing isolated functions.

---

### 2. SWE-bench Lite

**Subset**: 300 carefully selected issues from SWE-bench
**Purpose**: Faster evaluation while maintaining difficulty distribution
**Usage**: Most commonly reported benchmark for SWE agents

---

### 3. SWE-bench Pro (arXiv:2509.16941)

**Core Contribution**: A substantially more challenging benchmark designed for enterprise-level problems.

**Scale**:
- 1,865 problems
- 41 actively maintained repositories
- Spans business applications, B2B services, developer tools

**Key Differences from SWE-bench**:
- **Long-horizon tasks**: May require hours to days for human engineers
- **Multi-file patches**: Often require changes across multiple files
- **Enterprise complexity**: Real-world business logic, not just open-source libraries

**Partitions**:
1. **Public set**: 11 repositories, open access
2. **Held-out set**: 12 repositories, not publicly accessible
3. **Commercial set**: 18 proprietary repositories (partnership with startups)

**Current Performance** (as of paper publication):
- Best model (GPT-5): **23.3%** Pass@1
- Most models: **<25%** Pass@1

**Failure Mode Analysis**:
The paper clusters agent failure modes:
- Incorrect localization (wrong files/functions)
- Incomplete patches (partial fixes)
- Test failures (patches break other functionality)
- Timeout/resource exhaustion

**Relevance to CompyMac**: This benchmark represents the frontier of SWE agent evaluation. CompyMac should be designed to handle long-horizon, multi-file tasks.

---

### 4. SWE-bench Verified

**Purpose**: Human-verified subset to ensure issues are actually resolvable
**Concern Raised**: arXiv:2506.12286 ("The SWE-Bench Illusion") suggests some high performance may be due to memorization rather than genuine problem-solving.

**Key Finding**: State-of-the-art models achieve up to 76% accuracy in identifying buggy file paths using only issue descriptions, without access to repository structure. This drops to 53% on repositories not in SWE-bench, suggesting data contamination.

---

### 5. UTBoost: Rigorous Evaluation (arXiv:2506.09289)

**Core Contribution**: More rigorous evaluation methodology for SWE-bench.

**Problem Identified**: Some agent "solutions" pass tests but don't actually fix the underlying issue (test overfitting).

**Solution**: Additional unit tests to verify solution correctness beyond the original test suite.

---

### 6. SWE-Effi: Effectiveness Under Resource Constraints (arXiv:2509.09853)

**Core Contribution**: Metrics that balance accuracy with resource consumption.

**Key Insight**: "AI system's effectiveness depends not just on the scaffold itself, but on how well it integrates with the base model."

**Problems Identified**:
1. **Token Snowball Effect**: Agents consume increasingly more tokens as they explore
2. **Expensive Failures**: Agents consume excessive resources on unsolvable tasks

**Relevance to CompyMac**: We should track not just success rate but also resource efficiency (tokens, time, tool calls).

---

## Key SWE Agent Architectures

### 1. MASAI: Modular Architecture (arXiv:2406.11638)

**Core Idea**: Divide complex problems into sub-problems handled by specialized sub-agents.

**Architecture**:
- Multiple LLM-powered sub-agents
- Each sub-agent has well-defined objectives
- Strategies tuned per sub-agent

**Advantages**:
1. Different problem-solving strategies per sub-agent
2. Sub-agents gather information from different repository locations
3. Avoids unnecessarily long trajectories

**Performance**: 28.33% resolution rate on SWE-bench Lite (highest at time of publication)

**Relevance to CompyMac**: Our multi-agent architecture (Manager/Planner/Executor/Reflector) follows similar principles. MASAI validates the modular approach.

---

### 2. OpenHands (arXiv:2407.16741)

**Core Contribution**: Open platform for AI software developers as generalist agents.

**Architecture Components**:
- Sandboxed execution environment
- Shell, code editor, browser access
- Multi-agent coordination
- Evaluation benchmark integration

**Key Design Decisions**:
- Agents interact like human developers (shell, editor, browser)
- Safe sandboxed environments for code execution
- Extensible agent implementations

**Performance**: Evaluated on 15+ benchmarks including SWE-bench and WebArena

**Relevance to CompyMac**: OpenHands is the most similar open-source project to CompyMac. Key differences:
- OpenHands focuses on sandboxed execution
- CompyMac focuses on anti-hallucination guardrails
- Both use multi-agent patterns

---

### 3. AutoCodeRover

**Core Idea**: Intent inference through program analysis.

**Key Insight**: "The key to successfully developing trustworthy agentic AI-based software workflows will be to resolve the core difficulty in software engineering - the deciphering and clarification of developer intent."

**Approach**:
- Use static analysis to understand code structure
- Infer developer intent from issue descriptions
- Ground actions in program analysis results

**Integration**: Integrated into SonarQube static analysis tool

**Relevance to CompyMac**: Suggests we should integrate program analysis tools (AST parsing, type checking) to ground agent actions.

---

### 4. RepoGraph (arXiv:2410.14684)

**Core Contribution**: Repository-level code graph for navigation.

**Problem**: AI software engineering requires understanding entire repositories, not just individual files.

**Solution**: Build a graph representation of the repository:
- Nodes: Files, functions, classes
- Edges: Dependencies, imports, calls

**Usage**: Agents use the graph to navigate and understand code structure.

**Relevance to CompyMac**: Our LSP integration provides similar capabilities. Could be enhanced with explicit graph representation.

---

## Agentic Software Engineering Vision

### Agentic SE 3.0 (arXiv:2509.06216)

**Framework**: "Agentic Software Engineering represents a new era where intelligent agents are tasked not with simple code generation, but with achieving complex, goal-oriented SE objectives."

**Two Modalities**:
1. **SE for Humans**: Traditional software engineering with AI assistance
2. **SE for Agents**: Software engineering performed by agents

**Foundational Pillars** (reimagined for agents):
- **Actors**: Human developers + AI agents as team members
- **Processes**: Automated workflows with agent decision points
- **Tools**: Agent-compatible interfaces (not just human UIs)
- **Artifacts**: Code, tests, documentation generated by agents

**Key Challenge**: "Trusting the AI agent becomes a key aspect, as software engineering becomes more automated."

**Relevance to CompyMac**: This vision paper validates our focus on trustworthiness through guardrails. The "trust" problem is exactly what our anti-hallucination architecture addresses.

---

## Implications for CompyMac

### Design Principles from SWE Research

1. **Modular Architecture**: Break complex tasks into specialized sub-agents (MASAI)

2. **Repository Understanding**: Agents need structural understanding, not just file access (RepoGraph)

3. **Resource Efficiency**: Track and optimize token/time usage (SWE-Effi)

4. **Verifiable Completion**: Don't trust agent claims without evidence (all papers)

5. **Long-Horizon Capability**: Design for multi-step, multi-file tasks (SWE-bench Pro)

### Benchmark Integration

CompyMac should be evaluable on:
- SWE-bench Lite (standard comparison)
- SWE-bench Pro (enterprise capability)
- Custom internal benchmarks (specific use cases)

### Metrics to Track

| Metric | Description | Source |
|--------|-------------|--------|
| Resolution Rate | % of issues successfully resolved | SWE-bench |
| Token Efficiency | Tokens per successful resolution | SWE-Effi |
| Time Efficiency | Wall-clock time per resolution | SWE-Effi |
| Localization Accuracy | Correct file/function identification | SWE-bench Pro |
| Patch Quality | Changes beyond minimum necessary | UTBoost |

---

## References

- arXiv:2509.16941 - "SWE-Bench Pro: Can AI Agents Solve Long-Horizon Software Engineering Tasks?"
- arXiv:2506.09289 - "UTBoost: Rigorous Evaluation of Coding Agents on SWE-Bench"
- arXiv:2509.09853 - "SWE-Effi: Re-Evaluating Software AI Agent System Effectiveness Under Resource Constraints"
- arXiv:2506.12286 - "The SWE-Bench Illusion: When State-of-the-Art LLMs Remember Instead of Reason"
- arXiv:2406.11638 - "MASAI: Modular Architecture for Software-engineering AI Agents"
- arXiv:2407.16741 - "OpenHands: An Open Platform for AI Software Developers as Generalist Agents"
- arXiv:2509.06216 - "Agentic Software Engineering: Foundational Pillars and a Research Roadmap"
- arXiv:2410.14684 - "RepoGraph: Enhancing AI Software Engineering with Repository-level Code Graph"
