# locale2b Integration Implementation Report

**Date:** 2026-01-05  
**Author:** Devin  
**Status:** Research Complete, Ready for Implementation

## Executive Summary

This report details the research findings and implementation plan for integrating locale2b (a self-hosted Firecracker-based workspace service) into CompyMac's CLI tab. The integration will enable CompyMac to execute commands in isolated microVM sandboxes rather than locally, following the architectural patterns established by Manus, Devin, and E2B.

## 1. Industry Research: How Leading Agents Handle Sandbox Execution

### 1.1 Manus Architecture (Primary Reference)

Manus is the most relevant reference as it uses E2B (which locale2b replicates). Key findings from reverse engineering and official documentation:

**Sandbox Infrastructure:**
- Uses E2B Firecracker microVMs (~150ms spin-up time)
- Each user session gets an isolated sandbox with full Linux environment
- Sandboxes persist for hours, supporting long-running tasks
- 27+ tools available inside sandbox (shell, browser, filesystem, Python, Node.js)

**Agent Loop Pattern:**
```
1. Analyze current state and user request
2. Plan/Select action (one tool per iteration)
3. Execute action in sandbox
4. Observe result, append to context
5. Repeat until task complete
```

**Key Design Decisions:**
- One sandbox per session (not per command)
- Sandbox persists across multiple commands
- File-based memory for cross-operation state
- Pause/resume capability for human intervention

