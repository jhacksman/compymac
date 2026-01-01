# Gap 3: Workflow Closure (Full SWE Loop) - Research Document

This document synthesizes arxiv research on SWE agent orchestration, failure recovery, and CI integration to inform the implementation of Gap 3.

## Executive Summary

Gap 3 aims to implement the full SWE loop: understand task -> plan -> modify code -> run tests/lint -> debug failures -> create PR -> respond to CI -> iterate. This research document identifies key patterns, architectures, and techniques from academic literature that should guide implementation.

## Key Research Papers

### 1. SWE-agent: Agent-Computer Interfaces (arXiv:2405.15793)

**Key Finding**: The Agent-Computer Interface (ACI) design significantly impacts agent performance. SWE-agent achieved 12.5% pass@1 on SWE-bench by designing interfaces specifically for LLM agents.

**Relevant Patterns**:
- Custom file editing commands (search/replace format outperforms unified diff)
- Repository navigation tools designed for agent context windows
- Test execution with structured output parsing
- Iterative refinement based on execution feedback

**Implementation Insight**: CompyMac should expose tools with agent-friendly interfaces, not just human-friendly ones.

### 2. HyperAgent: Generalist Multi-Agent System (OpenReview)

**Key Finding**: A four-agent architecture (Planner, Navigator, Code Editor, Executor) achieves 26% on SWE-Bench-Lite and 33% on SWE-Bench-Verified.

**Relevant Patterns**:
- **Planner Agent**: Decomposes high-level tasks into subtasks
- **Navigator Agent**: Locates relevant code in the repository
- **Code Editor Agent**: Makes targeted modifications
- **Executor Agent**: Runs tests and validates changes

**Implementation Insight**: Consider role specialization even within a single agent loop - different phases need different prompts/tools.

### 3. Confucius Code Agent (arXiv:2512.10398)

**Key Finding**: Scalable agent scaffolding requires hierarchical working memory, persistent note-taking, and modular tool extensions. Achieved 54.3% Resolve@1 on SWE-Bench-Pro.

**Relevant Patterns**:
- **Hierarchical Working Memory**: Long-context reasoning across large codebases
- **Persistent Note-Taking**: Cross-session continual learning
- **Meta-Agent**: Automates synthesis, evaluation, and refinement through build-test-improve loop

**Implementation Insight**: The "build-test-improve" loop is central - not just a linear workflow.

### 4. Agentic Program Repair at Scale (arXiv:2507.18755) - Meta

**Key Finding**: Meta's Engineering Agent achieves 42.3% solve rate using ReAct harness with 15 actions and average 11.8 feedback iterations. Neuro-symbolic approach combining LLM reasoning with static analysis and test execution feedback.

**Relevant Patterns**:
- **Rule-based Test Failure Triage**: Pre-filter failures before agent engagement
- **15 Action Set**: From reading files to generating patches
- **Static Analysis Feedback**: Symbolic information enhances neural reasoning
- **LLM-as-a-Judge**: Validates patches conform to standards before human review
- **Search-and-Replace Format**: Outperforms unified diff format

**Implementation Insight**: The feedback loop is critical - static analysis + test execution traces significantly improve solve rate.

### 5. RepairAgent: Autonomous Program Repair (arXiv:2403.17134)

**Key Finding**: First autonomous LLM-based agent for program repair. Fixed 164 bugs on Defects4J including 39 not fixed by prior techniques. Average cost: 270K tokens ($0.14) per bug.

**Relevant Patterns**:
- **Finite State Machine**: Guides agent through tool invocation
- **Dynamic Prompt Format**: Allows LLM to interact with tools based on gathered info
- **Interleaved Actions**: Freely interleaves gathering info, gathering repair ingredients, and validating fixes

**Implementation Insight**: Don't force a rigid linear workflow - let the agent decide when to gather more info vs attempt fixes.

### 6. PALADIN: Self-Correcting Agents for Tool Failures (arXiv:2509.25238)

**Key Finding**: Tool failures (timeouts, API exceptions, inconsistent outputs) cause cascading reasoning errors. PALADIN improves Recovery Rate from 32.76% to 89.68%.

