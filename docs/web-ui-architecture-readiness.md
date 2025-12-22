# CompyMac Web UI Architecture Readiness

**Date**: December 22, 2025
**Question**: Is the current architecture ready for a web-based interface like Devin.ai or claude.ai/code?
**Answer**: **YES** - Core architecture is well-designed for web UI. Minimal additions needed.

---

## TL;DR: You're on the Right Path ✅

The current architecture is **excellent** for building a web UI. You won't need significant backtracking. Here's why:

### What You Already Have (Perfect for Web UI)

1. ✅ **TraceStore** - Complete execution capture
   - Shows every agent action in real-time
   - Supports replay and time-travel debugging
   - Perfect for rich UI visualization

2. ✅ **Message-based communication** - Structured I/O
   - Already uses Message objects (role, content)
   - Easy to stream over WebSocket/SSE
   - No tight coupling to CLI

3. ✅ **Harness abstraction** - Clean separation
   - Agent logic separate from execution
   - Easy to swap LocalHarness for WebHarness
   - Tools are already modular

4. ✅ **Session management** - State tracking
   - Session object tracks state
   - Context management for memory
   - Ready for persistence

5. ✅ **Multi-agent system** - Role visibility
   - Manager/Planner/Executor/Reflector
   - Can show what each agent is doing
   - Perfect for UI breakdown

### What You Need to Add (Straightforward)

1. ⚠️ **WebSocket/SSE server** - Real-time streaming
   - Wrap AgentLoop with FastAPI/WebSocket
   - Stream messages token-by-token
   - **Effort**: 1-2 weeks

2. ⚠️ **Multi-user sessions** - Isolation & auth
   - Session ID per user
   - Workspace isolation (already have workspace concept)
   - Authentication layer
   - **Effort**: 2-3 weeks

3. ⚠️ **Persistence layer** - Long-running sessions
   - Save/restore session state
   - TraceStore already provides this foundation
   - **Effort**: 1 week

4. ⚠️ **Pause/Resume/Interrupt** - User control
   - Add cancellation tokens to agent loop
   - Checkpoint mechanism (partially exists)
   - **Effort**: 1-2 weeks

---

## Comparison: Devin.ai vs Claude Code vs CompyMac

| Feature | Devin.ai | Claude Code | CompyMac (Now) | CompyMac (Web UI) |
|---------|----------|-------------|----------------|-------------------|
| **Interface** | Web-based | VSCode extension | CLI | Web + CLI |
| **Execution Capture** | Yes (proprietary) | Limited | ✅ TraceStore | ✅ Same |
| **Multi-agent** | Unknown | No | ✅ Manager/Planner/Executor | ✅ Same |
| **Browser Automation** | Yes | No | ✅ Playwright-based | ✅ Same |
| **Parallel Execution** | Yes | No | ✅ Rollouts + forked traces | ✅ Same |
| **Session Persistence** | Yes | VSCode workspace | ⚠️ Partial (TraceStore only) | ✅ Full persistence |
| **Real-time Streaming** | Yes | Yes | ❌ CLI only | ✅ WebSocket/SSE |
| **User Auth** | Yes | N/A (local) | ❌ None | ✅ Auth layer |
| **Workspace Isolation** | Cloud sandboxes | Local filesystem | ⚠️ Single user | ✅ Multi-tenant |

**Verdict**: CompyMac's core is **already more advanced** than Claude Code (multi-agent, parallelization, TraceStore). Just needs web layer on top.

---

## Architecture for Web UI

### Current Architecture (CLI-focused)

```
┌─────────────┐
│     CLI     │ (user types commands)
└─────┬───────┘
      │
      v
┌─────────────────┐
│   AgentLoop     │ (processes one turn at a time)
└─────┬───────────┘
      │
      v
┌─────────────────┐
│  LocalHarness   │ (executes tools on local filesystem)
└─────┬───────────┘
      │
      v
┌─────────────────┐
│   TraceStore    │ (logs everything to SQLite)
└─────────────────┘
```

**Strengths**:
- Clean separation of concerns
- Message-based communication (not tightly coupled to CLI)
- Complete execution capture

