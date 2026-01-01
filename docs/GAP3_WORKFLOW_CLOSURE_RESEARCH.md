# Gap 3: Workflow Closure (Full SWE Loop) - Comprehensive Research Document

This document synthesizes arxiv research, competitive analysis of Manus/Devin, and inventory of existing CompyMac infrastructure to inform the implementation of Gap 3.

## Implementation Status (Updated 2025-12-27)

**Status: INFRASTRUCTURE COMPLETE - END-TO-END VALIDATION PENDING**

### Completed PRs:
- **PR #167**: Phase 1 & 2 - Basic SWEWorkflow integration + Failure Recovery
- **PR #168**: Phase 3 & 4 - CI Integration + Validation Integration  
- **PR #169**: Bug fix - CI log fetching (`_fetch_job_logs()`)

### What's Implemented:
- SWEWorkflow integrated into AgentLoop (enabled via `use_swe_workflow=True`)
- Stage prompts injected into context at each workflow stage
- Failure recovery detects tool failures and suggests recovery actions
- PR URL detection from tool output (regex-based)
- CI status polling via `gh pr checks` 
- CI log fetching via `gh run view --log` for failed checks
- CI error parsing (lint, type, test, build errors)
- Validation stage runs tests/lint via SWEWorkflow methods
- Error summaries injected into agent context

### What's NOT Yet Validated:
- **End-to-end test with real LLM**: The full workflow (agent creates PR → CI fails → logs fetched → errors parsed → agent fixes) has NOT been tested with a real LLM call
- **`gh` CLI availability**: CI polling requires `gh` CLI installed and authenticated; this was not testable in the Devin environment (blocked)
- **Real-world task completion**: No SWE-bench or production task has been run through the full workflow

### Next Steps for Full Validation:
1. Run end-to-end test with Venice API on a task that requires PR creation
2. Verify CI polling works in production environment with `gh` CLI
3. Confirm error parsing produces actionable summaries
4. Test ITERATE stage loop (CI fail → fix → re-push → CI pass)

---

## 1. Executive Summary

Gap 3 aims to implement the full SWE loop: understand task -> plan -> modify code -> run tests/lint -> debug failures -> create PR -> respond to CI -> iterate. This research document identifies key patterns, architectures, and techniques from academic literature and production systems that should guide implementation.

**Key Finding:** CompyMac already has substantial Gap 3 infrastructure (`swe_loop.py`, `failure_recovery.py`, `ci_integration.py`, `artifact_store.py`) but it is NOT wired into the main `AgentLoop`. The primary work is integration, not new implementation.

**Success Criteria:**
- SWEWorkflow integrated into AgentLoop
- End-to-end test demonstrating full workflow
- Real-world validation on at least one task
- Feedback loops (test, lint, CI) operational

## 2. Problem Definition

### 2.1 What Manus/Devin Do

**Manus Architecture (from official blog and technical analysis):**
- **Agent Loop:** Iterative cycle of analyze -> plan -> execute -> observe
- **Planner Module:** Breaks high-level objectives into ordered steps with status tracking
- **Knowledge Module:** Provides relevant reference information and best-practice guidelines
- **File-Based Memory:** Tracks progress and stores information across operations
- **CodeAct Approach:** Uses executable Python code as action mechanism
- **Multi-Model Invocation:** Uses different models for different sub-tasks (Claude for reasoning, GPT-4 for coding)
- **Context Engineering:** KV-cache optimization is "single most important metric" - 10x cost difference between cached/uncached tokens

**Devin Architecture (from public sources):**
- Persistent VM workspace with full development environment
- Browser automation for documentation lookup
- Git integration for PR creation and CI monitoring
- Iterative debugging with test feedback
- Session continuity across interruptions

### 2.2 What CompyMac Currently Has

**Existing Infrastructure (NOT integrated into AgentLoop):**

1. **`swe_loop.py`** (535 lines):
   - `SWEWorkflow` class with stages: UNDERSTAND -> PLAN -> LOCATE -> MODIFY -> VALIDATE -> DEBUG -> PR -> CI -> ITERATE -> COMPLETE
   - `StageResult` for tracking stage outcomes
   - `advance()` method for stage transitions
   - `retry()` method with backoff
   - `get_stage_prompt()` for stage-specific instructions
   - `run_tests()` and `run_lint()` for validation
   - Serialization/deserialization for persistence

