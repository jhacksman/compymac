# CompyMac: Overview and Real-World Testing Guide

## What is CompyMac?

CompyMac is a proof-of-concept LLM-based agent framework designed to be a baseline reference implementation with observable, debuggable cognition. It provides a Manus/Devin-like experience with an interactive web UI, real-time tool execution, and structured workflows.

### Core Philosophy

CompyMac intentionally preserves fundamental LLM agent constraints to understand them before improving them:

1. **Session-bounded state**: State is discarded when a session ends (unless explicitly persisted)
2. **Fixed context window**: Limited token budget with truncation when exceeded
3. **Tool-mediated actions**: The agent can only affect the world through registered tools
4. **Turn-based processing**: One turn at a time, no background processing
5. **No learning**: The agent does not update weights from interactions

### What CompyMac Is NOT

CompyMac is not a production-ready agent system. It is a research platform for understanding and improving LLM agent architectures. The focus is on cognitive quality and observability over raw benchmark scores.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        Web UI (React)                           │
│   - Agent-driven todos    - Real-time tool execution           │
│   - Status tracking       - WebSocket streaming                 │
└─────────────────────────────────────────────────────────────────┘
                              │ WebSocket
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    API Server (FastAPI)                         │
│   - Session management    - Tool execution routing              │
│   - WebSocket broadcasts  - Trace storage                       │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      AgentLoop                                  │
│   - Turn-based execution  - Tool call handling                  │
│   - State management      - SWE workflow integration            │
└─────────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│   LocalHarness  │ │   LLM Client    │ │   Workflows     │
│   - File ops    │ │   - Venice.ai   │ │   - SWE Loop    │
│   - CLI/Bash    │ │   - OpenAI      │ │   - CI Integ    │
│   - Browser     │ │   - vLLM/Ollama │ │   - Multi-Agent │
│   - Git         │ │                 │ │   - Handoffs    │
└─────────────────┘ └─────────────────┘ └─────────────────┘
```

### Key Components

| Component | Location | Purpose |
|-----------|----------|---------|
| AgentLoop | `src/compymac/agent_loop.py` | Main execution loop with SWE workflow integration |
| LocalHarness | `src/compymac/local_harness.py` | Tool implementations (file, bash, browser, git) |
| LLMClient | `src/compymac/llm.py` | OpenAI-compatible API client |
| API Server | `src/compymac/api/server.py` | FastAPI backend with WebSocket |
| Web UI | `web/` | React frontend with real-time updates |
| Evaluation | `src/compymac/evaluation/` | Task bank and evaluation runner |
| Workflows | `src/compymac/workflows/` | SWE loop, CI integration, multi-agent orchestration |

### Feature Flags

| Flag | Location | Purpose |
|------|----------|---------|
| `use_swe_workflow` | AgentConfig | Enable SWE workflow stages (UNDERSTAND → PLAN → LOCATE → MODIFY → VALIDATE → DEBUG → PR → CI) |
| `action_gated` | AgentConfig | Require explicit tool calls for actions |
| `require_complete_tool` | AgentConfig | Require complete() tool to end session |

## Primary Entry Points

### 1. Interactive Web UI (Recommended for Testing)

```bash
# Terminal 1: Backend
export LLM_API_KEY="your-venice-api-key"
export LLM_BASE_URL="https://api.venice.ai/api/v1"
export LLM_MODEL="qwen3-235b-a22b-instruct-2507"
uv run python -m compymac.api.server

# Terminal 2: Frontend
cd web && npm install && npm run dev
```

Access at http://localhost:3000

### 2. Evaluation Runner (Automated Testing)

```bash
export LLM_API_KEY="your-venice-api-key"
uv run python -m compymac.evaluation.runner --tasks fix_001 fix_002
```

### 3. Programmatic API

```python
from compymac import AgentLoop, create_mock_tools

agent = AgentLoop.create(
    system_prompt="You are a helpful assistant.",
    tools=create_mock_tools(),
)
result = agent.run("Hello, what can you help me with?")
```

## Existing Test Infrastructure

### Unit Tests

Location: `tests/`

```bash
# Run all unit tests
uv run pytest tests/ -v