**Limitations**:
- Synchronous (blocks until turn completes)
- Single user, single session
- No real-time streaming

### Proposed Architecture (Web-friendly)

```
┌──────────────────────────────────────────────────────┐
│                    Frontend (React/Next.js)           │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐     │
│  │ Chat Panel │  │ File Tree  │  │ Terminal   │     │
│  └────────────┘  └────────────┘  └────────────┘     │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐     │
│  │ Agent View │  │ Browser    │  │ Trace View │     │
│  └────────────┘  └────────────┘  └────────────┘     │
└──────────────┬───────────────────────────────────────┘
               │ WebSocket / SSE
               v
┌──────────────────────────────────────────────────────┐
│              Backend (FastAPI)                        │
│                                                       │
│  ┌─────────────────────────────────────────┐         │
│  │         SessionManager                  │         │
│  │  - Multi-user session tracking          │         │
│  │  - Workspace isolation                  │         │
│  │  - Authentication                       │         │
│  └───────────┬─────────────────────────────┘         │
│              │                                        │
│              v                                        │
│  ┌─────────────────────────────────────────┐         │
│  │         StreamingAgentLoop              │         │
│  │  - Wraps existing AgentLoop             │         │
│  │  - Streams messages via WebSocket       │         │
│  │  - Supports pause/resume/interrupt      │         │
│  └───────────┬─────────────────────────────┘         │
│              │                                        │
│              v                                        │
│  ┌─────────────────────────────────────────┐         │
│  │         WebHarness (extends Harness)    │         │
│  │  - Same tool execution as LocalHarness  │         │
│  │  - Adds security policies per user      │         │
│  │  - Streams tool output incrementally    │         │
│  └───────────┬─────────────────────────────┘         │
│              │                                        │
│              v                                        │
│  ┌─────────────────────────────────────────┐         │
│  │         TraceStore (unchanged!)         │         │
│  │  - Already logs everything              │         │
│  │  - Perfect for UI visualization         │         │
│  └─────────────────────────────────────────┘         │
└──────────────────────────────────────────────────────┘
```

**Key Changes**:
1. **SessionManager**: Handles multi-user sessions (NEW)
2. **StreamingAgentLoop**: Wraps AgentLoop for WebSocket (NEW)
3. **WebHarness**: Extends LocalHarness with security (NEW)
4. **TraceStore**: Unchanged! Already perfect for this.

---

## Implementation Roadmap for Web UI

### Phase 0: Foundation (Already Built) ✅

You already have these:
- ✅ Message-based communication
- ✅ Harness abstraction
- ✅ TraceStore with complete execution capture
- ✅ Multi-agent coordination
- ✅ Browser automation
- ✅ Parallel execution

### Phase 1: Backend API (4-6 weeks)

#### Week 1-2: WebSocket Server
```python
# New file: src/compymac/web/server.py

from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure properly in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    """WebSocket endpoint for real-time agent communication."""
    await websocket.accept()

    # Get or create session
    session = session_manager.get_or_create(session_id)

    # Create streaming agent loop
    agent = StreamingAgentLoop(
        session=session,
        harness=WebHarness(session_id=session_id),
        message_callback=lambda msg: websocket.send_json(msg.to_dict())
    )

    try:
        async for message in websocket.iter_text():
            # Process user message
            response = await agent.run_async(message)
            # Response already streamed via callback

    except WebSocketDisconnect:
        session_manager.pause(session_id)
```

