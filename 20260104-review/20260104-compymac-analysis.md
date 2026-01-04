# CompyMac Architecture Analysis

**Date:** 2026-01-04
**Purpose:** Comprehensive analysis of CompyMac's current state, architecture, and capabilities

## Executive Summary

CompyMac is a proof-of-concept autonomous software engineering agent built on "honest constraints" - a philosophy that faithfully represents the fundamental limitations of LLM-based agents rather than hiding them. The project has evolved through V1-V5 iterations, with significant infrastructure already built but production hardening still needed.

## Core Philosophy

CompyMac distinguishes itself through **observable cognition** and **explicit constraints**:

1. **Session-bounded state**: All state discarded when session ends (no hidden persistence)
2. **Fixed context window**: Naive truncation when budget exceeded (information is LOST, not summarized)
3. **Tool-mediated actions**: Agent can only affect the world through explicit tool calls
4. **Turn-based processing**: No background processing between turns
5. **No learning**: Model weights don't update from interactions

This philosophy contrasts with commercial agents that may hide complexity or claim capabilities they don't reliably have.

## Architecture Overview

### Core Components

```
┌─────────────────────────────────────────────────────────────┐
│                     User Interfaces                         │
│  • FastAPI WebSocket Server (api/server.py)                │
│  • Next.js Web UI (web/src/)                               │
│  • CLI Run Viewer (cli/run_viewer.py)                      │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                   Agent Execution Core                      │
│  • AgentLoop: Orchestrates LLM + tools (agent_loop.py)     │
│  • LocalHarness: Executes 60+ tools (local_harness.py)     │
│  • SWEPhaseState: Phase-based workflow (swe_workflow.py)   │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│              Observability & Persistence                    │
│  • TraceStore: OTel-style spans + PROV lineage             │
│  • ArtifactStore: Content-addressed blob storage           │
│  • RunStore: Session persistence for pause/resume          │
│  • EventLog: Summary event stream                          │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│               Memory & Knowledge                            │
│  • MemoryManager: Context compression at 80% utilization   │
│  • KnowledgeStore: Factual memory with embeddings          │
│  • HybridRetriever: Sparse+Dense search with RRF merge     │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│            Evaluation & Verification                        │
│  • SWEBenchRunner: Task evaluation with inter-attempt learning│
│  • VerificationEngine: Contract-driven tool validation     │
│  • Evidence-based gating: Prevents false success claims    │
└─────────────────────────────────────────────────────────────┘
```

### Key Source Files

| File | Lines | Purpose |
|------|-------|---------|
| `local_harness.py` | 6,450 | Tool execution with 60+ registered tools |
| `trace_store.py` | 1,593 | OTel-style tracing with PROV lineage |
| `swe_workflow.py` | 1,445 | Phase-based SWE workflow enforcement |
| `agent_loop.py` | 1,095 | Turn-based agent execution loop |
| `multi_agent.py` | ~700 | Manager/Planner/Executor/Reflector coordination |
| `parallel.py` | ~676 | Fork-join parallelism with conflict detection |
| `browser.py` | ~1,100 | Playwright-based browser automation |

## Version History & Evolution

### V1: Initial Phase Enforcement
- Basic SWE workflow phases: LOCALIZATION → UNDERSTANDING → FIX → VERIFICATION
- Phase-based tool restrictions and budgets
- Foundation for structured agent behavior

### V2: Regression-Aware Verification
- Split verification into REGRESSION_CHECK and TARGET_FIX_VERIFICATION
- Separate pass_to_pass vs fail_to_pass test tracking
- Addressed test overfitting problem (arxiv:2511.16858)

### V3: Natural Workflow Completion
- Merged COMPLETE phase into TARGET_FIX_VERIFICATION
- Agent calls `complete()` directly when tests pass
- Eliminated awkward extra phase transition

### V4: Evidence-Based Gating (Current)
- Prevents claiming `fail_to_pass_status='all_passed'` without proof
- Validates bash execution history (command, exit_code, timestamp)
- Ensures tests run AFTER last code edit
- Validated on real SWE-bench tasks: 1/3 resolution rate, no false positives

### V5: Metacognitive Architecture (In Progress)
- `<think>` tool for private reasoning scratchpad
- CognitiveEvent tracking in trace store
- Temptation awareness framework (T1-T8 documented temptations)
- Required thinking scenarios before critical decisions
- Thinking compliance validation

