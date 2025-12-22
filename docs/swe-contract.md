# CompyMac SWE Contract

This document defines the canonical SWE workflows that CompyMac must execute reliably. These are the acceptance tests for the entire system.

## Canonical Workflow 1: Fix Failing Test

**Input:**
- Repository URL or local path
- Failing test identifier (file path, test name, or CI job URL)
- Optional: branch to work on

**Expected Behavior:**
1. Clone/checkout repository
2. Identify the failing test and understand the failure
3. Locate relevant source code
4. Implement a fix
5. Run the test locally to verify fix
6. Run full test suite to check for regressions
7. Create a commit with descriptive message
8. Create a PR with:
   - Clear title describing the fix
   - Description explaining what was wrong and how it was fixed
   - Link to the original failing test/issue
9. Wait for CI to complete
10. Report success or iterate on CI failures

**Success Criteria:**
- [ ] Test that was failing now passes
- [ ] No new test failures introduced
- [ ] PR is created and CI passes
- [ ] Total execution is captured in database with:
  - Every LLM request/response (full tokens)
  - Every tool call with arguments and results
  - Every file read/write operation
  - Every shell command and output
  - Timestamps for all operations
- [ ] Execution can be paused and resumed from any checkpoint
- [ ] Overview timeline can be generated from captured data

**Measurable Outputs:**
```
{
  "workflow": "fix_failing_test",
  "status": "success" | "failure",
  "pr_url": "https://github.com/...",
  "ci_status": "pass" | "fail",
  "test_results": {
    "target_test": "pass" | "fail",
    "regression_tests": "pass" | "fail",
    "new_failures": []
  },
  "capture": {
    "session_id": "uuid",
    "total_llm_calls": int,
    "total_tool_calls": int,
    "total_tokens": int,
    "checkpoints": int,
    "duration_seconds": float
  }
}
```

---

## Canonical Workflow 2: Implement Small Feature

**Input:**
- Repository URL or local path
- Feature specification (natural language description)
- Optional: target files or modules
- Optional: example code or tests to follow

**Expected Behavior:**
1. Clone/checkout repository
2. Understand the codebase structure and conventions
3. Plan the implementation approach
4. Implement the feature following existing patterns
5. Write tests for the new feature
6. Run tests to verify implementation
7. Run linter/formatter if configured
8. Create a commit with descriptive message
9. Create a PR with:
   - Clear title describing the feature
   - Description explaining the implementation
   - Any relevant context or decisions made
10. Wait for CI to complete
11. Report success or iterate on CI failures

**Success Criteria:**
- [ ] Feature works as specified
- [ ] Tests are written and pass
- [ ] No existing tests broken
- [ ] Code follows project conventions
- [ ] PR is created and CI passes
- [ ] Total execution is captured (same as Workflow 1)

**Measurable Outputs:**
```
{
  "workflow": "implement_feature",
  "status": "success" | "failure",
  "pr_url": "https://github.com/...",
  "ci_status": "pass" | "fail",
  "implementation": {
    "files_created": [],
    "files_modified": [],
    "tests_added": int,
    "lines_added": int,
    "lines_removed": int
  },
  "capture": {
    "session_id": "uuid",
    "total_llm_calls": int,
    "total_tool_calls": int,
    "total_tokens": int,
    "checkpoints": int,
    "duration_seconds": float
  }
}
```

---

## Execution Capture Requirements

Every workflow execution MUST capture:

### 1. LLM Interactions (Full Fidelity)
```python
{
  "type": "llm_call",
  "timestamp": "ISO8601",
  "request": {
    "model": str,
    "messages": [...],  # Full message history
    "tools": [...],     # Tool schemas provided
    "temperature": float,
    "max_tokens": int
  },
  "response": {
    "content": str,           # Full response text
    "tool_calls": [...],      # Any tool calls made
    "usage": {
      "prompt_tokens": int,
      "completion_tokens": int,
      "total_tokens": int
    },
    "finish_reason": str
  },
  "latency_ms": int
}
```

### 2. Tool Calls
```python
{
  "type": "tool_call",
  "timestamp": "ISO8601",
  "tool_name": str,
  "arguments": dict,
  "result": {
    "success": bool,
    "content": str,       # Full output (before truncation)
    "truncated": bool,
    "error": str | None
  },
  "latency_ms": int
}
```