#### Week 3-4: Session Management
```python
# New file: src/compymac/web/session_manager.py

class SessionManager:
    """Manages multiple user sessions."""

    def __init__(self):
        self.sessions: dict[str, WebSession] = {}
        self.session_db = SessionDatabase()

    def get_or_create(self, session_id: str) -> WebSession:
        """Get existing session or create new one."""
        if session_id in self.sessions:
            return self.sessions[session_id]

        # Try to restore from database
        saved_state = self.session_db.load(session_id)
        if saved_state:
            session = WebSession.from_state(saved_state)
        else:
            session = WebSession(
                session_id=session_id,
                workspace=self._create_workspace(session_id),
                created_at=datetime.now(UTC)
            )

        self.sessions[session_id] = session
        return session

    def _create_workspace(self, session_id: str) -> Path:
        """Create isolated workspace for session."""
        workspace = Path(f"/workspaces/{session_id}")
        workspace.mkdir(parents=True, exist_ok=True)
        return workspace

    def pause(self, session_id: str) -> None:
        """Pause session and save state."""
        if session_id in self.sessions:
            session = self.sessions[session_id]
            self.session_db.save(session_id, session.to_state())

    def resume(self, session_id: str) -> WebSession:
        """Resume paused session."""
        return self.get_or_create(session_id)

@dataclass
class WebSession:
    """A web-based agent session."""
    session_id: str
    workspace: Path
    created_at: datetime
    last_active: datetime = field(default_factory=lambda: datetime.now(UTC))

    # Reuse existing compymac Session for agent state
    agent_session: Session = field(default_factory=Session)

    # Web-specific state
    user_id: str | None = None
    paused: bool = False
```

#### Week 5-6: Streaming Agent Loop
```python
# New file: src/compymac/web/streaming_agent.py

class StreamingAgentLoop:
    """AgentLoop wrapper that streams messages."""

    def __init__(self, session: WebSession, harness: Harness,
                 message_callback: Callable[[Message], None]):
        # Wrap existing AgentLoop
        self.agent = AgentLoop.create(
            system_prompt="...",
            harness=harness,
            llm_client=create_streaming_llm_client(message_callback)
        )
        self.session = session
        self.message_callback = message_callback

    async def run_async(self, user_message: str) -> None:
        """Run agent turn with streaming."""

        # Send user message
        self.message_callback(Message(
            role="user",
            content=user_message
        ))

        # Run agent (will stream via LLM client callback)
        result = await asyncio.to_thread(
            self.agent.run,
            user_message
        )

        # Send final result
        self.message_callback(Message(
            role="assistant",
            content=result.response
        ))

class StreamingLLMClient(LLMClient):
    """LLM client that streams tokens."""

    def __init__(self, base_client: LLMClient,
                 token_callback: Callable[[str], None]):
        self.base_client = base_client
        self.token_callback = token_callback

    def call(self, messages: list[Message], **kwargs) -> str:
        """Call LLM with streaming."""
        response = ""

        # Use streaming API
        for chunk in self.base_client.stream(messages, **kwargs):
            token = chunk.delta.content
            response += token

            # Stream token to frontend
            self.token_callback(token)

        return response
```

### Phase 2: Frontend (6-8 weeks)