2. **`failure_recovery.py`** (569 lines):
   - `FailureType` enum: TIMEOUT, API_ERROR, RATE_LIMIT, SYNTAX_ERROR, IMPORT_ERROR, TYPE_ERROR, TEST_FAILURE, LINT_ERROR, MERGE_CONFLICT, etc.
   - `RecoveryAction` with action_type: retry, fix, skip, escalate
   - `FailureRecovery` class with 40+ failure patterns (based on PALADIN)
   - `detect_failure()` from tool output
   - `get_recovery_action()` for pattern-matched recovery
   - `suggest_fix()` for actionable suggestions

3. **`ci_integration.py`** (418 lines):
   - `CIStatus` enum: PENDING, RUNNING, PASSED, FAILED
   - `CIError` with file_path, line_number, rule, suggestion
   - `CIIntegration` class with `poll_status()`, `parse_logs()`, `auto_fix()`
   - `wait_for_ci()` with timeout and polling
   - `summarize_errors()` for agent-friendly output

4. **`artifact_store.py`** (423 lines):
   - `ArtifactType` enum for typed storage
   - `Artifact` with metadata and content
   - `ArtifactStore` with indexing by stage/type
   - Persistence to disk

**What's Missing:**
- Integration with `AgentLoop` - SWEWorkflow is never instantiated or used
- No end-to-end tests demonstrating the workflow
- No real-world validation data

## 3. Key Research Papers

### 3.1 Core SWE Agent Papers

**SWE-agent (arXiv:2405.15793):**
- Agent-Computer Interface (ACI) design significantly impacts performance
- 12.5% pass@1 on SWE-bench with custom file editing commands
- Search-replace format outperforms unified diff
- Key insight: Design interfaces for LLM agents, not humans

**HyperAgent (OpenReview ICLR 2025):**
- Four-agent architecture: Planner, Navigator, Code Editor, Executor
- 26% on SWE-Bench-Lite, 33% on SWE-Bench-Verified
- Role specialization improves performance
- Key insight: Different phases need different prompts/tools

**Meta Engineering Agent (arXiv:2507.18755):**
- 42.3% solve rate with ReAct harness and 15 actions
- Average 11.8 feedback iterations per task
- Rule-based test failure triage before agent engagement
- LLM-as-a-Judge validates patches before human review
- Key insight: Feedback loops are critical - static analysis + test execution traces significantly improve solve rate

**RepairAgent (arXiv:2403.17134):**
- First autonomous LLM-based agent for program repair
- Fixed 164 bugs on Defects4J including 39 not fixed by prior techniques
- FSM-guided tool invocation
- Average cost: 270K tokens ($0.14) per bug
- Key insight: Don't force rigid linear workflow - let agent decide when to gather info vs attempt fixes

**PALADIN (arXiv:2509.25238):**
- Tool failures cause cascading reasoning errors
- Improves Recovery Rate from 32.76% to 89.68%
- 55+ failure patterns with recovery actions
- Key insight: Build explicit failure recovery into workflow

**Confucius Code Agent (arXiv:2512.10398):**
- Scalable agent scaffolding with hierarchical working memory
- 54.3% Resolve@1 on SWE-Bench-Pro
- Persistent note-taking for cross-session learning
- Key insight: "Build-test-improve" loop is central

### 3.2 Long-Horizon and Evolution Papers

**SWE-Bench Pro (arXiv:2509.16941):**
- 1,865 problems from 41 repositories
- Long-horizon tasks requiring hours to days for humans
- Multi-file patches with substantial code modifications
- Key insight: Current agents struggle with sustained, multi-file reasoning

**SWE-EVO (arXiv:2512.18470):**
- Benchmarks long-horizon software evolution
- GPT-5 with OpenHands achieves only 21% vs 65% on SWE-Bench Verified
- Average 21 files per task, 874 tests per instance
- Proposes "Fix Rate" metric for partial progress
- Key insight: Long-horizon tasks require different strategies than single-issue fixes

**Live-SWE-agent (arXiv:2511.13646):**
- First "live" software agent that evolves itself on-the-fly
- Starts with basic bash tools, autonomously evolves scaffold
- 75.4% solve rate on SWE-bench Verified without test-time scaling
- Key insight: Self-improving agents can outperform static designs