# Run specific test file
uv run pytest tests/test_agent_loop.py -v
```

Key test files:
- `test_agent_loop.py` - AgentLoop execution tests
- `test_dynamic_orchestration.py` - Gap 6 Phase 3 routing tests
- `test_parallel_workstreams.py` - Gap 6 Phase 2 merge/review tests
- `test_agent_handoffs.py` - Gap 6 Phase 1 artifact handoff tests

### Lint and Type Checks

```bash
# Lint
uv run ruff check src/

# Type check
uv run mypy src/compymac/
```

### Evaluation Task Bank

Location: `src/compymac/evaluation/tasks.py`

16 predefined tasks across 7 categories:
- CODE_FIX (4 tasks): Bug fixes in Python code
- CODE_REFACTOR (2 tasks): Code improvement
- CODE_FEATURE (3 tasks): New feature implementation
- FILE_OPS (2 tasks): File system operations
- RESEARCH (2 tasks): Web search and synthesis
- ANALYSIS (2 tasks): Code/data analysis
- MULTI_STEP (2 tasks): Complex multi-step tasks

---

## Real-World Testing Strategy

### Tier 1: Toolchain Reality Check (Fast, ~5 min)

**Purpose**: Verify tool mediation is functioning end-to-end.

**Test**: Run a scripted scenario through the agent that exercises core tools.

```bash
# Using evaluation runner
export LLM_API_KEY="your-venice-api-key"
uv run python -m compymac.evaluation.runner --tasks file_001 file_002
```

**Expected Output**:
- Files created at `/tmp/eval_file_001/` and `/tmp/eval_file_002/`
- Results logged to `/tmp/compymac_eval/`
- Success rate reported

**Pass Criteria**:
- Both tasks complete without errors
- Files exist with correct content
- Trace store has recorded events

### Tier 2: SWE Workflow Closure (Medium, ~15 min)

**Purpose**: Verify the SWE workflow loop closes correctly with stage transitions.

**Test**: Run a code fix task with `use_swe_workflow` enabled.

```bash
export LLM_API_KEY="your-venice-api-key"
uv run python -m compymac.evaluation.runner --tasks fix_001 fix_003
```

**Expected Output**:
- Agent transitions through workflow stages
- Code is modified
- Tests/validation run after modification
- Task completes with evidence

**Pass Criteria**:
- Stage transitions visible in logs (UNDERSTAND → PLAN → LOCATE → MODIFY → VALIDATE)
- Code fix is correct
- Validation step executed

### Tier 3: Interactive Web UI Smoke Test (Medium, ~10 min)

**Purpose**: Verify the UI is functional with real-time tool execution.

**Test**: Manual test through the web interface.

**Steps**:
1. Start backend and frontend (see entry points above)
2. Open http://localhost:3000
3. Send prompt: "Create a file at /tmp/ui_test/hello.py with print('Hello World'), then run it"
4. Observe:
   - Agent creates todo list
   - Tool calls stream in real-time
   - File is created
   - Python script executes
   - Output displayed

**Pass Criteria**:
- UI loads without errors
- Agent creates plan (todos visible)
- Tool calls execute and stream to UI
- Task completes successfully

### Tier 4: Multi-Agent Orchestration (Component, ~5 min)

**Purpose**: Verify Gap 6 multi-agent components work correctly.

**Test**: Run unit tests for orchestration components.

```bash
uv run pytest tests/test_dynamic_orchestration.py tests/test_parallel_workstreams.py tests/test_agent_handoffs.py -v
```

**Pass Criteria**:
- All 35+ orchestration tests pass
- No import errors
- Routing decisions are deterministic

**Note**: Multi-agent orchestration is implemented as library code. Full integration testing (where tasks are actually routed to specialized agents) is pending integration into the main AgentLoop.

### Tier 5: Full Evaluation Suite (Slow, ~60 min)

**Purpose**: Comprehensive validation across all task categories.

**Test**: Run all 16 evaluation tasks.

```bash
export LLM_API_KEY="your-venice-api-key"
uv run python -m compymac.evaluation.runner
```

**Expected Output**:
- Report at `/tmp/compymac_eval/report.json`
- Per-task results in `/tmp/compymac_eval/{task_id}/`
- Summary printed to console

**Pass Criteria**:
- Success rate > 50% (baseline expectation)
- No crashes or unhandled exceptions
- All categories have at least one success

---

## Evidence Collection

All tests should produce evidence that can be reviewed:

| Evidence Type | Location | Purpose |
|---------------|----------|---------|
| Evaluation reports | `/tmp/compymac_eval/report.json` | Overall success metrics |
| Task results | `/tmp/compymac_eval/{task_id}/result.json` | Per-task details |
| Trace store | `~/.compymac/traces.db` | SQLite database of all events |
| Server logs | Console output | Real-time execution logs |
| Created files | `/tmp/eval_*` | Artifacts from tasks |

## Running the Tests

### Quick Validation (Recommended First Run)

```bash
# 1. Run unit tests
uv run pytest tests/ -v