```typescript
// frontend/src/components/AgentChat.tsx

import { useWebSocket } from '@/hooks/useWebSocket'
import { useState } from 'react'

export function AgentChat({ sessionId }: { sessionId: string }) {
  const { messages, sendMessage, isConnected } = useWebSocket(sessionId)
  const [input, setInput] = useState('')

  const handleSubmit = () => {
    sendMessage(input)
    setInput('')
  }

  return (
    <div className="flex flex-col h-screen">
      {/* Messages */}
      <div className="flex-1 overflow-y-auto">
        {messages.map((msg, idx) => (
          <MessageBubble key={idx} message={msg} />
        ))}
      </div>

      {/* Input */}
      <div className="p-4 border-t">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyPress={(e) => e.key === 'Enter' && handleSubmit()}
          placeholder="Tell the agent what to do..."
          disabled={!isConnected}
        />
      </div>
    </div>
  )
}

// frontend/src/hooks/useWebSocket.ts

export function useWebSocket(sessionId: string) {
  const [messages, setMessages] = useState<Message[]>([])
  const [ws, setWs] = useState<WebSocket | null>(null)

  useEffect(() => {
    const socket = new WebSocket(`ws://localhost:8000/ws/${sessionId}`)

    socket.onmessage = (event) => {
      const message = JSON.parse(event.data)
      setMessages((prev) => [...prev, message])
    }

    setWs(socket)

    return () => socket.close()
  }, [sessionId])

  const sendMessage = (content: string) => {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(content)
    }
  }

  return { messages, sendMessage, isConnected: ws?.readyState === WebSocket.OPEN }
}
```

### Phase 3: Advanced UI Features (4-6 weeks)

- **Agent View**: Show Manager/Planner/Executor/Reflector states
- **File Tree**: Live file browser with diffs
- **Terminal**: Show bash command execution
- **Browser View**: Embedded browser or screenshots
- **Trace Viewer**: Interactive TraceStore visualization
- **Pause/Resume**: Interrupt agent mid-execution

---

## Specific Questions Addressed

### 1. "Are we going down the right path?"

**YES**. Your current architecture is excellent for web UI:

- ✅ **Message-based communication**: Not CLI-specific
- ✅ **Harness abstraction**: Easy to wrap for web
- ✅ **TraceStore**: Perfect for rich UI visualization
- ✅ **Multi-agent**: Can show what each agent is doing
- ✅ **Modular tools**: Already structured for API exposure

**What you'd need to change**: Almost nothing in core logic. Just add a web layer on top.

### 2. "Like OpenWebUI or HyperChat?"

**YES**, similar pattern:

OpenWebUI Architecture:
```
Frontend (Svelte) → WebSocket → FastAPI Backend → LLM
```

CompyMac Web Architecture:
```
Frontend (React/Next.js) → WebSocket → FastAPI → StreamingAgentLoop → AgentLoop (existing)
```

**Key difference**: You have much more sophisticated backend (TraceStore, multi-agent, parallelization). The web layer is just an interface.

### 3. "Web page or local CLI?"

**BOTH**, easily:

```python
# Option 1: Web UI
compymac web --port 8000