**LoCoBench-Agent (arXiv:2511.13998):**
- Interactive benchmark for long-context software engineering
- 8,000 scenarios, 10 languages, 8 categories
- Three-tier adaptive context compression
- Hierarchical memory architecture
- 9 bias-free evaluation metrics
- Key insight: Long-context management is critical for complex tasks

### 3.3 Orchestration and Workflow Papers

**AgentOrchestra (arXiv:2506.12508):**
- TEA (Tool-Environment-Agent) Protocol
- Hierarchical multi-agent with central planning agent
- Tool manager agent for dynamic tool creation/retrieval
- 83.39% on GAIA benchmark
- Key insight: Treat environments and agents as first-class resources

**Orchestrated Distributed Intelligence (arXiv:2503.13754):**
- Multi-loop feedback mechanisms
- High cognitive density framework
- Transforms static systems into dynamic, action-oriented environments
- Key insight: Orchestration layers enable cohesive agent networks

**Manager Agent (arXiv:2510.02557):**
- Autonomous Manager Agent for workflow orchestration
- Decomposes goals into task graphs
- Allocates tasks to human and AI workers
- Formalizes workflow as Partially Observable Stochastic Game
- Key insight: Workflow management is a difficult open problem

**Agent Workflow Survey (arXiv:2508.01186):**
- Comprehensive taxonomy of agent workflow systems
- Functional capabilities: Planning, multi-agent collaboration, external API integration
- Architectural features: Agent roles, orchestration flows, specification languages
- Key insight: Consider both functional and architectural dimensions

**Fault-Tolerant Sandboxing (arXiv:2512.12806):**
- Transactional approach to safe autonomous execution
- 100% interception rate for high-risk commands
- 100% rollback success rate, only 14.5% performance overhead
- Key insight: Safety mechanisms should not break autonomous operation

**Understanding LLM Agent Planning (arXiv:2402.02716):**
- Taxonomy: Task Decomposition, Plan Selection, External Module, Reflection, Memory
- Key insight: All five capabilities needed for robust workflow closure

## 4. Manus/Devin Workflow Patterns

### 4.1 Manus Context Engineering (from official blog)

**KV-Cache Optimization:**
- "Single most important metric for production-stage AI agent"
- Cached tokens cost 0.30 USD/MTok vs 3 USD/MTok uncached (10x difference)
- Average input-to-output ratio is 100:1 in Manus

