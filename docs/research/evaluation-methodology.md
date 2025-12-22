# Evaluation Methodology Research

## Overview

This document summarizes research on LLM evaluation methodology, focusing on data contamination, benchmark gaming, and reproducibility. These concerns are critical for ensuring CompyMac measures real competence, not memorization or overfitting.

## Key Papers

### 1. Survey on Data Contamination (arXiv:2502.14425)

**Definition**: Data contamination is the unintended overlap between training and test datasets, which can artificially inflate model performance.

**Impact**:
- Overestimation of generalization capabilities
- Unreliable performance comparisons
- False confidence in model abilities

**Contamination-Free Evaluation Methods**:

1. **Data Updating**: Create new benchmarks with fresh data
2. **Data Rewriting**: Modify existing benchmarks to avoid memorization
3. **Prevention-Based**: Design benchmarks that resist contamination

**Detection Methods**:
- **White-Box**: Access to model weights (membership inference)
- **Gray-Box**: Access to model outputs (perplexity analysis)
- **Black-Box**: Only API access (behavioral tests)

**Key Insight**: "The reliability of performance evaluation has come under scrutiny due to data contamination—the unintended overlap between training and test datasets."

**Relevance to CompyMac**: When evaluating our agents, we must ensure test tasks weren't seen during training. Dynamic benchmarks may be necessary.

---

### 2. Static to Dynamic Evaluation (arXiv:2502.17521)

**Problem**: Static benchmarks become contaminated over time as they're included in training data.

**Solution**: Dynamic benchmarks that generate new test cases.

**Taxonomy**:
- **Static Benchmarks**: Fixed test sets (vulnerable to contamination)
- **Dynamic Benchmarks**: Generated test sets (resistant to contamination)

**Dynamic Benchmark Criteria**:
1. **Freshness**: New data not in training sets
2. **Diversity**: Cover range of capabilities
3. **Difficulty Calibration**: Consistent difficulty over time
4. **Reproducibility**: Same generation process yields comparable tests

**Key Insight**: "In the era of evaluating large language models (LLMs), data contamination has become an increasingly prominent concern. To address this data contamination risk, LLM benchmarking has evolved from a static to a dynamic paradigm."

**Relevance to CompyMac**: Our evaluation should include dynamic components - perhaps generating new tasks based on templates rather than using fixed test sets.

---

### 3. DCR: Quantifying Data Contamination (arXiv:2507.11405)

**Core Contribution**: Framework to detect and quantify contamination risk across four levels.

**Contamination Levels**:
1. **Semantic**: Similar meaning to training data
2. **Informational**: Same facts/knowledge
3. **Data**: Same examples
4. **Label**: Same answers

**DCR Factor**: Unified score that adjusts raw accuracy to reflect contamination-aware performance.

**Results**: DCR Factor adjusts accuracy to within 4% average error compared to uncontaminated baseline.

**Relevance to CompyMac**: We could use DCR-like analysis to understand how much our agent's performance is due to memorization vs. genuine capability.

---

### 4. How Much Can We Forget About Contamination? (ICML 2025)

**Key Finding**: Moderate amounts of contamination are forgotten by the end of LLM training runs.

**Scaling Analysis**:
- Number of model parameters (up to 1.6B)
- Number of times example is seen (up to 144)
- Number of training tokens (up to 40B)

**Key Insight**: "If model and data follow the Chinchilla scaling laws, minor contamination indeed leads to overfitting. At the same time, even 144 times of contamination can be forgotten if the training data is scaled beyond five times Chinchilla."

**Implication**: For modern LLMs trained on massive data, minor contamination may not be as problematic as feared.

**Relevance to CompyMac**: We shouldn't over-correct for contamination concerns, but should still use diverse evaluation methods.

---

### 5. Mitigation Strategies Assessment (arXiv:2503.16402)

**Title**: "The Emperor's New Clothes in Benchmarking?"

**Key Finding**: No existing mitigation strategy significantly improves contamination resistance across all benchmarks.

**Metrics Proposed**:
1. **Fidelity**: Does modified benchmark still measure the same capability?
2. **Contamination Resistance**: Does modification prevent memorization?

**Conclusion**: "None effectively balances fidelity and contamination resistance."

**Relevance to CompyMac**: We should be skeptical of claims that benchmark modifications solve contamination. Multiple evaluation approaches are needed.

---

### 6. Benchmark Data Contamination Survey (arXiv:2406.04244)

**Comprehensive Review** of contamination in LLM evaluation.

