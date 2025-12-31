# CompyMac Competitive Gaps - Design Document

This document outlines the implementation plan for closing the gaps between CompyMac and competitors like Devin/Manus.

## Executive Summary

After comprehensive analysis, we identified 5 key gaps that prevent CompyMac from feeling like a production-grade AI agent. This document provides detailed implementation plans for each gap.

**Existing Infrastructure We Can Leverage:**
- `TraceStore` with SQLite, spans, artifacts, and `Checkpoint` class (already has pause/resume primitives!)
- `PolicyEngine` wired into `LocalHarness` with `REQUEST_APPROVAL` action
- Git tools in `tool_menu.py` (branch/commit/PR/CI)
- `Session` class (needs persistence layer)

---

## Gap 1: Session Persistence + Resume

### Problem
Currently, `session.py` explicitly states "There is no persistence between sessions." Users cannot pause a task and resume later.

### Solution
Leverage the existing `Checkpoint` class in `TraceStore` which already has the primitives for pause/resume.

### Files to Modify
- `src/compymac/agent_loop.py` - Add `--resume` support
- `src/compymac/trace_store.py` - Add session state serialization
- `src/compymac/session.py` - Add `to_dict()` / `from_dict()` methods

### Files to Create
- `src/compymac/run_store.py` - High-level run management API

### Key Classes/Functions

```python
# run_store.py
class RunStore:
    """High-level API for managing persistent runs."""
    
    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        
    def create_run(self, task: str, config: AgentConfig) -> str:
        """Create a new run and return run_id."""
        
    def save_checkpoint(self, run_id: str, session: Session, step: int) -> str:
        """Save checkpoint and return checkpoint_id."""
        
    def load_checkpoint(self, run_id: str, checkpoint_id: str = None) -> tuple[Session, int]:
        """Load session from checkpoint. If checkpoint_id is None, load latest."""
        
    def list_runs(self, status: str = None) -> list[RunInfo]:
        """List all runs, optionally filtered by status."""
        
    def get_run(self, run_id: str) -> RunInfo:
        """Get run metadata."""
```

### Integration Points
1. `AgentLoop.__init__` accepts optional `run_id` for resume
2. `AgentLoop.run()` auto-checkpoints every N steps (configurable)
3. On crash/interrupt, latest checkpoint is preserved
4. CLI: `compymac run --resume <run_id>`

### Testing
1. Start run, execute 3 steps, force stop
2. Resume with `--resume`, verify step count continues from 3
3. Verify conversation history is preserved
4. Verify no duplicate tool executions

---

## Gap 2: Run Viewer (CLI/TUI)

### Problem
No way to see what happened during a run: diffs, commands, screenshots, timeline. TraceStore exists but no viewer.

### Solution
Create a CLI viewer that reads from TraceStore and displays timeline, diffs, and artifacts.

### Files to Create
- `src/compymac/cli/__init__.py` - CLI package
- `src/compymac/cli/main.py` - Main CLI entrypoint
- `src/compymac/cli/run_view.py` - Run viewer commands

### Key Classes/Functions

```python
# cli/run_view.py
class RunViewer:
    """View run history and artifacts."""
    
    def __init__(self, trace_store: TraceStore):
        self.trace_store = trace_store
        
    def show_timeline(self, run_id: str, verbose: bool = False) -> str:
        """Show chronological timeline of events."""
        
    def show_diffs(self, run_id: str) -> str:
        """Show file diffs from the run."""
        
    def show_artifacts(self, run_id: str) -> list[str]:
        """List artifacts (screenshots, etc.)."""
        
    def show_tool_calls(self, run_id: str) -> str:
        """Show all tool calls with inputs/outputs."""
```

### CLI Commands
```bash
compymac run list                    # List all runs
compymac run view <run_id>           # Show timeline
compymac run view <run_id> --diffs   # Show file changes
compymac run view <run_id> --tools   # Show tool calls
compymac run artifacts <run_id>      # List artifacts
```

### Integration Points
1. Reads from existing `TraceStore` SQLite database
2. Uses `SessionOverview` for summary view
3. Uses `Span` reconstruction for detailed view

### Testing
1. Run a task that does Write -> bash -> screenshot
2. Verify `run view` shows all events in order
3. Verify `run view --diffs` shows file changes
4. Verify works on partially-completed runs

---

## Gap 3: Verification Before Complete

### Problem
Agent can claim "done" without evidence. Task 8 bug: agent said "no httpx imports" but there are 4+ files with httpx.

### Solution
1. Block `complete()` unless verification command ran
2. Require provenance for negative claims (search results must include command + output)

### Files to Modify
- `src/compymac/local_harness.py` - Add verification tracking and complete gate
- `src/compymac/safety.py` - Add verification policy

### Files to Create
- `src/compymac/verification_tracker.py` - Track verification state

### Key Classes/Functions

```python
# verification_tracker.py
class VerificationTracker:
    """Track whether verification has been performed."""
    
    def __init__(self, verification_patterns: list[str] = None):
        # Default patterns: pytest, npm test, ruff, mypy, cargo test, go test
        self.patterns = verification_patterns or DEFAULT_VERIFICATION_PATTERNS
        self.dirty = False  # True if files modified since last verification
        self.last_verification_step = None
        
    def mark_dirty(self):
        """Called when file-mutating tool runs (Write, Edit, bash with writes)."""
        self.dirty = True
        
    def mark_verified(self, step: int, command: str):
        """Called when verification command runs successfully."""
        self.dirty = False
        self.last_verification_step = step
        
    def can_complete(self) -> tuple[bool, str]:
        """Check if completion is allowed. Returns (allowed, reason)."""
        if self.dirty:
            return False, "Files modified since last verification. Run tests/lint before completing."
        return True, ""
```