**Best Practices:**
1. Keep prompt prefix stable (no timestamps at beginning)
2. Make context append-only (don't modify previous actions/observations)
3. Ensure deterministic serialization (stable JSON key ordering)
4. Mark cache breakpoints explicitly

**Tool Management:**
- Avoid dynamically adding/removing tools mid-iteration
- Tool definitions at front of context affect cache
- Use tool masking instead of removal

### 4.2 Manus Agent Loop

```
1. Analyze: Parse current state and user request from event stream
2. Plan: Select action (which tool/operation to use)
3. Execute: Run action in sandbox
4. Observe: Append result to event stream
5. Repeat until task complete
```

**Key Constraints:**
- One tool action per iteration
- Must await result before next step
- Planner generates ordered step list with status tracking
- Knowledge module injects relevant guidelines

### 4.3 Devin Workflow Patterns

- Persistent VM with full dev environment
- Browser for documentation lookup
- Git integration for PR/CI
- Iterative debugging with test feedback
- Session continuity across interruptions

## 5. Recommended Architecture for Gap 3 Integration

### 5.1 Integration Approach

The primary work is wiring existing infrastructure into AgentLoop, not building new components.

**Option A: Workflow-Driven AgentLoop (Recommended)**
- AgentLoop instantiates SWEWorkflow for SWE tasks
- Each agent turn advances workflow stage
- Stage prompts injected into context
- Failure recovery triggered on tool errors
- CI integration polls after PR creation

**Option B: Workflow as Tool**
- SWEWorkflow exposed as a tool the agent can call
- Agent decides when to advance stages
- More flexible but less structured

**Option C: Hybrid**
- Workflow provides guidance but agent can deviate
- Stage prompts as suggestions, not requirements
- Best of both worlds but more complex

### 5.2 Integration Points

1. **AgentLoop.__init__()**: Optionally instantiate SWEWorkflow
2. **AgentLoop.run_step()**: Check workflow stage, inject stage prompt
3. **AgentLoop.run()**: After tool execution, check for failures and trigger recovery
4. **Harness**: Add workflow-aware tool filtering (only show relevant tools per stage)

### 5.3 Workflow Stages (from existing swe_loop.py)

```
UNDERSTAND -> PLAN -> LOCATE -> MODIFY -> VALIDATE -> DEBUG -> PR -> CI -> ITERATE -> COMPLETE
```

**Stage Transitions:**
- Normal: UNDERSTAND -> PLAN -> LOCATE -> MODIFY -> VALIDATE -> PR -> CI -> COMPLETE
- On validation failure: VALIDATE -> DEBUG -> MODIFY (loop)
- On CI failure: CI -> ITERATE -> MODIFY (loop)
- Max iterations before FAILED

### 5.4 Feedback Loop Design

```
MODIFY -> VALIDATE -> [PASS] -> PR -> CI -> [PASS] -> COMPLETE
                   -> [FAIL] -> DEBUG -> MODIFY (loop)
                                         -> CI -> [FAIL] -> ITERATE -> MODIFY (loop)
```

**Feedback Sources:**
1. Test execution (pytest output parsing)
2. Static analysis (ruff, mypy output parsing)
3. CI status (GitHub Actions polling)
4. LLM-as-Judge (optional, for patch quality)

### 5.5 Search-Replace Format (from Meta research)

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

## 6. Implementation Roadmap

### Phase 1: Basic Integration (MVP)
1. Add `workflow: SWEWorkflow | None` to AgentConfig
2. Instantiate workflow in AgentLoop.__init__() when enabled
3. Inject stage prompt at start of each turn
4. Advance workflow on successful tool execution
5. Add integration test demonstrating full loop

**Success Criteria:**
- Agent can complete UNDERSTAND -> PLAN -> LOCATE -> MODIFY -> VALIDATE -> PR flow
- Stage prompts visible in agent context
- Workflow state persisted across turns

### Phase 2: Failure Recovery Integration
1. Wrap tool execution with failure detection
2. On failure, consult FailureRecovery for action
3. Inject recovery suggestion into context
4. Track recovery stats

**Success Criteria:**
- Common failures (syntax error, import error) trigger recovery
- Recovery rate > 50% for known patterns

### Phase 3: CI Integration
1. After PR creation, poll CI status
2. Parse CI logs for actionable errors
3. Inject error summary into context
4. Advance to ITERATE stage on CI failure

**Success Criteria:**
- Agent waits for CI after PR creation
- CI failures trigger iteration loop
- Lint/type errors auto-fixed

### Phase 4: Validation and Metrics
1. Run on SWE-bench subset (10 tasks)
2. Measure solve rate, fix rate, iterations
3. Compare to baseline (no workflow)
4. Document findings

**Success Criteria:**
- Solve rate > 0% (any improvement over baseline)
- Clear metrics for future comparison

## 7. Evaluation Plan

### 7.1 Metrics (from research)

- **Solve Rate:** Percentage of tasks fully resolved
- **Fix Rate:** Partial progress metric for complex tasks
- **Feedback Iterations:** Average iterations to resolution
- **Cost:** Tokens/dollars per task
- **Latency:** Time to resolution
- **Recovery Rate:** Percentage of failures recovered

### 7.2 Test Cases

1. **Simple bug fix:** Single file, clear error message
2. **Multi-file change:** Requires locating related files
3. **Test failure:** Requires debugging and iteration
4. **CI failure:** Requires responding to lint/type errors
5. **Long-horizon:** Multiple steps, sustained reasoning

### 7.3 Baseline Comparison

- Run same tasks with and without SWEWorkflow
- Measure improvement in solve rate and iterations
- Document qualitative differences in agent behavior

## 8. References

### Academic Papers
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
11. Deng et al. "SWE-Bench Pro: Can AI Agents Solve Long-Horizon Software Engineering Tasks?" arXiv:2509.16941
12. Xia et al. "Live-SWE-agent: Can Software Engineering Agents Self-Evolve on the Fly?" arXiv:2511.13646
13. Qiu et al. "LoCoBench-Agent: An Interactive Benchmark for LLM Agents in Long-Context Software Engineering" arXiv:2511.13998
14. Zhang et al. "AgentOrchestra: Orchestrating Hierarchical Multi-Agent Intelligence with TEA Protocol" arXiv:2506.12508
15. Tallam "Orchestrated Distributed Intelligence" arXiv:2503.13754
16. Masters et al. "Orchestrating Human-AI Teams: The Manager Agent" arXiv:2510.02557

### Industry Sources
17. Manus Blog "Context Engineering for AI Agents: Lessons from Building Manus" https://manus.im/blog/Context-Engineering-for-AI-Agents-Lessons-from-Building-Manus
18. Manus Technical Analysis (renschni) https://gist.github.com/renschni/4fbc70b31bad8dd57f3370239dccd58f
19. GitHub Next "Agentic Workflows" https://githubnext.com/projects/agentic-workflows/

## 9. Appendix: Existing CompyMac Code Inventory

### A.1 swe_loop.py Key Classes

```python
class WorkflowStage(Enum):
    UNDERSTAND, PLAN, LOCATE, MODIFY, VALIDATE, DEBUG, PR, CI, ITERATE, COMPLETE, FAILED

class SWEWorkflow:
    task_description: str
    repo_path: Path
    current_stage: WorkflowStage
    status: WorkflowStatus
    stage_results: list[StageResult]
    
    def advance(self, result: StageResult) -> bool
    def retry(self, max_attempts: int = 3) -> bool
    def get_stage_prompt(self) -> str
    def run_tests(self, test_command: str | None = None) -> tuple[bool, str, list[str]]
    def run_lint(self, lint_command: str | None = None) -> tuple[bool, str, list[str]]
```

### A.2 failure_recovery.py Key Classes

```python
class FailureType(Enum):
    TIMEOUT, API_ERROR, RATE_LIMIT, AUTH_ERROR, NETWORK_ERROR,
    SYNTAX_ERROR, IMPORT_ERROR, TYPE_ERROR, RUNTIME_ERROR,
    TEST_FAILURE, ASSERTION_ERROR, FIXTURE_ERROR,
    LINT_ERROR, FORMAT_ERROR,
    MERGE_CONFLICT, PUSH_REJECTED, BRANCH_EXISTS,
    CI_TIMEOUT, CI_BUILD_FAILED, CI_TEST_FAILED, CI_LINT_FAILED,
    UNKNOWN

class FailureRecovery:
    FAILURE_PATTERNS: dict[str, tuple[FailureType, RecoveryAction]]  # 40+ patterns
    
    def detect_failure(self, output: str) -> FailureType | None
    def get_recovery_action(self, failure_type: FailureType, output: str) -> RecoveryAction
    def suggest_fix(self, failure_type: FailureType, error_message: str) -> str
```

### A.3 ci_integration.py Key Classes

```python
class CIIntegration:
    def poll_status(self, pr_url: str) -> tuple[CIStatus, list[CICheckResult]]
    def parse_logs(self, log_content: str) -> list[CIError]
    def auto_fix(self, errors: list[CIError]) -> list[Fix]
    def wait_for_ci(self, pr_url: str, timeout_seconds: int = 600) -> tuple[CIStatus, list[CICheckResult]]
    def summarize_errors(self, errors: list[CIError]) -> str
```

### A.4 AgentLoop Integration Points

```python
class AgentConfig:
    # Add these for workflow integration:
    use_swe_workflow: bool = False
    swe_task_description: str = ""
    swe_repo_path: str = ""

class AgentLoop:
    # Add these:
    _swe_workflow: SWEWorkflow | None = None
    _failure_recovery: FailureRecovery | None = None
    _ci_integration: CIIntegration | None = None
    
    def __init__(self, ...):
        if self.config.use_swe_workflow:
            self._swe_workflow = SWEWorkflow(
                task_description=self.config.swe_task_description,
                repo_path=Path(self.config.swe_repo_path),
            )
            self._failure_recovery = FailureRecovery()
            self._ci_integration = CIIntegration(Path(self.config.swe_repo_path))
    
    def run_step(self) -> tuple[str | None, list[ToolResult]]:
        # Inject stage prompt if workflow active
        if self._swe_workflow:
            stage_prompt = self._swe_workflow.get_stage_prompt()
            # Inject into context...
        
        # Execute tools...
        
        # Check for failures and trigger recovery
        if self._failure_recovery:
            for result in tool_results:
                failure = self._failure_recovery.detect_failure(result.content)
                if failure:
                    recovery = self._failure_recovery.get_recovery_action(failure, result.content)
                    # Inject recovery suggestion...
```