**Relevant Patterns**:
- **Failure Injection Training**: Train on recovery-annotated trajectories
- **Failure Exemplar Bank**: 55+ failure patterns with recovery actions
- **Taxonomy-Aligned Recovery**: Match failures to known patterns and execute corresponding recovery

**Implementation Insight**: Build explicit failure recovery into the workflow - don't assume tools always succeed.

### 7. Agent Workflow Survey (arXiv:2508.01186)

**Key Finding**: Comprehensive taxonomy of agent workflow systems across functional capabilities and architectural features.

**Relevant Patterns**:
- **Functional Capabilities**: Planning, multi-agent collaboration, external API integration
- **Architectural Features**: Agent roles, orchestration flows, specification languages
- **Workflow Optimization**: Strategies for improving efficiency and reliability
- **Security Considerations**: Safe automation patterns

**Implementation Insight**: Consider both functional and architectural dimensions when designing the workflow.

### 8. SWE-EVO: Long-Horizon Software Evolution (arXiv:2512.18470)

**Key Finding**: Current agents struggle with sustained, multi-file reasoning. GPT-5 with OpenHands achieves only 21% on SWE-EVO vs 65% on SWE-Bench Verified.

**Relevant Patterns**:
- **Multi-step Modifications**: Average 21 files per task
- **Test Suite Validation**: Average 874 tests per instance
- **Fix Rate Metric**: Captures partial progress on complex tasks

**Implementation Insight**: Long-horizon tasks require different strategies than single-issue fixes.

### 9. Fault-Tolerant Sandboxing (arXiv:2512.12806)

**Key Finding**: Transactional approach to safe autonomous execution. 100% interception rate for high-risk commands, 100% rollback success rate, only 14.5% performance overhead.

**Relevant Patterns**:
- **Policy-based Interception**: Catch dangerous commands before execution
- **Transactional Filesystem Snapshots**: Atomic transactions for safety
- **Headless Operation**: No interactive authentication barriers

**Implementation Insight**: Safety mechanisms should not break autonomous operation.

### 10. Understanding LLM Agent Planning (arXiv:2402.02716)

**Key Finding**: Taxonomy of LLM-agent planning: Task Decomposition, Plan Selection, External Module, Reflection, Memory.

**Relevant Patterns**:
- **Task Decomposition**: Break complex tasks into subtasks
- **Plan Selection**: Choose among alternative approaches
- **External Module**: Leverage tools and APIs
- **Reflection**: Learn from failures and successes
- **Memory**: Maintain context across steps

**Implementation Insight**: All five capabilities are needed for robust workflow closure.

## Recommended Architecture for Gap 3

Based on the research, here is the recommended architecture:

### Workflow Stages (from HyperAgent + Meta patterns)

```
UNDERSTAND -> PLAN -> LOCATE -> MODIFY -> VALIDATE -> DEBUG -> PR -> CI -> ITERATE
```

1. **UNDERSTAND**: Parse task description, identify requirements
2. **PLAN**: Decompose into subtasks, prioritize
3. **LOCATE**: Navigate repository, find relevant files
4. **MODIFY**: Make code changes (search-replace format)
5. **VALIDATE**: Run tests, lint, type checks
6. **DEBUG**: Analyze failures, gather more info if needed
7. **PR**: Create pull request with description
8. **CI**: Poll CI status, parse logs
9. **ITERATE**: Fix CI failures, respond to review comments

### Key Components

#### 1. Workflow Orchestrator
```python
class SWEWorkflow:
    stages = [UNDERSTAND, PLAN, LOCATE, MODIFY, VALIDATE, DEBUG, PR, CI, ITERATE]
    
    def advance(self) -> bool:
        """Advance to next stage if current stage is complete."""
        
    def retry(self, max_attempts: int = 3) -> bool:
        """Retry current stage with different approach."""
        
    def get_artifacts(self) -> dict:
        """Return all artifacts from workflow execution."""
```