**Alternative Assessment Methods**:
1. **Human Evaluation**: Gold standard but expensive
2. **LLM-as-Judge**: Scalable but potentially biased
3. **Behavioral Tests**: Probe for specific capabilities
4. **Adversarial Evaluation**: Test edge cases and failures

**Key Insight**: "The rapid development of Large Language Models (LLMs) like GPT-4, Claude-3, and Gemini has transformed the field of natural language processing. However, it has also resulted in a significant issue known as Benchmark Data Contamination (BDC)."

**Relevance to CompyMac**: We should use multiple evaluation methods, not rely on single benchmarks.

---

## Implications for CompyMac

### Evaluation Strategy

Based on the research, CompyMac evaluation should include:

1. **Dynamic Task Generation**: Generate new tasks from templates rather than using fixed test sets

2. **Multi-Method Evaluation**: Combine automated benchmarks with human evaluation and behavioral tests

3. **Contamination Awareness**: Track which tasks might be contaminated and weight results accordingly

4. **Capability Probing**: Test specific capabilities in isolation, not just end-to-end performance

### Evaluation Framework

```python
class EvaluationFramework:
    """Multi-method evaluation for CompyMac agents."""
    
    def evaluate_task(self, agent, task) -> EvaluationResult:
        """Evaluate agent on a single task."""
        
        # 1. Automated execution
        execution_result = self.run_task(agent, task)
        
        # 2. Contamination check
        contamination_risk = self.check_contamination(task)
        
        # 3. Capability probing
        capability_scores = self.probe_capabilities(agent, task)
        
        # 4. Behavioral tests
        behavioral_results = self.run_behavioral_tests(agent, task)
        
        return EvaluationResult(
            success=execution_result.success,
            contamination_risk=contamination_risk,
            capabilities=capability_scores,
            behavioral=behavioral_results,
            adjusted_score=self.compute_adjusted_score(...)
        )
```

### Dynamic Task Templates

```yaml
# Template for file editing tasks
file_edit_template:
  description: "Edit {file_type} file to {change_type}"
  parameters:
    file_type: [python, javascript, typescript, rust]
    change_type: [add_function, fix_bug, refactor, add_tests]
  generation:
    - Create fresh file content
    - Define specific change requirement
    - Generate expected outcome
  
# Template for debugging tasks
debug_template:
  description: "Fix {bug_type} in {context}"
  parameters:
    bug_type: [type_error, logic_error, off_by_one, null_reference]
    context: [function, class, module]
  generation:
    - Generate buggy code
    - Define expected behavior
    - Generate test cases
```

### Metrics to Track

| Metric | Description | Purpose |
|--------|-------------|---------|
| Raw Success Rate | Tasks completed successfully | Basic performance |
| Adjusted Success Rate | Success rate weighted by contamination risk | True capability |
| Capability Coverage | Which capabilities are demonstrated | Completeness |
| Failure Analysis | Why tasks fail | Improvement guidance |
| Generalization Gap | Performance on novel vs. familiar tasks | Memorization detection |

### Red Flags for Contamination

1. **Perfect Performance on Old Benchmarks**: Suspiciously high scores on well-known benchmarks
2. **Verbatim Reproduction**: Agent produces exact text from training data
3. **Inconsistent Capability**: High performance on benchmarks, low on novel tasks
4. **Pattern Matching**: Agent recognizes task format rather than understanding task

---

## Open Questions

1. **Dynamic Benchmark Design**: How do we generate tasks that are both novel and meaningful?

2. **Capability Isolation**: How do we test specific capabilities without confounding factors?

3. **Human Evaluation Scale**: How do we get human evaluation at scale without prohibitive cost?

4. **Contamination Detection**: How do we detect contamination without access to training data?

---

## References

- arXiv:2502.14425 - "A Survey on Data Contamination for Large Language Models"
- arXiv:2502.17521 - "Benchmarking Large Language Models Under Data Contamination: A Survey from Static to Dynamic Evaluation"
- arXiv:2507.11405 - "DCR: Quantifying Data Contamination in LLMs Evaluation"
- ICML 2025 - "How Much Can We Forget about Data Contamination?"
- arXiv:2503.16402 - "The Emperor's New Clothes in Benchmarking? A Rigorous Examination of Mitigation Strategies"
- arXiv:2406.04244 - "Benchmark Data Contamination of Large Language Models: A Survey"
- arXiv:2411.03923 - "Evaluation data contamination in LLMs: how do we measure it and (when) does it matter?"