# 2. Run lint
uv run ruff check src/

# 3. Run Tier 1 toolchain check
export LLM_API_KEY="your-venice-api-key"
uv run python -m compymac.evaluation.runner --tasks file_001

# 4. Check results
cat /tmp/compymac_eval/report.json
```

### Full Validation

```bash
# Run all tiers sequentially
export LLM_API_KEY="your-venice-api-key"

# Tier 1-2: Automated tasks
uv run python -m compymac.evaluation.runner --tasks file_001 file_002 fix_001 fix_003

# Tier 3: Manual UI test (see steps above)

# Tier 4: Component tests
uv run pytest tests/test_dynamic_orchestration.py tests/test_parallel_workstreams.py -v

# Tier 5: Full suite (optional, slow)
uv run python -m compymac.evaluation.runner
```

---

## Current Status Summary

| Gap | Status | Validation |
|-----|--------|------------|
| Gap 1: Auto-Verify | COMPLETED | Unit tests pass |
| Gap 3: Workflow Closure | COMPLETED | Integrated into AgentLoop via `use_swe_workflow` |
| Gap 4: Session Continuity | COMPLETED | UI shows real sessions |
| Gap 6: Multi-Agent | COMPLETED | 3 phases merged, unit tests pass |
| Gap 2: Persistent Workspace | Design complete | Pending NUC hardware |
| Gap 5: Safety Controls | Deprioritized | Not implemented |

## Validation Results (2025-12-27)

### Unit Tests: PASSED

```
======================= 535 passed, 88 warnings in 2.79s =======================
```

All 535 unit tests pass, including:
- 35 dynamic orchestration tests (Gap 6 Phase 3)
- Agent loop tests with SWE workflow integration
- Parallel workstreams and handoff tests

### Tier 1: Toolchain Reality Check - PASSED

**Task: file_001** - Create directory structure

```
Task file_001: SUCCESS in 7 steps (37.3s)
Success Rate: 100.0%
```

Evidence: Files created at `/tmp/eval_file_001/` with correct structure (src/, tests/, README.md)

### Tier 2: Code Fix Task - PASSED

**Task: fix_001** - Fix division by zero bug

```
Task fix_001: SUCCESS in 10 steps (50.5s)
Success Rate: 100.0%
```

Evidence: `/tmp/eval_fix_001/buggy.py` contains fixed code with proper error handling:
```python
def calculate_average(numbers):
    if len(numbers) == 0:
        raise ValueError("Cannot calculate average of empty list")
    return total / len(numbers)
```

## Next Steps

1. Run Tier 3 (Web UI smoke test) for interactive validation
2. Run Tier 5 (full evaluation suite) for comprehensive coverage
3. Address any gaps between expected and actual behavior
4. Consider implementing Gap 5 (Safety Controls) if unattended operation is desired