### Search Provenance Fix

Modify grep tool to always return structured output:
```python
# In local_harness.py _grep method
def _grep(self, pattern: str, path: str, ...) -> str:
    result = {
        "command": f"rg {pattern} {path} ...",
        "exit_code": exit_code,
        "match_count": len(matches),
        "matches": matches[:50],  # Truncate for context
        "searched_path": path,
    }
    return json.dumps(result)
```

### Integration Points
1. `LocalHarness` tracks dirty state on Write/Edit
2. `LocalHarness._complete()` checks `VerificationTracker.can_complete()`
3. Grep tool returns structured JSON with command and match count

### Testing
1. Edit file, call complete() -> should be blocked
2. Edit file, run pytest, call complete() -> should succeed
3. Search for "import httpx" -> should return match_count > 0
4. Search for nonexistent pattern -> should return match_count = 0 with command shown

---

## Gap 4: Git PR Loop Automation

### Problem
Git tools exist but no robust workflow: branch -> change -> verify -> commit -> PR -> poll CI -> iterate.

### Solution
Create a `GitPRWorkflow` that orchestrates git operations with safety gates.

### Files to Create
- `src/compymac/workflows/git_pr.py` - Git PR workflow

### Key Classes/Functions

```python
# workflows/git_pr.py
class GitPRWorkflow:
    """Orchestrate git operations for PR creation."""
    
    def __init__(self, harness: LocalHarness, approval_callback: Callable = None):
        self.harness = harness
        self.approval_callback = approval_callback  # For HITL approval
        
    def ensure_clean(self) -> bool:
        """Ensure working directory is clean."""
        
    def create_branch(self, branch_name: str) -> bool:
        """Create and checkout new branch."""
        
    def stage_changes(self, files: list[str] = None) -> bool:
        """Stage changes (specific files or all)."""
        
    def run_verification(self) -> tuple[bool, str]:
        """Run verification commands. Returns (passed, output)."""
        
    def commit(self, message: str) -> bool:
        """Commit staged changes."""
        
    def push_and_create_pr(self, title: str, body: str) -> str:
        """Push and create PR. Returns PR URL. Requires approval."""
        
    def poll_ci(self, pr_url: str, timeout: int = 600) -> tuple[bool, str]:
        """Poll CI status. Returns (passed, logs_if_failed)."""
        
    def iterate_on_failure(self, failure_logs: str) -> None:
        """Analyze failure and suggest fixes."""
```

### Integration Points
1. Uses existing git tools from `tool_menu.py`
2. Uses `PolicyEngine` for approval gates on push/PR
3. Emits events to `TraceStore` for viewer

### Testing
1. Create temp git repo, run workflow through commit stage
2. Verify branch created and commit exists
3. Test approval gate blocks push without approval
4. (Optional) Test real PR creation on test repo

---

## Gap 5: Search Reliability Fixes

### Problem
Task 8 bug: agent said "no httpx imports" but `rg "import httpx"` shows 4+ files. Search can fail silently.

### Root Cause Analysis
Need to inspect the actual grep implementation to understand the failure mode.

### Solution
1. Make grep tool return structured JSON with command and match count
2. Add path validation (ensure path exists before searching)
3. Add "negative claim" policy: claims of "none found" must cite tool output

### Files to Modify
- `src/compymac/local_harness.py` - Fix grep tool implementation

### Key Changes

```python
# In local_harness.py
def _grep(self, pattern: str, path: str, ...) -> str:
    # Validate path exists
    if not Path(path).exists():
        return json.dumps({
            "error": f"Path does not exist: {path}",
            "command": f"rg {pattern} {path}",
            "match_count": 0,
        })
    
    # Run ripgrep with consistent flags
    cmd = ["rg", "-n", "--json", pattern, path]
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    # Parse and return structured result
    matches = parse_rg_json(result.stdout)
    return json.dumps({
        "command": " ".join(cmd),
        "exit_code": result.returncode,
        "match_count": len(matches),
        "matches": matches[:50],
        "searched_path": str(Path(path).resolve()),
    })
```

### Testing
1. Search for "import httpx" in compymac -> should find 4+ files
2. Search for nonexistent pattern -> should return match_count=0 with command
3. Search in nonexistent path -> should return error with path shown
4. Regression test: run Task 8 equivalent and verify correct result

---

## Implementation Order

Based on impact and dependencies:

1. **Gap 5: Search Reliability** (1-2 hours)
   - Fixes trust-destroying bug
   - No dependencies
   - Enables reliable testing of other features

2. **Gap 3: Verification Before Complete** (2-3 hours)
   - Builds on fixed search
   - Improves reliability
   - Foundation for PR workflow

3. **Gap 1: Session Persistence** (3-4 hours)
   - Leverages existing Checkpoint class
   - Enables long-running tasks
   - Foundation for viewer

4. **Gap 2: Run Viewer** (2-3 hours)
   - Depends on persistence
   - Reads from TraceStore
   - Enables debugging

5. **Gap 4: Git PR Workflow** (3-4 hours)
   - Depends on verification
   - Uses existing git tools
   - Requires approval gates

---

## Success Criteria

Each gap has specific acceptance tests:

| Gap | Test | Pass Criteria |
|-----|------|---------------|
| 1 | Resume interrupted run | Step count continues, no duplicate tools |
| 2 | View completed run | Timeline shows all events in order |
| 3 | Complete without verification | Blocked with clear message |
| 4 | Create PR workflow | Branch + commit created, approval gate works |
| 5 | Search for httpx | Returns 4+ matches with file paths |

---

## Non-Goals (Future Work)

- Full TUI with curses (CLI viewer is sufficient for now)
- Multi-agent orchestration improvements
- IDE integration (VS Code extension)
- Semantic code indexing (tree-sitter/LSP)