# Option 2: CLI (existing)
compymac run "fix this bug"
```

The same core (`AgentLoop`, `Harness`, `TraceStore`) powers both. You just swap the interface layer.

### 4. "Implementation not until later"

**GOOD**. Here's why:

- Current work (tool verification, safety policies, SWE-bench) builds the foundation
- These improvements benefit BOTH CLI and web UI
- Web UI is "just" an interface layer on top
- No backtracking needed

**Priority order**:
1. ✅ **Now (Q1 2026)**: Production hardening (verification, safety, evaluation)
2. ⏸️ **Q2 2026**: Web UI backend (WebSocket, session management)
3. ⏸️ **Q3 2026**: Web UI frontend (React components)

---

## What NOT to Worry About

### ❌ You WON'T need to:

1. ❌ Rewrite `AgentLoop` - it's already perfect
2. ❌ Redesign `TraceStore` - it's exactly what you need
3. ❌ Change tool system - already modular
4. ❌ Refactor multi-agent - already has role separation
5. ❌ Rebuild parallelization - already supports it

### ✅ You WILL need to:

1. ✅ Add WebSocket server (new layer, doesn't change core)
2. ✅ Add session persistence (TraceStore already provides foundation)
3. ✅ Add user authentication (standard FastAPI middleware)
4. ✅ Add workspace isolation (you already have workspace concept)
5. ✅ Build frontend (completely separate from backend)

---

## Comparison to Other Tools

### Devin.ai (Web-first)

**Strengths**:
- Polished web UI
- Cloud-hosted (no local setup)

**CompyMac Advantages**:
- ✅ Open source (vs proprietary)
- ✅ TraceStore (complete execution capture)
- ✅ Multi-agent coordination (explicit roles)
- ✅ Parallel execution (rollouts, forked traces)
- ✅ Local or cloud deployment

**Architecture Similarity**: Very similar. Devin probably has:
- Session manager for multi-user
- WebSocket for streaming
- Cloud sandboxes for isolation

You'd be building the same thing, but with better observability (TraceStore) and parallelization.

### Claude Code (VSCode Extension)

**Strengths**:
- Deep IDE integration
- Native file editing experience

**CompyMac Advantages**:
- ✅ Browser automation (Claude Code can't do this)
- ✅ Multi-agent (Claude Code is single-agent)
- ✅ Parallelization (Claude Code is sequential)
- ✅ Web UI option (not tied to VSCode)

**Architecture Difference**: Claude Code is VSCode-first. You're building a web-first system that can also have CLI.

### Cursor (IDE)

**Strengths**:
- Native IDE (VSCode fork)
- Inline editing

**CompyMac Advantages**:
- ✅ Autonomous task completion (Cursor is interactive)
- ✅ Multi-agent workflows (Cursor is single-agent)
- ✅ Full stack (Cursor is code-only, no browser/bash)

---

## Recommended Next Steps

### Q1 2026: Focus on Core (Current Plan) ✅

1. ✅ Tool verification framework
2. ✅ Safety policies
3. ✅ ToolOutputSummarizer validation
4. ✅ SWE-bench integration

**Why**: These improvements benefit both CLI and web UI. Build a solid foundation first.

### Q2 2026: Web Backend (If Desired)

1. ⏸️ FastAPI + WebSocket server
2. ⏸️ Session manager with persistence
3. ⏸️ Authentication layer
4. ⏸️ Streaming agent wrapper

**Effort**: 6-8 weeks
**Risk**: Low (just adding a layer on top)

### Q3 2026: Web Frontend (If Desired)

1. ⏸️ React/Next.js app
2. ⏸️ Chat interface
3. ⏸️ File tree, terminal, browser views
4. ⏸️ Trace visualization

**Effort**: 8-10 weeks
**Risk**: Medium (frontend is always harder than expected)

---

## Architecture Decision: CLI vs Web

### Option A: CLI-First (Current)

**Pros**:
- ✅ Simpler deployment (no web server)
- ✅ Lower resource usage (no frontend)
- ✅ Easier debugging (direct output)
- ✅ Faster iteration (no frontend build step)

**Cons**:
- ❌ Less accessible (requires terminal comfort)
- ❌ No visual debugging (text-only output)
- ❌ Single user per machine
- ❌ Less "wow factor"

### Option B: Web-First (Future)

**Pros**:
- ✅ More accessible (web browser = universal)
- ✅ Rich visualization (file diffs, browser view, traces)
- ✅ Multi-user (cloud deployment)
- ✅ Better UX (modern web UI)

**Cons**:
- ❌ More complex deployment (web server + DB)
- ❌ Higher resource usage (frontend + backend)
- ❌ Slower iteration (need to build frontend)
- ❌ More attack surface (auth, sessions, CORS)

### Recommendation: Hybrid Approach ✅

**Phase 1 (Now - Q1 2026)**: CLI-first
- Focus on core capabilities
- Build foundation (verification, safety, evaluation)
- Use CLI for development and testing

**Phase 2 (Q2 2026)**: Web backend
- Add WebSocket API
- Wrap existing AgentLoop
- Support both CLI and web

**Phase 3 (Q3 2026)**: Web frontend
- Build React app
- Rich visualization
- Deploy as web service

**Result**: Same core, multiple interfaces. Users can choose CLI or web.

---

## Bottom Line

### You're on the RIGHT PATH ✅

**Current architecture is web-UI-ready**:
- Clean abstractions (Harness, Session, TraceStore)
- Message-based communication (easy to stream)
- Complete execution capture (perfect for UI)
- Multi-agent coordination (can visualize roles)

**Minimal additions needed**:
- WebSocket server (1-2 weeks)
- Session management (2-3 weeks)
- Streaming wrapper (1-2 weeks)
- Frontend (8-10 weeks)

**No backtracking required**:
- Core logic stays the same
- Just add a web layer on top
- CLI and web can coexist

**Priority**:
- Focus on production hardening now (Q1 2026)
- Add web layer later (Q2-Q3 2026)
- Current work benefits both CLI and web

**You're building the right foundation. The web UI will be easy to add when you're ready.**

---

**Questions?**

1. Should we add web UI to Q2 2026 roadmap, or defer?
2. Do you want local-first (OpenWebUI style) or cloud-first (Devin style)?
3. Any specific UI features from Devin/Claude that are must-haves?

Let me know if you want me to expand on any section!