**Context Engineering (from Manus blog):**
- KV-cache optimization is critical (10x cost difference for cached vs uncached tokens)
- Keep prompt prefix stable (no timestamps at start)
- Context is append-only (don't modify previous actions/observations)
- Tool masking over removal (don't dynamically add/remove tools mid-session)

### 1.2 Devin Architecture

Devin operates similarly but with additional enterprise features:

**Sandbox Model:**
- Remote browser with streaming visuals
- User can interrupt and take over at any time
- Commands execute in isolated environment
- Session state persists across interactions

**Human-in-the-Loop:**
- Interactive Planning (user can review/modify plans)
- Inline edits during execution
- Interrupt/resume capability
- Visual feedback of agent actions

### 1.3 E2B (Infrastructure Provider)

E2B is the infrastructure Manus uses. Key technical details:

**Firecracker MicroVMs:**
- Sub-200ms startup time
- Full OS isolation (not just containers)
- Snapshot/restore capability
- Memory-efficient (can run thousands concurrently)

**Why Firecracker over Docker:**
- Docker: 10-20 seconds to spawn, container-level isolation
- Firecracker: ~150ms spawn, full VM isolation
- Firecracker supports OS-level operations (install packages, etc.)
- Better security boundary for untrusted code

**API Pattern:**
```
POST /sandboxes - Create sandbox
POST /sandboxes/{id}/exec - Execute command
POST /sandboxes/{id}/files/write - Write file
GET /sandboxes/{id}/files/read - Read file
POST /sandboxes/{id}/pause - Pause (snapshot)
POST /sandboxes/{id}/resume - Resume from snapshot
DELETE /sandboxes/{id} - Destroy
```

## 2. Relevant Academic Research

### 2.1 Fault-Tolerant Sandboxing (arXiv:2512.12806)

**Key Findings:**
- Transactional filesystem snapshots enable safe rollback
- Policy-based interception layer for dangerous commands
- 100% interception rate for high-risk commands
- Only 14.5% performance overhead per transaction
- Commercial CLIs (like Gemini) require interactive auth, breaking headless workflows

**Relevance to locale2b:**
- locale2b should support headless operation (no interactive auth in agent loop)
- Consider adding command interception for dangerous operations
- Snapshot/rollback capability is valuable for error recovery

### 2.2 AgentBay: Hybrid Interaction Sandbox (arXiv:2512.04367)

**Key Findings:**
- Hybrid control interface: AI agent + human can both control sandbox
- Adaptive Streaming Protocol (ASP) for low-latency visual feedback
- 48% success rate improvement with Agent + Human model
- 50% bandwidth reduction vs standard RDP
- Supports Windows, Linux, Android, Web Browsers, Code interpreters

**Relevance to locale2b:**
- Human takeover capability is essential for production
- Visual streaming enables debugging and intervention
- Multiple environment types may be needed long-term

### 2.3 IsolateGPT: Execution Isolation (arXiv:2403.04960, NDSS 2025)

**Key Findings:**
- Isolation between apps and system is critical for security
- Natural language interfaces are imprecise, increasing risk
- Under 30% performance overhead for isolation
- Protects against security, privacy, and safety issues

**Relevance to locale2b:**
- Validates the need for sandbox isolation
- Performance overhead is acceptable for security benefits

## 3. Current CompyMac State

### 3.1 Existing CLI Infrastructure

**Frontend (TerminalPanel.tsx):**
- Displays `terminalOutput` from Zustand store
- Has `onRunCommand(command, execDir)` callback
- Sends WebSocket message `{type: 'run_command', command, exec_dir}`

**Backend (server.py, handle_run_command):**
- Currently executes commands locally via `runtime.harness.execute()`
- Uses `bash` tool with `exec_dir` parameter
- Returns output via WebSocket event `terminal_output`

**Session Management:**
- Sessions created via `POST /sessions`
- Each session has a `SessionRuntime` with harness, agent loop, browser service
- No sandbox lifecycle management currently

### 3.2 What Needs to Change

1. **Add locale2b client** - HTTP client to call locale2b REST API
2. **Sandbox lifecycle management** - Create sandbox per session, reuse for commands
3. **Modify handle_run_command** - Route to locale2b instead of local bash
4. **Add configuration** - Environment variables for locale2b URL and API key
5. **Handle sandbox state** - Track sandbox_id per session

## 4. Implementation Plan

### 4.1 Phase 1: Configuration (Day 1)

Add to `.env.example`:
```bash
# locale2b Sandbox Service Configuration
# --------------------------------------
# locale2b provides isolated Firecracker microVM sandboxes for command execution.
# This is the self-hosted alternative to E2B used by Manus.
# ALL CLI commands execute through locale2b - there is no local fallback.

LOCALE2B_BASE_URL=http://97.115.170.137:8080
LOCALE2B_API_KEY=3216549870BB
LOCALE2B_API_KEY_HEADER=X-API-Key

# Sandbox defaults
LOCALE2B_DEFAULT_MEMORY_MB=512
LOCALE2B_DEFAULT_VCPU_COUNT=1
LOCALE2B_DEFAULT_TEMPLATE=default
```

### 4.2 Phase 2: locale2b Client (Day 1-2)

Create `src/compymac/sandbox/locale2b_client.py`:

```python
"""
locale2b client for Firecracker sandbox management.

This client provides a Python interface to the locale2b REST API,
enabling CompyMac to execute commands in isolated microVM sandboxes.
"""

import os
import httpx
from dataclasses import dataclass
from typing import Optional

@dataclass
class Locale2bConfig:
    """Configuration for locale2b client."""
    base_url: str
    api_key: str
    api_key_header: str = "X-API-Key"
    default_memory_mb: int = 512
    default_vcpu_count: int = 1
    default_template: str = "default"
    
    @classmethod
    def from_env(cls) -> "Locale2bConfig":
        return cls(
            base_url=os.environ.get("LOCALE2B_BASE_URL", "http://localhost:8080"),
            api_key=os.environ.get("LOCALE2B_API_KEY", ""),
            api_key_header=os.environ.get("LOCALE2B_API_KEY_HEADER", "X-API-Key"),
            default_memory_mb=int(os.environ.get("LOCALE2B_DEFAULT_MEMORY_MB", "512")),
            default_vcpu_count=int(os.environ.get("LOCALE2B_DEFAULT_VCPU_COUNT", "1")),
            default_template=os.environ.get("LOCALE2B_DEFAULT_TEMPLATE", "default"),
        )

@dataclass
class SandboxInfo:
    """Information about a sandbox."""
    sandbox_id: str
    status: str
    template: str
    memory_mb: int
    vcpu_count: int
    workspace_id: str
    created_at: str
    ip_address: Optional[str] = None

@dataclass
class CommandResult:
    """Result of command execution."""
    success: bool
    exit_code: int
    stdout: str
    stderr: str
    error: Optional[str] = None

class Locale2bClient:
    """Client for locale2b sandbox service."""
    
    def __init__(self, config: Locale2bConfig):
        self.config = config
        self._client = httpx.AsyncClient(
            base_url=config.base_url,
            headers={config.api_key_header: config.api_key},
            timeout=300.0,  # 5 minute timeout for long commands
        )
    
    async def health_check(self) -> dict:
        """Check service health."""
        response = await self._client.get("/health")
        response.raise_for_status()
        return response.json()
    
    async def create_sandbox(
        self,
        workspace_id: Optional[str] = None,
        memory_mb: Optional[int] = None,
        vcpu_count: Optional[int] = None,
        template: Optional[str] = None,
    ) -> SandboxInfo:
        """Create a new sandbox."""
        response = await self._client.post(
            "/sandboxes",
            json={
                "template": template or self.config.default_template,
                "memory_mb": memory_mb or self.config.default_memory_mb,
                "vcpu_count": vcpu_count or self.config.default_vcpu_count,
                "workspace_id": workspace_id,
            },
        )
        response.raise_for_status()
        data = response.json()
        return SandboxInfo(**data)
    
    async def exec_command(
        self,
        sandbox_id: str,
        command: str,
        timeout_seconds: int = 300,
        working_dir: str = "/workspace",
    ) -> CommandResult:
        """Execute a command in the sandbox."""
        response = await self._client.post(
            f"/sandboxes/{sandbox_id}/exec",
            json={
                "command": command,
                "timeout_seconds": timeout_seconds,
                "working_dir": working_dir,
            },
        )
        response.raise_for_status()
        data = response.json()
        return CommandResult(**data)
    
    async def write_file(
        self,
        sandbox_id: str,
        path: str,
        content: str,
        is_base64: bool = False,
    ) -> dict:
        """Write a file to the sandbox."""
        response = await self._client.post(
            f"/sandboxes/{sandbox_id}/files/write",
            json={"path": path, "content": content, "is_base64": is_base64},
        )
        response.raise_for_status()
        return response.json()
    
    async def read_file(self, sandbox_id: str, path: str) -> dict:
        """Read a file from the sandbox."""
        response = await self._client.get(
            f"/sandboxes/{sandbox_id}/files/read",
            params={"path": path},
        )
        response.raise_for_status()
        return response.json()
    
    async def list_files(self, sandbox_id: str, path: str = "/workspace") -> dict:
        """List files in a directory."""
        response = await self._client.get(
            f"/sandboxes/{sandbox_id}/files/list",
            params={"path": path},
        )
        response.raise_for_status()
        return response.json()
    
    async def pause_sandbox(self, sandbox_id: str) -> dict:
        """Pause a sandbox (snapshot state)."""
        response = await self._client.post(f"/sandboxes/{sandbox_id}/pause")
        response.raise_for_status()
        return response.json()
    
    async def resume_sandbox(self, sandbox_id: str) -> SandboxInfo:
        """Resume a paused sandbox."""
        response = await self._client.post(f"/sandboxes/{sandbox_id}/resume")
        response.raise_for_status()
        data = response.json()
        return SandboxInfo(**data)
    
    async def destroy_sandbox(self, sandbox_id: str) -> dict:
        """Destroy a sandbox."""
        response = await self._client.delete(f"/sandboxes/{sandbox_id}")
        response.raise_for_status()
        return response.json()
    
    async def close(self):
        """Close the HTTP client."""
        await self._client.aclose()
```

### 4.3 Phase 3: Session Integration (Day 2-3)

Modify `SessionRuntime` in `server.py`:

```python
@dataclass
class SessionRuntime:
    """Runtime state for a session including harness and tools."""
    session_id: str
    harness: LocalHarness
    llm_client: LLMClient
    agent_loop: AgentLoop | None = None
    browser_service: BrowserService | None = None
    browser_control: str = "user"
    messages: list[dict[str, Any]] = field(default_factory=list)
    terminal_output: list[dict[str, Any]] = field(default_factory=list)
    browser_state: dict[str, Any] | None = None
    created_at: str = ""
    _last_todo_version: int = 0
    is_paused: bool = False
    pause_reason: str = ""
    audit_events: list[dict[str, Any]] = field(default_factory=list)
    
    # NEW: Sandbox state
    sandbox_id: str | None = None
    sandbox_client: Locale2bClient | None = None
```

Add sandbox initialization:

```python
async def initialize_sandbox(runtime: SessionRuntime) -> str:
    """Initialize locale2b sandbox for a session.
    
    All CLI commands execute through locale2b - there is no local fallback.
    """
    if runtime.sandbox_id is not None:
        return runtime.sandbox_id
    
    config = Locale2bConfig.from_env()
    runtime.sandbox_client = Locale2bClient(config)
    
    # Create sandbox with session_id as workspace_id for persistence
    sandbox = await runtime.sandbox_client.create_sandbox(
        workspace_id=runtime.session_id
    )
    runtime.sandbox_id = sandbox.sandbox_id
    
    logger.info(f"Created sandbox {sandbox.sandbox_id} for session {runtime.session_id}")
    return sandbox.sandbox_id
```

### 4.4 Phase 4: Command Routing (Day 3)

Modify `handle_run_command` to execute all commands through locale2b:

```python
async def handle_run_command(
    websocket: WebSocket, runtime: SessionRuntime, message: dict[str, Any]
) -> None:
    """Handle running a shell command through locale2b sandbox.
    
    All commands execute in the locale2b Firecracker microVM sandbox.
    """
    command = message.get("command", "")
    exec_dir = message.get("exec_dir", "/workspace")

    if not command:
        return

    try:
        # Initialize sandbox if needed
        sandbox_id = await initialize_sandbox(runtime)
        
        # Execute command in locale2b sandbox
        result = await runtime.sandbox_client.exec_command(
            sandbox_id=sandbox_id,
            command=command,
            working_dir=exec_dir,
        )
        
        output = result.stdout
        if result.stderr:
            output += f"\n[stderr]\n{result.stderr}"
        if result.error:
            output += f"\n[error]\n{result.error}"
        exit_code = result.exit_code

        # Add to terminal output
        terminal_entry = {
            "id": str(uuid.uuid4()),
            "command": command,
            "output": output,
            "timestamp": datetime.utcnow().isoformat(),
            "exit_code": exit_code,
        }
        runtime.terminal_output.append(terminal_entry)

        # Send terminal output event
        await send_event(websocket, "terminal_output", {
            "lines": runtime.terminal_output,
            "new_entry": terminal_entry,
        })

    except Exception as e:
        logger.error(f"Command execution error: {e}")
        error_entry = {
            "id": str(uuid.uuid4()),
            "command": command,
            "output": f"Error: {e}",
            "timestamp": datetime.utcnow().isoformat(),
            "exit_code": 1,
        }
        runtime.terminal_output.append(error_entry)
        await send_event(websocket, "terminal_output", {
            "lines": runtime.terminal_output,
            "new_entry": error_entry,
        })
```

### 4.5 Phase 5: Cleanup (Day 3)

Add sandbox cleanup on session end:

```python
async def cleanup_session(session_id: str) -> None:
    """Clean up session resources including sandbox."""
    if session_id not in sessions:
        return
    
    runtime = sessions[session_id]
    
    # Destroy sandbox if exists
    if runtime.sandbox_client and runtime.sandbox_id:
        try:
            await runtime.sandbox_client.destroy_sandbox(runtime.sandbox_id)
            logger.info(f"Destroyed sandbox {runtime.sandbox_id}")
        except Exception as e:
            logger.error(f"Failed to destroy sandbox: {e}")
        finally:
            await runtime.sandbox_client.close()
    
    # Clean up browser
    if runtime.browser_service:
        await runtime.browser_service.close()
    
    del sessions[session_id]
```

## 5. Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        CompyMac Web UI                          │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐             │
│  │ Conversation│  │   Browser   │  │     CLI     │             │
│  │    Panel    │  │    Panel    │  │    Panel    │             │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘             │
└─────────┼────────────────┼────────────────┼─────────────────────┘
          │                │                │
          │    WebSocket   │                │
          ▼                ▼                ▼
┌─────────────────────────────────────────────────────────────────┐
│                    CompyMac Backend (FastAPI)                   │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    SessionRuntime                        │   │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────────────────┐   │   │
│  │  │  Agent   │  │ Browser  │  │   Locale2bClient     │   │   │
│  │  │   Loop   │  │ Service  │  │  (sandbox_id: xxx)   │   │   │
│  │  └──────────┘  └──────────┘  └──────────┬───────────┘   │   │
│  └──────────────────────────────────────────┼───────────────┘   │
└─────────────────────────────────────────────┼───────────────────┘
                                              │
                                              │ HTTP REST API
                                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    locale2b Service (97.115.170.137:8080)       │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    Sandbox Manager                       │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │   │
│  │  │  Sandbox A   │  │  Sandbox B   │  │  Sandbox C   │   │   │
│  │  │ (session 1)  │  │ (session 2)  │  │ (session 3)  │   │   │
│  │  │  Firecracker │  │  Firecracker │  │  Firecracker │   │   │
│  │  │   microVM    │  │   microVM    │  │   microVM    │   │   │
│  │  └──────────────┘  └──────────────┘  └──────────────┘   │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

## 6. Key Design Decisions

### 6.1 One Sandbox Per Session

Following Manus's pattern, each CompyMac session gets one sandbox that persists across all commands. This enables:
- State persistence (files created in one command available in next)
- Efficient resource usage (no sandbox spin-up per command)
- Consistent environment for multi-step tasks

### 6.2 locale2b is Required

All CLI commands execute through locale2b - there is no local fallback. This ensures:
- Consistent execution environment across all sessions
- Proper isolation and security for all commands
- Same behavior in development and production

If locale2b is unavailable, commands will fail with an error rather than silently falling back to local execution.

### 6.3 Workspace ID = Session ID

Using the CompyMac session ID as the locale2b workspace ID enables:
- Future pause/resume capability (resume sandbox by workspace_id)
- Correlation between CompyMac sessions and sandboxes
- Potential for session persistence across restarts

### 6.4 Default Working Directory: /workspace

Changed from `/home/ubuntu` to `/workspace` to match:
- locale2b's allowed path prefixes (`/workspace`, `/tmp`)
- Manus's convention of using `/workspace` as the agent's working directory
- E2B's standard workspace location

## 7. Security Considerations

### 7.1 API Key Protection

- API key stored server-side only (not in frontend)
- Never exposed via `NEXT_PUBLIC_*` environment variables
- Transmitted via HTTP header, not URL parameter

### 7.2 Path Validation

locale2b already validates paths against `ALLOWED_PATH_PREFIXES`. CompyMac should:
- Default to `/workspace` for all operations
- Not allow user to specify arbitrary paths outside allowed prefixes

### 7.3 Command Interception

Consider adding (future enhancement):
- Dangerous command detection (rm -rf /, etc.)
- User confirmation for destructive operations
- Audit logging of all commands

## 8. Future Enhancements

### 8.1 Visual Terminal Streaming

Following the browser HITL research (PR #231, #232), add:
- Real-time terminal output streaming
- User can see commands as they execute
- Human takeover capability for interactive commands

### 8.2 Pause/Resume

Leverage locale2b's pause/resume for:
- Session persistence across CompyMac restarts
- Cost optimization (pause idle sandboxes)
- Human intervention points

### 8.3 File Browser Integration

Add UI for:
- Browsing sandbox filesystem
- Uploading/downloading files
- Editing files in sandbox

### 8.4 Multi-Environment Support

Following AgentBay's pattern, consider:
- Windows sandboxes for Windows-specific tasks
- Android emulators for mobile testing
- Browser-only sandboxes for web automation

## 9. Testing Plan

### 9.1 Unit Tests

- `Locale2bClient` methods with mocked HTTP responses
- Configuration loading from environment
- Error handling for API failures

### 9.2 Integration Tests

- Create sandbox, execute command, destroy sandbox
- File operations (write, read, list)
- Pause/resume cycle
- Session cleanup

### 9.3 End-to-End Tests

- User types command in CLI tab
- Command executes in sandbox
- Output appears in terminal
- Files persist across commands

## 10. Timeline

| Phase | Task | Duration |
|-------|------|----------|
| 1 | Configuration (.env.example) | 0.5 day |
| 2 | Locale2bClient implementation | 1 day |
| 3 | Session integration | 1 day |
| 4 | Command routing | 0.5 day |
| 5 | Cleanup and testing | 1 day |
| **Total** | | **4 days** |

## 11. References

### Industry Sources
- [How Manus Uses E2B](https://e2b.dev/blog/how-manus-uses-e2b-to-provide-agents-with-virtual-computers)
- [Manus Context Engineering](https://manus.im/blog/Context-Engineering-for-AI-Agents-Lessons-from-Building-Manus)
- [Manus Technical Investigation](https://gist.github.com/renschni/4fbc70b31bad8dd57f3370239dccd58f)
- [E2B Documentation](https://e2b.dev/docs)

### Academic Papers
- arXiv:2512.12806 - Fault-Tolerant Sandboxing for AI Coding Agents
- arXiv:2512.04367 - AgentBay: Hybrid Interaction Sandbox for Human-AI Intervention
- arXiv:2403.04960 - IsolateGPT: Execution Isolation Architecture (NDSS 2025)

### locale2b Documentation
- [locale2b README](https://github.com/jhacksman/locale2b)
- Server: 97.115.170.137:8080
- API Key: 3216549870BB (X-API-Key header)