## Phase-Based Workflow System

CompyMac enforces a structured workflow for SWE tasks:

```
LOCALIZATION (15 tool calls)
    ↓ Required: suspect_files, hypothesis
UNDERSTANDING (20 tool calls)
    ↓ Required: root_cause
FIX (15 tool calls)
    ↓ Required: modified_files
REGRESSION_CHECK (10 tool calls)
    ↓ Required: pass_to_pass_status
    ↓ Can return to FIX if regressions detected
TARGET_FIX_VERIFICATION (5 tool calls)
    ↓ Required: fail_to_pass_status
    → Call complete() when tests pass
```

### Phase Budget Enforcement
- Each phase has a maximum tool call budget
- Budget-neutral tools: `think`, `advance_phase`, `get_phase_status`, `complete`
- Phase-neutral tools: `think`, `advance_phase`, `get_phase_status`
- Allowed tools vary by phase (e.g., `Edit` only in FIX phase)

### Evidence-Based Gating (V4)
```python
def validate_test_evidence(self, test_status: str, test_type: str) -> tuple[bool, str]:
    """
    Validates:
    1. A bash command was run that matches test patterns
    2. That command had exit_code=0 (tests passed)
    3. No code edits happened after that test run
    """
```

## Metacognitive Architecture (V5)

### The `<think>` Tool
- Private reasoning scratchpad (user never sees content)
- Captured in trace store for analysis
- Budget-neutral and phase-neutral
- Loop detection: max 3 consecutive think calls before forced action

### Required Thinking Scenarios
1. Before git/GitHub operations
2. Before transitioning UNDERSTANDING → FIX
3. Before claiming completion
4. After 3+ failed attempts
5. When tests/lint/CI fail
6. Before modifying tests

### Temptation Catalog (T1-T8)
| ID | Name | Description |
|----|------|-------------|
| T1 | Claiming Victory | Calling complete() without running tests |
| T2 | Premature Editing | Making changes before understanding context |
| T3 | Test Overfitting | Modifying tests to pass instead of fixing code |
| T4 | Infinite Loop | Repeating failed approach without new info |
| T5 | Environment Avoidance | Trying to fix env issues instead of reporting |
| T6 | Library Assumption | Using libraries without checking availability |
| T7 | Skipping References | Editing without checking all references |
| T8 | Sycophancy | Agreeing with user instead of validating |

## Observability Infrastructure

### TraceStore (OTel-style)
- Append-only event log with SPAN_START/SPAN_END pairs
- W3C PROV-style lineage: USED, WAS_GENERATED_BY, WAS_DERIVED_FROM
- Content-addressed artifact storage with SHA-256 hashing
- Checkpoint/resume/fork capabilities
- Secret redaction via SecretScanner

### Span Types
- `AGENT_TURN`: Main loop iteration
- `LLM_CALL`: LLM request/response
- `TOOL_CALL`: Tool execution
- `REASONING`: Think tool usage
- `BROWSER_SESSION`: Browser automation
- `MEMORY_OPERATION`: Memory compression

### CognitiveEvent (V5)
```python
@dataclass
class CognitiveEvent:
    event_type: str  # "think", "temptation_awareness", "decision_point", "reflection"
    timestamp: float
    phase: str | None
    content: str
    metadata: dict[str, Any]
```

## Tool System

### Tool Categories
- **CORE**: Read, Write, Edit, bash, grep, glob, think, message_user
- **SHELL**: bash_output, write_to_shell, kill_shell, wait
- **GIT_LOCAL**: git_status, git_diff_*, git_commit, git_add
- **GIT_REMOTE**: git_view_pr, git_create_pr, git_pr_checks
- **BROWSER**: browser_navigate, browser_view, browser_click, etc.
- **SEARCH**: web_search, web_get_contents
- **LSP**: lsp_tool (goto_definition, goto_references, hover_symbol)
- **TODO**: TodoCreate, TodoRead, TodoStart, TodoClaim, TodoVerify
- **AI**: ask_smart_friend, visual_checker

### ActiveToolset
Dynamic tool enabling/disabling at runtime:
- Core tools always enabled unless explicitly disabled
- Categories can be enabled/disabled
- Individual tools can be explicitly enabled/disabled