#### 2. Failure Recovery (from PALADIN)
```python
class FailureRecovery:
    failure_patterns: dict[str, RecoveryAction]
    
    def detect_failure(self, output: str) -> FailureType | None:
        """Detect failure type from tool output."""
        
    def get_recovery_action(self, failure: FailureType) -> RecoveryAction:
        """Get appropriate recovery action for failure type."""
```

#### 3. CI Integration (from Meta patterns)
```python
class CIIntegration:
    def poll_status(self, pr_url: str) -> CIStatus:
        """Poll CI status for PR."""
        
    def parse_logs(self, job_id: str) -> list[CIError]:
        """Parse CI logs for actionable errors."""
        
    def auto_fix(self, errors: list[CIError]) -> list[Fix]:
        """Generate fixes for common CI errors (lint, type)."""
```

#### 4. Artifact Storage (from Confucius patterns)
```python
class ArtifactStore:
    def store(self, stage: str, artifact: Artifact) -> str:
        """Store artifact and return ID."""
        
    def get_by_stage(self, stage: str) -> list[Artifact]:
        """Get all artifacts from a stage."""
        
    def get_history(self) -> list[Artifact]:
        """Get full artifact history for debugging."""
```

### Feedback Loop Design (Critical)

The research consistently shows that feedback loops are essential:

1. **Test Execution Feedback**: Run tests after each modification, parse results
2. **Static Analysis Feedback**: Run linters/type checkers, parse errors
3. **CI Feedback**: Poll CI status, parse logs for actionable errors
4. **LLM-as-Judge Feedback**: Validate patches meet quality standards

```
MODIFY -> VALIDATE -> [PASS] -> PR
                   -> [FAIL] -> DEBUG -> MODIFY (loop)
```

### Search-Replace Format (from Meta research)

Use search-replace format instead of unified diff:

```
<<<<<<< SEARCH
def old_function():
    return "old"
=======
def new_function():
    return "new"
>>>>>>> REPLACE
```

This format is more reliable for LLM-generated patches.

## Implementation Priorities

Based on research findings, implement in this order:

1. **Workflow State Machine**: Basic stage transitions with validation
2. **Test Execution Feedback**: Run tests, parse results, feed back to agent
3. **CI Integration**: Poll status, parse logs, generate fixes
4. **Failure Recovery**: Detect failures, apply recovery patterns
5. **Artifact Storage**: Store all outputs for debugging and review
6. **LLM-as-Judge**: Validate patches before PR creation

## Success Metrics (from research)

- **Solve Rate**: Percentage of tasks fully resolved
- **Fix Rate**: Partial progress metric for complex tasks
- **Feedback Iterations**: Average iterations to resolution
- **Cost**: Tokens/dollars per task
- **Latency**: Time to resolution

## References

1. Yang et al. "SWE-agent: Agent-Computer Interfaces Enable Automated Software Engineering" arXiv:2405.15793
2. Phan et al. "HyperAgent: Generalist Software Engineering Agents" OpenReview ICLR 2025
3. Wong et al. "Confucius Code Agent: Scalable Agent Scaffolding" arXiv:2512.10398
4. Maddila et al. "Agentic Program Repair from Test Failures at Scale" arXiv:2507.18755
5. Bouzenia et al. "RepairAgent: An Autonomous, LLM-Based Agent for Program Repair" arXiv:2403.17134
6. Vuddanti et al. "PALADIN: Self-Correcting Language Model Agents" arXiv:2509.25238
7. Yu et al. "A Survey on Agent Workflow" arXiv:2508.01186
8. Thai et al. "SWE-EVO: Benchmarking Coding Agents in Long-Horizon Software Evolution" arXiv:2512.18470
9. Yan "Fault-Tolerant Sandboxing for AI Coding Agents" arXiv:2512.12806
10. Huang et al. "Understanding the planning of LLM agents: A survey" arXiv:2402.02716
11. Hassan et al. "Agentic Software Engineering: Foundational Pillars and a Research Roadmap" arXiv:2509.06216
12. Li et al. "The Rise of AI Teammates in Software Engineering (SE) 3.0" arXiv:2507.15003
