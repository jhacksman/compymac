# Automated Testing and Program Repair Research

## Overview

This document summarizes research on automated program repair (APR) and test generation for LLM agents. These capabilities are directly relevant to CompyMac's "verified completion" principle - if agents can generate strong tests and reliably repair code, the verification phase becomes more robust.

## Key Papers

### 1. RepairAgent: Autonomous LLM-Based Program Repair (arXiv:2403.17134)

**Core Contribution**: First autonomous LLM-based agent for program repair that dynamically plans and executes repair actions.

**Architecture**:
- LLM as autonomous agent (not fixed prompt/feedback loop)
- Dynamically interleaves: gathering bug info, gathering repair ingredients, validating fixes
- Finite state machine guides tool invocation
- Tools include: fault localization, code search, test execution, patch generation

**Results on Defects4J**:
- 164 bugs fixed (39 unique to RepairAgent)
- Average cost: 270k tokens per bug (~14 cents with GPT-3.5)

**Key Insight**: "Unlike existing deep learning-based approaches, which prompt a model with a fixed prompt or in a fixed feedback loop, our work treats the LLM as an agent capable of autonomously planning and executing actions."

**Relevance to CompyMac**: Validates our agent-based approach. The tool-based repair loop (gather info -> generate patch -> validate) maps to our todo verification pattern.

---

### 2. Agentic Program Repair at Scale (arXiv:2507.18755)

**Source**: Meta's Engineering Agent for production bug fixing

**Architecture**:
- ReAct harness with Llama base model
- 15 available actions (read file, generate patch, run tests, etc.)
- Feedback from static analysis AND test execution
- LLM-as-Judge for patch quality validation
- Human reviewer for final approval

**Key Findings**:
- Specialized 70B model competitive with vanilla 405B
- "Search-and-replace" format outperforms unified diff
- ReAct harness benefits from symbolic information (static analysis, test traces)
- Balanced model: **42.3% solve rate** with 11.8 feedback iterations average

**Relevance to CompyMac**: The neuro-symbolic approach (LLM + static analysis + test feedback) aligns with our verification philosophy. The LLM-as-Judge pattern could inform our acceptance criteria checking.

---

### 3. HAFixAgent: History-Aware Bug Fixing (arXiv:2511.01047)

**Core Insight**: Repository history (git blame, commit history) helps repair bugs because "the last commit touching the buggy line is often the bug-introducing one."

**Results**:
- 212.3% improvement over agent-based baseline
- 29.9% improvement over multi-hunk baseline
- History doesn't significantly increase agent steps or token costs

**Key Technique**: Blame-derived repository heuristics injected into repair loop.

**Relevance to CompyMac**: Our git tools could be enhanced to provide blame information for bug localization. History-aware context could improve repair accuracy.

---

### 4. REFINE: Context-Aware Patch Refinement (arXiv:2510.03588)

**Problem**: LLM-based APR often produces "Draft Patches" - partially correct patches that either incompletely address bugs or overfit to test cases.

**Solution**: Three-stage refinement:
1. Disambiguate vague issue/code context
2. Diversify patch candidates through test-time scaling
3. Aggregate partial fixes via LLM-powered code review

**Results**:
- 14.67% boost to AutoCodeRover (51.67% on SWE-Bench Lite)
- 12.2% improvement on SWE-Bench Verified
- Average 14% improvement across multiple APR systems

**Relevance to CompyMac**: The refinement pattern (draft -> review -> refine) maps to our two-phase completion (claimed -> verified). Could inform how we handle partial completions.

---

### 5. TestForge: Agentic Test Suite Generation (arXiv:2503.14713)

**Problem**: Existing test generation either compromises readability (search-based) or is expensive (LLM-based).

**Solution**: Feedback-driven agentic approach that balances:
- Test readability
- Coverage
- Cost efficiency

**Key Insight**: Agents can iteratively improve test suites based on coverage feedback, similar to how human developers write tests.

**Relevance to CompyMac**: Test generation is critical for our verification phase. If agents can generate good tests, acceptance criteria become more meaningful.

---

### 6. Repair-R1: Better Test Before Repair (arXiv:2507.22853)

**Core Innovation**: Generate discriminative tests BEFORE attempting repair.

**Approach**:
1. Generate test cases that distinguish defective behavior
2. Use tests to better locate defects
3. Perform repair based on test insights

**Training**: Reinforcement learning to co-optimize test generation and bug repair.

**Key Insight**: "The model is required to first generate discriminative test cases that can distinguish defective behaviors, and then perform repair based on these tests."

**Relevance to CompyMac**: This "test-first" approach could inform our verification design. Instead of just checking if tests pass, we could have agents generate tests that specifically verify the claimed completion.

---

### 7. Survey: LLM-based Automated Program Repair (arXiv:2506.23749)

**Taxonomy of 63 APR systems (2022-2025)**:

**Four Paradigms**:
1. **Fine-tuning**: Strong task alignment, high training cost
2. **Prompting**: Rapid deployment, limited by prompt design
3. **Procedural Pipelines**: Reproducible control, moderate overhead
4. **Agentic Frameworks**: Handles multi-hunk/cross-file bugs, higher latency

**Key Trade-offs**:
- Fine-tuning vs prompting: task alignment vs deployment speed
- Procedural vs agentic: reproducibility vs flexibility
- Single-file vs repository-level: simplicity vs real-world applicability

**Persistent Challenges**:
- Verifying semantic correctness beyond test suites
- Repairing repository-scale defects
- Lowering computational costs

**Relevance to CompyMac**: Our agentic approach is validated but we should be aware of the latency/complexity trade-off. The challenge of "verifying semantic correctness beyond test suites" is exactly what our guardrailed system addresses.

---

## Implications for CompyMac

### Design Principles

1. **Test-First Verification**: Generate discriminative tests before claiming completion (Repair-R1 pattern)

2. **Neuro-Symbolic Feedback**: Combine LLM reasoning with static analysis and test execution (Meta's approach)

3. **History-Aware Context**: Use git blame and commit history for better localization (HAFixAgent)

4. **Iterative Refinement**: Draft -> Review -> Refine pattern for patches (REFINE)

5. **LLM-as-Judge**: Use separate LLM to validate patch quality before human review

### Integration Points

| APR Capability | CompyMac Component | Status |
|----------------|-------------------|--------|
| Fault localization | LSP tool + git blame | Partial |
| Patch generation | Edit tool | Implemented |
| Test execution | Bash tool | Implemented |
| Static analysis | LSP tool | Partial |
| Patch validation | Acceptance criteria | Implemented |

### Open Questions

1. **Test Generation Quality**: How do we ensure agent-generated tests are meaningful, not just passing?

2. **Verification Strength**: Can we use APR techniques to verify that claimed completions actually fix the underlying issue?

3. **Cost-Benefit**: When is full APR verification worth the token cost vs. simpler checks?

---

## References

- arXiv:2403.17134 - "RepairAgent: An Autonomous, LLM-Based Agent for Program Repair"
- arXiv:2507.18755 - "Agentic Program Repair from Test Failures at Scale"
- arXiv:2511.01047 - "HAFixAgent: History-Aware Automated Program Repair Agent"
- arXiv:2510.03588 - "REFINE: Enhancing Program Repair Agents through Context-Aware Patch Refinement"
- arXiv:2503.14713 - "TestForge: Feedback-Driven, Agentic Test Suite Generation"
- arXiv:2507.22853 - "Repair-R1: Better Test Before Repair"
- arXiv:2506.23749 - "A Survey of LLM-based Automated Program Repair"