### Menu System
Hierarchical tool discovery to reduce context size:
- ROOT level: only navigation tools
- Modes: swe, browser, git, search
- `menu_enter(mode)` / `menu_exit()` for navigation

## Memory System

### MemoryManager
- Compresses context when utilization > 80%
- Keeps recent N turns (configurable)
- Extracts MemoryFacts during compression
- LLM-generated summaries for older content

### MemoryFacts
Structured information preserved during compression:
- Files touched
- Commands run
- Errors encountered
- Key decisions made

### HybridRetriever
- Sparse search (keyword/BM25)
- Dense search (vector similarity via Venice.ai embeddings)
- RRF (Reciprocal Rank Fusion) merge
- Metadata filtering and reranking

## Multi-Agent System

### ManagerAgent (FSM Orchestrator)
States: PLANNING → EXECUTING → REFLECTING → COMPLETED/FAILED

Coordinates:
- **PlannerAgent**: Creates execution plans
- **ExecutorAgent**: Executes plan steps
- **ReflectorAgent**: Evaluates results, recommends actions

### ReflectionAction
- CONTINUE: Proceed to next step
- RETRY_SAME: Retry current step
- RETRY_WITH_CHANGES: Retry with modifications
- GATHER_INFO: Need more information
- REPLAN: Create new plan
- COMPLETE: Task finished
- STOP: Abort execution

### ParallelExecutor
- ThreadPoolExecutor for concurrent tool calls
- ToolConflictModel: PARALLEL_SAFE vs EXCLUSIVE classification
- ForkedTraceContext for parallel tracing

## Verification System

### VerificationEngine
- Tool-specific Verifiers (BashVerifier, FileEditVerifier)
- ToolContract with pre/postconditions
- Execution validation against contracts

### VerificationTracker
- Collects EvidenceRecords (test_pass, file_edit, command_success)
- Gates completion via `can_complete()`
- Requires proof before allowing complete() tool

## Current Gaps (From DEVIN_ANALYSIS_SUMMARY.md)

### Critical (Do Now)
1. **Tool Verification Framework**: Only TodoVerify has postcondition checking
2. **ToolOutputSummarizer Validation**: Heuristic truncation may lose critical info
3. **Safety Policy Layer**: No allowlists for filesystem/network, no secrets redaction enforcement

### Important (Next Quarter)
4. **SWE-Bench Style Evaluation**: No real-world task benchmarks
5. **Vision Model Integration**: OmniParser V2 spec done, not implemented
6. **Vector Retrieval Over TraceStore**: No semantic search over past experiences

## Strengths

1. **Observable cognition**: Every decision traceable via TraceStore
2. **Explicit constraints**: Phase budgets, tool restrictions, evidence gating
3. **Honest limitations**: No hidden state or capabilities
4. **Comprehensive infrastructure**: Tracing, parallelization, multi-agent already built
5. **Research-backed**: References arxiv papers, production agent analysis

## Weaknesses

1. **No production deployment**: Safety policies not enforced
2. **Limited benchmarking**: SWE-bench integration incomplete
3. **Metacognitive scaffolding incomplete**: V5 partially implemented
4. **No vision integration**: Browser automation limited to DOM
5. **Unknown real-world performance**: No systematic evaluation

## Configuration

### AgentConfig Options
```python
@dataclass
class AgentConfig:
    max_steps: int = 50
    max_tool_calls_per_step: int = 10
    action_gated: bool = False  # Require tool call every turn
    use_memory: bool = False
    use_menu_system: bool = False
    use_guided_templates: bool = False  # arxiv:2509.18076
    enable_persistence: bool = False
    use_swe_workflow: bool = False
```

### LLM Backend Support
- vLLM: `http://localhost:8000/v1`
- Ollama: `http://localhost:11434/v1`
- Venice.ai: `https://api.venice.ai/api/v1`
- OpenAI: `https://api.openai.com/v1`

## Conclusion

CompyMac has substantial infrastructure already built - more than the DEVIN_ANALYSIS_SUMMARY.md suggests. The key gaps are in production hardening (safety, verification) and systematic evaluation (benchmarks). The metacognitive architecture (V5) is a differentiating approach that prioritizes observable reasoning over raw benchmark scores.

The "honest constraints" philosophy is both a strength (transparency, debuggability) and a potential limitation (may not match commercial agents' capabilities). The question is whether this philosophy should be preserved as a differentiator or relaxed to compete on performance.
