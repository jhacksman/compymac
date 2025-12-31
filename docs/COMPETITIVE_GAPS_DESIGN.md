# CompyMac Competitive Gaps - Design Document

This document outlines the implementation plan for closing the gaps between CompyMac and competitors like Devin/Manus.

## Executive Summary

After comprehensive analysis comparing CompyMac to Manus, Devin, Claude Code, Cursor, Windsurf, and OpenAI Operator, we identified gaps in two categories:

**Phase 1 Gaps (COMPLETED - PR #151):**
- Gap 1: Session Persistence + Resume
- Gap 2: Run Viewer (CLI)
- Gap 3: Verification Before Complete
- Gap 4: Git PR Loop Automation
- Gap 5: Search Reliability Fixes

**Phase 2 Gaps (NEW - To Be Implemented):**
- Gap A: Interactive Web UI (see GAP1_INTERACTIVE_UI_DESIGN.md)
- Gap B: Per-Run Sandboxing/Isolation
- Gap C: MCP/Plugin Protocol for Integrations
- Gap D: Multi-Model Routing
- Gap E: First-Class Memories/Rules System
- Gap F: Tiered Permission Model
- Gap G: Secrets/Cookies Management

**Existing Infrastructure We Can Leverage:**
- `TraceStore` with SQLite, spans, artifacts, and `Checkpoint` class (already has pause/resume primitives!)
- `PolicyEngine` wired into `LocalHarness` with `REQUEST_APPROVAL` action
- Git tools in `tool_menu.py` (branch/commit/PR/CI)
- `Session` class (now with persistence layer)
- `BrowserService` with element ID injection and screenshot capture
- `MemoryManager` with vector store and hybrid retrieval

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

---

# Phase 2 Gaps (NEW)

The following gaps were identified after comprehensive analysis of Manus, Devin, Claude Code, Cursor, Windsurf, and OpenAI Operator.

---

## Gap A: Interactive Web UI

**See detailed design document:** `GAP1_INTERACTIVE_UI_DESIGN.md`

### Problem
CompyMac has only a CLI interface. Users cannot easily review changes as diffs, approve actions inline, or take over mid-task. Competitors like Devin have full web IDEs with VSCode, browser, terminal, and interactive takeover.

### Solution
Build a web-based control surface with:
- Three-column layout: History sidebar | Conversation | Canvas (tabbed)
- Real-time streaming via WebSockets
- Interactive browser/terminal takeover (screenshot + action loop)
- Multi-user auth via OIDC (Google, Apple, Authentik)

### Tech Stack
- Frontend: Next.js 14+, React, Tailwind, shadcn/ui, react-resizable-panels
- Backend: FastAPI WebSocket server
- Auth: Auth.js + Authentik (OIDC)
- Database: PostgreSQL

### Impact: HIGH | Feasibility: MEDIUM | Effort: 6-8 weeks

---

## Gap B: Per-Run Sandboxing/Isolation

### Problem
CompyMac runs directly on the host via `LocalHarness`. This risks host damage, dependency conflicts, and inconsistent results. Manus/Devin run in cloud VMs/containers that can be reset, cloned, and paused.

### Current State
- `WorkspaceIsolation` in `parallel.py` uses git worktrees (not true sandboxing)
- `swe_bench.py` creates isolated venvs but not full containers

### Solution
Add Docker/Podman-based execution environment:

```python
# sandbox.py
class SandboxedHarness(Harness):
    """Execute agent actions in isolated container."""
    
    def __init__(self, image: str = "compymac-sandbox:latest"):
        self.container = None
        self.image = image
        
    def start(self, workspace_path: Path) -> str:
        """Start container with workspace mounted."""
        
    def execute(self, tool_call: ToolCall) -> ToolResult:
        """Execute tool call inside container."""
        
    def snapshot(self) -> str:
        """Create container snapshot for resume."""
        
    def restore(self, snapshot_id: str) -> None:
        """Restore container from snapshot."""
        
    def cleanup(self) -> None:
        """Stop and remove container."""
```

### Benefits
- Safe execution (can't damage host)
- Reproducible environments
- Snapshot/restore for pause/resume
- Background execution (container keeps running)

### Impact: HIGH | Feasibility: HIGH | Effort: 2-3 weeks

---

## Gap C: MCP/Plugin Protocol for Integrations

### Problem
CompyMac has `ToolRegistry` for registering tools, but no plugin protocol for external integrations. Every integration must be built into core. Devin has MCP marketplace (Slack, Jira, Linear, GitHub deep hooks). Windsurf has MCP support.

### Solution
Implement Model Context Protocol (MCP) support:

```python
# mcp/client.py
class MCPClient:
    """Client for connecting to MCP servers."""
    
    def __init__(self, server_url: str):
        self.server_url = server_url
        
    def list_tools(self) -> list[Tool]:
        """List available tools from MCP server."""
        
    def call_tool(self, name: str, arguments: dict) -> ToolResult:
        """Call a tool on the MCP server."""
        
    def list_resources(self) -> list[Resource]:
        """List available resources."""
        
    def read_resource(self, uri: str) -> str:
        """Read a resource from the server."""

# mcp/registry.py
class MCPRegistry:
    """Registry of MCP server connections."""
    
    def register_server(self, name: str, url: str) -> None:
        """Register an MCP server."""
        
    def get_all_tools(self) -> list[Tool]:
        """Get tools from all registered servers."""
```

### Reference Integrations
1. GitHub (issues, PR comments, CI status)
2. Slack (notifications, thread updates)
3. Linear (ticket creation, status updates)

### Impact: HIGH | Feasibility: HIGH | Effort: 2-3 weeks

---

## Gap D: Multi-Model Routing

### Problem
CompyMac uses a single `LLMClient` with one configured model. Manus uses multi-model dynamic invocation (Claude for reasoning, GPT-4 for coding, Gemini for knowledge).

### Solution
Add a router policy that selects models per task type:

```python
# llm_router.py
class ModelRouter:
    """Route requests to optimal models based on task type."""
    
    def __init__(self, config: RouterConfig):
        self.clients = {}  # model_name -> LLMClient
        self.policies = config.policies
        
    def route(self, task_type: str, messages: list[dict]) -> LLMClient:
        """Select optimal model for task type."""
        # task_type: "reasoning", "coding", "search_summary", "planning"
        
    def chat(self, task_type: str, messages: list[dict], **kwargs) -> ChatResponse:
        """Route and execute chat request."""
        client = self.route(task_type, messages)
        return client.chat(messages, **kwargs)

# Example config
router_config = RouterConfig(
    models={
        "reasoning": LLMConfig(model="claude-3-5-sonnet", ...),
        "coding": LLMConfig(model="qwen3-235b", ...),
        "search_summary": LLMConfig(model="qwen3-next-80b", ...),  # Cheaper
    },
    default="coding",
)
```

### Benefits
- Cost optimization (cheap model for simple tasks)
- Quality optimization (best model for complex reasoning)
- Fallback handling (try another model on failure)

### Impact: MEDIUM | Feasibility: HIGH | Effort: 1-2 weeks

---

## Gap E: First-Class Memories/Rules System

### Problem
CompyMac has `MemoryManager` and `knowledge_store.py`, but no user-editable rules/preferences that are actively enforced. Windsurf has Memories (remembers codebase/workflow) and Rules (project-specific patterns). Devin has Knowledge onboarding and AGENTS.md.

### Solution
Add a Rules system that's explicitly referenced during planning and enforced during action:

```python
# rules.py
@dataclass
class Rule:
    """A user-defined rule for agent behavior."""
    id: str
    name: str
    description: str
    pattern: str  # When to apply (regex on task/tool)
    action: str  # What to do: "require", "prefer", "avoid", "block"
    content: str  # The actual rule content
    enabled: bool = True

class RulesEngine:
    """Manage and enforce user-defined rules."""
    
    def __init__(self, rules_path: Path):
        self.rules = self._load_rules(rules_path)
        
    def get_applicable_rules(self, context: str) -> list[Rule]:
        """Get rules that apply to current context."""
        
    def format_for_prompt(self, rules: list[Rule]) -> str:
        """Format rules for inclusion in system prompt."""
        
    def check_action(self, tool_call: ToolCall) -> tuple[bool, str]:
        """Check if action violates any rules."""
```

### Example Rules
```yaml
# .compymac/rules.yaml
rules:
  - name: "Use TypeScript"
    pattern: ".*\\.js$"
    action: "prefer"
    content: "Prefer TypeScript (.ts) over JavaScript (.js) for new files"
    
  - name: "No console.log"
    pattern: "console\\.log"
    action: "avoid"
    content: "Use proper logging instead of console.log"
    
  - name: "Run tests before commit"
    pattern: "git commit"
    action: "require"
    content: "Always run npm test before committing"
```

### Impact: MEDIUM | Feasibility: MEDIUM | Effort: 2-3 weeks

---

## Gap F: Tiered Permission Model

### Problem
CompyMac has `PolicyEngine` with BLOCK/WARN/ADVISORY levels, but no tiered permission escalation. Claude Code has incremental trust (auto-approve reads, ask for writes, stronger gates for network). Cursor has YOLO mode vs approve-every-change.

### Solution
Extend PolicyEngine with tiered permissions:

```python
# safety.py additions
class PermissionTier(Enum):
    AUTO_APPROVE = "auto"      # No confirmation needed
    NOTIFY = "notify"          # Show notification, continue
    CONFIRM = "confirm"        # Require explicit approval
    ELEVATED = "elevated"      # Require elevated approval (e.g., 2FA)

class TieredPolicyEngine(PolicyEngine):
    """Policy engine with tiered permission levels."""
    
    def __init__(self, trust_level: str = "standard"):
        # trust_level: "paranoid", "standard", "yolo"
        self.trust_level = trust_level
        self.tier_map = self._build_tier_map()
        
    def _build_tier_map(self) -> dict[str, PermissionTier]:
        """Map tool patterns to permission tiers based on trust level."""
        if self.trust_level == "yolo":
            return {".*": PermissionTier.AUTO_APPROVE}
        elif self.trust_level == "paranoid":
            return {
                "Read|grep|glob": PermissionTier.AUTO_APPROVE,
                "Write|Edit": PermissionTier.CONFIRM,
                "bash": PermissionTier.ELEVATED,
                "browser_.*": PermissionTier.ELEVATED,
            }
        else:  # standard
            return {
                "Read|grep|glob": PermissionTier.AUTO_APPROVE,
                "Write|Edit": PermissionTier.NOTIFY,
                "bash": PermissionTier.CONFIRM,
                "browser_.*": PermissionTier.CONFIRM,
            }
```

### Impact: MEDIUM | Feasibility: HIGH | Effort: 1-2 weeks

---

## Gap G: Secrets/Cookies Management

### Problem
CompyMac has `SecretsRedactor` (redacts secrets from output), but no secure storage/injection. Devin has secrets management and site cookies for authenticated browsing.

### Solution
Add secure secrets storage and injection:

```python
# secrets_manager.py
class SecretsManager:
    """Secure storage and injection of secrets."""
    
    def __init__(self, keyring_backend: str = "system"):
        self.backend = self._init_backend(keyring_backend)
        
    def store_secret(self, name: str, value: str, scope: str = "global") -> None:
        """Store a secret securely."""
        # scope: "global", "project", "session"
        
    def get_secret(self, name: str, scope: str = "global") -> str | None:
        """Retrieve a secret."""
        
    def inject_env(self, env: dict, patterns: list[str]) -> dict:
        """Inject secrets into environment variables."""
        
    def store_cookie(self, domain: str, cookie: dict) -> None:
        """Store browser cookie for domain."""
        
    def get_cookies(self, domain: str) -> list[dict]:
        """Get cookies for domain."""

# Integration with BrowserService
class AuthenticatedBrowserService(BrowserService):
    """Browser service with cookie injection."""
    
    def __init__(self, secrets_manager: SecretsManager, **kwargs):
        super().__init__(**kwargs)
        self.secrets_manager = secrets_manager
        
    async def navigate(self, url: str, **kwargs) -> BrowserAction:
        """Navigate with automatic cookie injection."""
        domain = urlparse(url).netloc
        cookies = self.secrets_manager.get_cookies(domain)
        if cookies:
            await self._inject_cookies(cookies)
        return await super().navigate(url, **kwargs)
```

### Impact: MEDIUM | Feasibility: MEDIUM | Effort: 2-3 weeks

---

## Phase 2 Implementation Order

Based on impact, dependencies, and user value:

1. **Gap A: Interactive Web UI** (6-8 weeks)
   - Highest user impact
   - Foundation for other features
   - See GAP1_INTERACTIVE_UI_DESIGN.md for details

2. **Gap B: Per-Run Sandboxing** (2-3 weeks)
   - Safety and reliability
   - Enables background execution
   - Required for hosted deployment

3. **Gap C: MCP/Plugin Protocol** (2-3 weeks)
   - Ecosystem growth
   - Reduces core maintenance burden
   - Enables community contributions

4. **Gap D: Multi-Model Routing** (1-2 weeks)
   - Cost optimization
   - Quality improvement
   - Quick win

5. **Gap F: Tiered Permissions** (1-2 weeks)
   - Extends existing PolicyEngine
   - Better UX for different trust levels
   - Quick win

6. **Gap E: Memories/Rules System** (2-3 weeks)
   - User customization
   - Project-specific behavior
   - Builds on existing memory system

7. **Gap G: Secrets/Cookies Management** (2-3 weeks)
   - Authenticated workflows
   - Enterprise requirement
   - Security-sensitive

---

## Phase 2 Success Criteria

| Gap | Test | Pass Criteria |
|-----|------|---------------|
| A | Web UI loads and connects | Can send message, see response stream |
| B | Run in sandbox | Container created, tool executes, cleanup works |
| C | MCP integration | Can list tools from external MCP server |
| D | Multi-model routing | Different models used for different task types |
| E | Rules enforcement | Rule blocks disallowed action |
| F | Tiered permissions | Read auto-approved, write requires confirm |
| G | Secrets injection | Secret injected into env without exposure |