### 3. State Transitions
```python
{
  "type": "state_transition",
  "timestamp": "ISO8601",
  "from_state": str,
  "to_state": str,
  "trigger": str,
  "context": dict
}
```

### 4. Checkpoints
```python
{
  "type": "checkpoint",
  "timestamp": "ISO8601",
  "checkpoint_id": "uuid",
  "state": {
    "message_history": [...],
    "current_step": str,
    "workspace": dict,
    "tool_state": dict
  },
  "resumable": bool
}
```

---

## Query Interface Requirements

The capture system MUST support:

### Timeline Queries
```python
# Get all events in a session
get_session_timeline(session_id) -> List[Event]

# Get events in time range
get_events_between(session_id, start_time, end_time) -> List[Event]

# Get events by type
get_events_by_type(session_id, event_type) -> List[Event]
```

### Overview Generation
```python
# Get high-level summary
get_session_overview(session_id) -> SessionOverview

# Overview includes:
# - Total duration
# - LLM calls count and token usage
# - Tool calls count by tool
# - Checkpoints available
# - Current status
# - Key milestones (PR created, tests run, etc.)
```

### Checkpoint Operations
```python
# List all checkpoints
list_checkpoints(session_id) -> List[Checkpoint]

# Get checkpoint details
get_checkpoint(checkpoint_id) -> Checkpoint

# Resume from checkpoint
resume_from_checkpoint(checkpoint_id) -> Session

# Fork from checkpoint (create new branch of execution)
fork_from_checkpoint(checkpoint_id) -> Session
```

---

## Acceptance Test Script

```python
"""
Run this script to verify CompyMac meets the contract.
"""

def test_workflow_1_fix_failing_test():
    """Test: Fix a failing test in a sample repo."""
    # Setup: Create repo with intentionally failing test
    repo = create_test_repo_with_failing_test()
    
    # Execute workflow
    session = compymac.run_workflow(
        workflow="fix_failing_test",
        repo=repo,
        test="test_example.py::test_should_pass"
    )
    
    # Verify success criteria
    assert session.status == "success"
    assert session.pr_url is not None
    assert session.ci_status == "pass"
    assert session.test_results.target_test == "pass"
    assert len(session.test_results.new_failures) == 0
    
    # Verify capture
    assert session.capture.total_llm_calls > 0
    assert session.capture.total_tool_calls > 0
    assert session.capture.checkpoints > 0
    
    # Verify queryability
    timeline = get_session_timeline(session.session_id)
    assert len(timeline) > 0
    
    overview = get_session_overview(session.session_id)
    assert overview.total_tokens > 0
    
    # Verify checkpoint/resume
    checkpoints = list_checkpoints(session.session_id)
    assert len(checkpoints) > 0
    
    # Can resume from any checkpoint
    for cp in checkpoints:
        resumed = resume_from_checkpoint(cp.checkpoint_id)
        assert resumed is not None


def test_workflow_2_implement_feature():
    """Test: Implement a small feature in a sample repo."""
    # Setup: Create repo needing a feature
    repo = create_test_repo_for_feature()
    
    # Execute workflow
    session = compymac.run_workflow(
        workflow="implement_feature",
        repo=repo,
        spec="Add a function that calculates fibonacci numbers"
    )
    
    # Verify success criteria
    assert session.status == "success"
    assert session.pr_url is not None
    assert session.ci_status == "pass"
    assert session.implementation.tests_added > 0
    
    # Verify capture (same as workflow 1)
    assert session.capture.total_llm_calls > 0
    assert session.capture.checkpoints > 0
```

---

## Implementation Checklist

### Phase 0 Complete When:
- [x] This contract document exists
- [ ] Sample test repos created for acceptance tests
- [ ] Acceptance test script is runnable (even if failing)

### Phase 1 Complete When:
- [ ] Full LLM request/response capture implemented
- [ ] All tool calls captured with full output
- [ ] State transitions captured
- [ ] Checkpoints created automatically
- [ ] SQLite database backend working
- [ ] Timeline query interface implemented
- [ ] Overview generation implemented
- [ ] Checkpoint list/get/resume implemented
- [ ] Acceptance tests pass for capture requirements
