# CompyMac Web UI Implementation Plan

**Purpose**: Detailed implementation plan for building a modern web interface for CompyMac, similar to Devin.ai or claude.ai/code

**Date**: December 22, 2025
**Timeline**: 12 weeks (Q2 2026)
**Based on**: Modern AI chat best practices 2025, Vercel AI SDK, Next.js App Router

---

## Executive Summary

### What We're Building

A **modern, production-ready web interface** for CompyMac that enables:

- ✅ **Real-time agent interaction** - Chat-style interface with streaming responses
- ✅ **Multi-panel IDE-style layout** - Chat, file tree, terminal, browser, trace viewer
- ✅ **Multi-user support** - Isolated sessions, workspaces, authentication
- ✅ **Session persistence** - Save/resume long-running tasks
- ✅ **Real-time collaboration** - Multiple users can observe (optional)
- ✅ **Rich visualization** - TraceStore data, file diffs, browser screenshots

### Technology Stack (2025 Best Practices)

**Backend**:
- **FastAPI** - High-performance Python web framework
- **WebSockets** - Real-time bidirectional communication
- **PostgreSQL** - Session persistence (upgrade from SQLite)
- **Redis** - Session state caching, pub/sub for collaboration

**Frontend** (following [modern AI chat best practices](https://dev.to/hashan2kk2/how-to-build-ai-powered-react-apps-in-2025-1pcf)):
- **Next.js 15** - App Router with Server Components
- **Vercel AI SDK** - Built-in streaming, state management ([recommended for AI chat](https://medium.com/@johngoyason/ai-sdk-and-react-next-js-unlocking-a-new-era-of-interactive-ai-agents-f860326c7e35))
- **React 19** - Concurrent features, Server Actions
- **TypeScript** - Type safety throughout
- **Tailwind CSS** - Modern styling
- **shadcn/ui** - High-quality component library
- **Monaco Editor** - VS Code editor component

**Infrastructure**:
- **Docker** - Containerization for deployment
- **Nginx** - Reverse proxy, static file serving
- **GitHub Actions** - CI/CD pipeline
- **Vercel/Railway/Fly.io** - Deployment options

---

## Architecture Overview

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────┐
│                     Frontend (Next.js)                  │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐    │
│  │ Chat Panel  │  │ File Tree   │  │ Terminal    │    │
│  │ (Streaming) │  │ (Real-time) │  │ (Live logs) │    │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘    │
│         │                 │                 │            │
│  ┌──────┴──────────┬──────┴──────────┬──────┴─────┐    │
│  │ Browser Preview │ Agent Inspector │ Trace View │    │
│  └──────┬──────────┘ └──────┬────────┘ └──────┬────┘    │
└─────────┼──────────────────┼─────────────────┼──────────┘
          │                   │                  │
          │    WebSocket      │                  │
          v                   v                  v
┌─────────────────────────────────────────────────────────┐
│               Backend (FastAPI + WebSocket)             │
│                                                          │
│  ┌────────────────────────────────────────────────┐    │
│  │           SessionManager                       │    │
│  │  - Session isolation & authentication          │    │
│  │  - Workspace management                        │    │
│  │  - State persistence (PostgreSQL)              │    │
│  │  - Real-time pub/sub (Redis)                   │    │
│  └──────────────────┬─────────────────────────────┘    │
│                     │                                    │
│  ┌──────────────────v─────────────────────────────┐    │
│  │        StreamingAgentLoop                      │    │
│  │  - Wraps existing AgentLoop                    │    │
│  │  - Token-by-token streaming via WebSocket      │    │
│  │  - Pause/resume/cancel support                 │    │
│  │  - Event emission (tool calls, state changes)  │    │
│  └──────────────────┬─────────────────────────────┘    │
│                     │                                    │
│  ┌──────────────────v─────────────────────────────┐    │
│  │         WebHarness (extends LocalHarness)      │    │
│  │  - Same tool execution                         │    │
│  │  - Streams tool output incrementally           │    │
│  │  - Per-user safety policies                    │    │
│  │  - Workspace isolation                         │    │
│  └──────────────────┬─────────────────────────────┘    │
│                     │                                    │
│  ┌──────────────────v─────────────────────────────┐    │
│  │         TraceStore (unchanged!)                │    │
│  │  - Complete execution capture                  │    │
│  │  - Perfect for UI visualization                │    │
│  │  - PostgreSQL backend (multi-user ready)       │    │
│  └────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────┘
```

### Key Design Decisions

1. **Existing core unchanged** - AgentLoop, Harness, TraceStore remain as-is
2. **WebSocket for real-time** - Token-by-token streaming, live updates
3. **Server Components for performance** - Next.js App Router optimizes initial load
4. **Vercel AI SDK for chat** - Built-in streaming, state management, proven patterns
5. **PostgreSQL for multi-user** - Replace SQLite with scalable database
6. **Redis for real-time** - Session caching, pub/sub for live collaboration

---

## Week-by-Week Implementation Plan

### Phase 1: Backend Foundation (Weeks 1-3)

#### Week 1: FastAPI + WebSocket Server

**Goal**: Basic WebSocket server that can stream messages

**Tasks**:
1. Set up FastAPI project structure
2. Implement WebSocket endpoint
3. Add session management (in-memory for now)
4. Implement basic streaming

**Deliverables**:

```python
# src/compymac/web/main.py

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import json

app = FastAPI(title="CompyMac API")

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Next.js dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory session storage (temporary)
sessions = {}

@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    """WebSocket endpoint for real-time agent communication."""
    await websocket.accept()

    # Get or create session
    if session_id not in sessions:
        sessions[session_id] = {
            "messages": [],
            "active": True
        }

    session = sessions[session_id]

    try:
        async for message in websocket.iter_text():
            data = json.loads(message)

            if data["type"] == "user_message":
                # Echo user message
                await websocket.send_json({
                    "type": "user_message_ack",
                    "content": data["content"]
                })

                # Simulate streaming response (replace with actual agent later)
                response = f"You said: {data['content']}"
                for char in response:
                    await websocket.send_json({
                        "type": "assistant_token",
                        "token": char
                    })
                    await asyncio.sleep(0.01)  # Simulate streaming delay

                await websocket.send_json({
                    "type": "assistant_message_complete",
                    "full_content": response
                })

    except WebSocketDisconnect:
        session["active"] = False
        print(f"Session {session_id} disconnected")

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok"}
```

**Testing**:
```bash
# Run server
uvicorn compymac.web.main:app --reload --port 8000

# Test WebSocket (using wscat or Python client)
wscat -c "ws://localhost:8000/ws/test-session"
> {"type": "user_message", "content": "Hello!"}
< {"type": "user_message_ack", "content": "Hello!"}
< {"type": "assistant_token", "token": "Y"}
< {"type": "assistant_token", "token": "o"}
< {"type": "assistant_token", "token": "u"}
...
```

---

#### Week 2: Session Management + PostgreSQL

**Goal**: Persistent sessions with database backend

**Tasks**:
1. Set up PostgreSQL database
2. Create session models with SQLAlchemy
3. Implement session CRUD operations
4. Add authentication (JWT tokens)

**Deliverables**:

```python
# src/compymac/web/database.py

from sqlalchemy import create_engine, Column, String, DateTime, JSON, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime, UTC
import os

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:pass@localhost/compymac")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class Session(Base):
    """User session in database."""
    __tablename__ = "sessions"

    id = Column(String, primary_key=True)
    user_id = Column(String, nullable=False, index=True)
    workspace_path = Column(String, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    last_active = Column(DateTime, default=lambda: datetime.now(UTC))
    paused = Column(Boolean, default=False)

    # Session state (JSON)
    agent_state = Column(JSON, default=dict)
    messages = Column(JSON, default=list)

class User(Base):
    """User account."""
    __tablename__ = "users"

    id = Column(String, primary_key=True)
    email = Column(String, unique=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    is_active = Column(Boolean, default=True)

# Create tables
Base.metadata.create_all(bind=engine)
```

```python
# src/compymac/web/session_manager.py

from pathlib import Path
from datetime import datetime, UTC
import uuid
from compymac.web.database import SessionLocal, Session as DBSession
from compymac.session import Session as AgentSession

class SessionManager:
    """Manages user sessions with database persistence."""

    def __init__(self):
        self.db = SessionLocal()
        self.workspaces_root = Path("/workspaces")
        self.workspaces_root.mkdir(parents=True, exist_ok=True)

    def create_session(self, user_id: str) -> str:
        """Create new session for user."""
        session_id = str(uuid.uuid4())
        workspace_path = self.workspaces_root / session_id
        workspace_path.mkdir(parents=True, exist_ok=True)

        db_session = DBSession(
            id=session_id,
            user_id=user_id,
            workspace_path=str(workspace_path)
        )
        self.db.add(db_session)
        self.db.commit()

        return session_id

    def get_session(self, session_id: str) -> DBSession | None:
        """Get session by ID."""
        return self.db.query(DBSession).filter(
            DBSession.id == session_id
        ).first()

    def update_session(self, session_id: str, agent_state: dict, messages: list):
        """Update session state."""
        db_session = self.get_session(session_id)
        if db_session:
            db_session.agent_state = agent_state
            db_session.messages = messages
            db_session.last_active = datetime.now(UTC)
            self.db.commit()

    def pause_session(self, session_id: str):
        """Pause session (save state, release resources)."""
        db_session = self.get_session(session_id)
        if db_session:
            db_session.paused = True
            self.db.commit()

    def resume_session(self, session_id: str) -> AgentSession:
        """Resume paused session."""
        db_session = self.get_session(session_id)
        if not db_session:
            raise ValueError(f"Session {session_id} not found")

        # Restore agent session from saved state
        agent_session = AgentSession()
        # TODO: Restore state from db_session.agent_state

        db_session.paused = False
        self.db.commit()

        return agent_session

    def delete_session(self, session_id: str):
        """Delete session and workspace."""
        db_session = self.get_session(session_id)
        if db_session:
            # Delete workspace files
            workspace = Path(db_session.workspace_path)
            if workspace.exists():
                import shutil
                shutil.rmtree(workspace)

            # Delete from database
            self.db.delete(db_session)
            self.db.commit()
```

**Migration**:
```bash
# Install alembic for migrations
pip install alembic

# Initialize migrations
alembic init migrations

# Create first migration
alembic revision --autogenerate -m "Initial tables"

# Apply migrations
alembic upgrade head
```

---

#### Week 3: StreamingAgentLoop Integration

**Goal**: Integrate existing AgentLoop with WebSocket streaming

**Tasks**:
1. Create StreamingAgentLoop wrapper
2. Implement token-by-token streaming
3. Add event emission (tool calls, state changes)
4. Add pause/resume/cancel support

**Deliverables**:

```python
# src/compymac/web/streaming_agent.py

import asyncio
from typing import Callable, Any
from compymac.agent_loop import AgentLoop
from compymac.llm import LLMClient
from compymac.types import Message
from compymac.harness import Harness

class StreamingLLMClient(LLMClient):
    """LLM client that streams tokens via callback."""

    def __init__(self, base_client: LLMClient,
                 token_callback: Callable[[str], None]):
        self.base_client = base_client
        self.token_callback = token_callback

    async def call_streaming(self, messages: list[Message], **kwargs) -> str:
        """Call LLM with token-by-token streaming."""
        response = ""

        # Use streaming API (implementation depends on LLM provider)
        async for chunk in self.base_client.stream(messages, **kwargs):
            token = chunk.choices[0].delta.content
            if token:
                response += token
                # Stream token to frontend
                await asyncio.to_thread(self.token_callback, token)

        return response

    def call(self, messages: list[Message], **kwargs) -> str:
        """Synchronous wrapper for backward compatibility."""
        return asyncio.run(self.call_streaming(messages, **kwargs))

class StreamingAgentLoop:
    """AgentLoop wrapper that streams to WebSocket."""

    def __init__(self,
                 session_id: str,
                 harness: Harness,
                 llm_client: LLMClient,
                 event_callback: Callable[[dict], None]):
        self.session_id = session_id
        self.event_callback = event_callback

        # Wrap LLM client for streaming
        streaming_llm = StreamingLLMClient(
            llm_client,
            lambda token: self.emit_event({
                "type": "assistant_token",
                "token": token
            })
        )

        # Create agent with streaming LLM
        self.agent = AgentLoop.create(
            system_prompt="You are a helpful coding assistant.",
            harness=harness,
            llm_client=streaming_llm
        )

        self.cancelled = False

    def emit_event(self, event: dict):
        """Emit event to frontend via callback."""
        self.event_callback(event)

    async def run_async(self, user_message: str):
        """Run agent turn with streaming and event emission."""

        # Emit user message acknowledgment
        self.emit_event({
            "type": "user_message_ack",
            "content": user_message
        })

        # Run agent (will stream tokens via StreamingLLMClient)
        try:
            result = await asyncio.to_thread(
                self.agent.run,
                user_message
            )

            if self.cancelled:
                self.emit_event({
                    "type": "cancelled",
                    "message": "Task cancelled by user"
                })
                return

            # Emit completion
            self.emit_event({
                "type": "assistant_message_complete",
                "content": result.response,
                "tool_calls": result.tool_calls_made,
                "tokens": result.tokens_used
            })

        except Exception as e:
            self.emit_event({
                "type": "error",
                "error": str(e)
            })

    def cancel(self):
        """Cancel ongoing task."""
        self.cancelled = True
        # TODO: Implement graceful cancellation in AgentLoop
```

**Updated WebSocket endpoint**:

```python
# Update src/compymac/web/main.py

from compymac.web.streaming_agent import StreamingAgentLoop
from compymac.web.session_manager import SessionManager
from compymac.local_harness import LocalHarness
from compymac.llm import LLMClient

session_manager = SessionManager()

@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    await websocket.accept()

    # Get or create session
    db_session = session_manager.get_session(session_id)
    if not db_session:
        await websocket.send_json({
            "type": "error",
            "error": "Session not found"
        })
        await websocket.close()
        return

    # Create streaming agent
    harness = LocalHarness(workspace=Path(db_session.workspace_path))
    llm_client = LLMClient()  # Configure with API keys

    agent = StreamingAgentLoop(
        session_id=session_id,
        harness=harness,
        llm_client=llm_client,
        event_callback=lambda event: asyncio.create_task(
            websocket.send_json(event)
        )
    )

    try:
        async for message in websocket.iter_text():
            data = json.loads(message)

            if data["type"] == "user_message":
                # Run agent asynchronously
                await agent.run_async(data["content"])

            elif data["type"] == "cancel":
                agent.cancel()

    except WebSocketDisconnect:
        session_manager.pause_session(session_id)
```

---

### Phase 2: Frontend Foundation (Weeks 4-6)

#### Week 4: Next.js App Setup + Basic Chat UI

**Goal**: Working chat interface with WebSocket connection

**Tasks**:
1. Initialize Next.js 15 project with App Router
2. Set up Vercel AI SDK
3. Create basic chat UI
4. Implement WebSocket client

**Deliverables**:

```bash
# Create Next.js project
npx create-next-app@latest compymac-web --typescript --tailwind --app

cd compymac-web

# Install dependencies
npm install ai @ai-sdk/react
npm install @radix-ui/react-avatar @radix-ui/react-scroll-area
npm install lucide-react class-variance-authority clsx tailwind-merge
```

```typescript
// app/chat/[sessionId]/page.tsx

'use client'

import { useEffect, useState, useRef } from 'react'
import { useParams } from 'next/navigation'
import { Message } from '@/types'
import { ChatMessage } from '@/components/ChatMessage'
import { ChatInput } from '@/components/ChatInput'

export default function ChatPage() {
  const params = useParams()
  const sessionId = params.sessionId as string

  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [isConnected, setIsConnected] = useState(false)
  const [isStreaming, setIsStreaming] = useState(false)

  const ws = useRef<WebSocket | null>(null)
  const currentMessage = useRef('')

  useEffect(() => {
    // Connect to WebSocket
    const socket = new WebSocket(`ws://localhost:8000/ws/${sessionId}`)

    socket.onopen = () => {
      console.log('WebSocket connected')
      setIsConnected(true)
    }

    socket.onmessage = (event) => {
      const data = JSON.parse(event.data)

      switch (data.type) {
        case 'user_message_ack':
          setMessages(prev => [...prev, {
            role: 'user',
            content: data.content
          }])
          setIsStreaming(true)
          break

        case 'assistant_token':
          currentMessage.current += data.token
          setMessages(prev => {
            const newMessages = [...prev]
            const lastMessage = newMessages[newMessages.length - 1]

            if (lastMessage?.role === 'assistant') {
              lastMessage.content = currentMessage.current
            } else {
              newMessages.push({
                role: 'assistant',
                content: currentMessage.current
              })
            }

            return newMessages
          })
          break

        case 'assistant_message_complete':
          currentMessage.current = ''
          setIsStreaming(false)
          break

        case 'error':
          console.error('Error from server:', data.error)
          setIsStreaming(false)
          break
      }
    }

    socket.onclose = () => {
      console.log('WebSocket disconnected')
      setIsConnected(false)
    }

    ws.current = socket

    return () => {
      socket.close()
    }
  }, [sessionId])

  const sendMessage = () => {
    if (!input.trim() || !ws.current || !isConnected) return

    ws.current.send(JSON.stringify({
      type: 'user_message',
      content: input
    }))

    setInput('')
  }

  return (
    <div className="flex flex-col h-screen">
      {/* Header */}
      <div className="border-b p-4 flex items-center justify-between">
        <h1 className="text-lg font-semibold">CompyMac Agent</h1>
        <div className="flex items-center gap-2">
          <div className={`w-2 h-2 rounded-full ${isConnected ? 'bg-green-500' : 'bg-red-500'}`} />
          <span className="text-sm text-gray-600">
            {isConnected ? 'Connected' : 'Disconnected'}
          </span>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.map((message, i) => (
          <ChatMessage key={i} message={message} />
        ))}
      </div>

      {/* Input */}
      <ChatInput
        value={input}
        onChange={setInput}
        onSend={sendMessage}
        disabled={!isConnected || isStreaming}
      />
    </div>
  )
}
```

```typescript
// components/ChatMessage.tsx

import { Avatar } from '@/components/ui/avatar'
import { Message } from '@/types'

export function ChatMessage({ message }: { message: Message }) {
  const isUser = message.role === 'user'

  return (
    <div className={`flex gap-3 ${isUser ? 'justify-end' : ''}`}>
      {!isUser && (
        <Avatar className="h-8 w-8">
          <div className="bg-blue-500 text-white flex items-center justify-center h-full">
            AI
          </div>
        </Avatar>
      )}

      <div className={`rounded-lg p-3 max-w-[70%] ${
        isUser
          ? 'bg-blue-500 text-white'
          : 'bg-gray-100 text-gray-900'
      }`}>
        <p className="text-sm whitespace-pre-wrap">{message.content}</p>
      </div>

      {isUser && (
        <Avatar className="h-8 w-8">
          <div className="bg-gray-500 text-white flex items-center justify-center h-full">
            U
          </div>
        </Avatar>
      )}
    </div>
  )
}
```

```typescript
// components/ChatInput.tsx

import { Send } from 'lucide-react'
import { KeyboardEvent } from 'react'

interface ChatInputProps {
  value: string
  onChange: (value: string) => void
  onSend: () => void
  disabled: boolean
}

export function ChatInput({ value, onChange, onSend, disabled }: ChatInputProps) {
  const handleKeyPress = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      onSend()
    }
  }

  return (
    <div className="border-t p-4">
      <div className="flex gap-2">
        <textarea
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onKeyPress={handleKeyPress}
          placeholder="Tell the agent what to do..."
          disabled={disabled}
          className="flex-1 resize-none border rounded-lg p-3 focus:outline-none focus:ring-2 focus:ring-blue-500"
          rows={3}
        />
        <button
          onClick={onSend}
          disabled={disabled || !value.trim()}
          className="px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <Send className="w-5 h-5" />
        </button>
      </div>
    </div>
  )
}
```

**Testing**:
```bash
# Run frontend
npm run dev

# Open browser to http://localhost:3000/chat/test-session
# Type message, verify streaming works
```

---

#### Week 5: Multi-Panel Layout + File Tree

**Goal**: IDE-style layout with chat, file tree, terminal

**Tasks**:
1. Create resizable panel layout
2. Implement file tree component
3. Add terminal panel
4. Add browser preview panel

**Deliverables**:

```bash
# Install panel library
npm install react-resizable-panels
```

```typescript
// app/chat/[sessionId]/page.tsx (updated with layout)

'use client'

import { ResizablePanelGroup, ResizablePanel, ResizableHandle } from '@/components/ui/resizable'
import { ChatPanel } from '@/components/panels/ChatPanel'
import { FileTreePanel } from '@/components/panels/FileTreePanel'
import { TerminalPanel } from '@/components/panels/TerminalPanel'
import { BrowserPanel } from '@/components/panels/BrowserPanel'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'

export default function ChatPage() {
  const params = useParams()
  const sessionId = params.sessionId as string

  return (
    <div className="h-screen flex flex-col">
      {/* Top bar */}
      <div className="border-b p-2 flex items-center justify-between">
        <h1 className="text-lg font-semibold">CompyMac</h1>
        {/* Add session controls, settings */}
      </div>

      {/* Main layout */}
      <ResizablePanelGroup direction="horizontal" className="flex-1">
        {/* Left sidebar: File tree */}
        <ResizablePanel defaultSize={20} minSize={15}>
          <FileTreePanel sessionId={sessionId} />
        </ResizablePanel>

        <ResizableHandle />

        {/* Center: Chat */}
        <ResizablePanel defaultSize={50} minSize={30}>
          <ChatPanel sessionId={sessionId} />
        </ResizablePanel>

        <ResizableHandle />

        {/* Right panel: Terminal/Browser/Trace tabs */}
        <ResizablePanel defaultSize={30} minSize={20}>
          <Tabs defaultValue="terminal" className="h-full flex flex-col">
            <TabsList className="w-full justify-start border-b rounded-none">
              <TabsTrigger value="terminal">Terminal</TabsTrigger>
              <TabsTrigger value="browser">Browser</TabsTrigger>
              <TabsTrigger value="trace">Trace</TabsTrigger>
            </TabsList>

            <TabsContent value="terminal" className="flex-1">
              <TerminalPanel sessionId={sessionId} />
            </TabsContent>

            <TabsContent value="browser" className="flex-1">
              <BrowserPanel sessionId={sessionId} />
            </TabsContent>

            <TabsContent value="trace" className="flex-1">
              {/* Trace viewer component */}
            </TabsContent>
          </Tabs>
        </ResizablePanel>
      </ResizablePanelGroup>
    </div>
  )
}
```

```typescript
// components/panels/FileTreePanel.tsx

'use client'

import { useState, useEffect } from 'react'
import { ChevronRight, ChevronDown, File, Folder } from 'lucide-react'

interface FileNode {
  name: string
  path: string
  type: 'file' | 'directory'
  children?: FileNode[]
}

export function FileTreePanel({ sessionId }: { sessionId: string }) {
  const [tree, setTree] = useState<FileNode[]>([])
  const [expanded, setExpanded] = useState<Set<string>>(new Set())

  useEffect(() => {
    // Fetch file tree from backend
    fetch(`http://localhost:8000/api/sessions/${sessionId}/files`)
      .then(res => res.json())
      .then(data => setTree(data))
  }, [sessionId])

  const toggleExpand = (path: string) => {
    setExpanded(prev => {
      const next = new Set(prev)
      if (next.has(path)) {
        next.delete(path)
      } else {
        next.add(path)
      }
      return next
    })
  }

  const renderNode = (node: FileNode, depth: number = 0) => {
    const isExpanded = expanded.has(node.path)
    const hasChildren = node.children && node.children.length > 0

    return (
      <div key={node.path}>
        <div
          className="flex items-center gap-1 px-2 py-1 hover:bg-gray-100 cursor-pointer"
          style={{ paddingLeft: `${depth * 12 + 8}px` }}
          onClick={() => node.type === 'directory' && toggleExpand(node.path)}
        >
          {node.type === 'directory' ? (
            <>
              {hasChildren && (
                isExpanded ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />
              )}
              <Folder className="w-4 h-4 text-blue-500" />
            </>
          ) : (
            <File className="w-4 h-4 text-gray-500" />
          )}
          <span className="text-sm">{node.name}</span>
        </div>

        {node.type === 'directory' && isExpanded && node.children && (
          <div>
            {node.children.map(child => renderNode(child, depth + 1))}
          </div>
        )}
      </div>
    )
  }

  return (
    <div className="h-full overflow-y-auto border-r">
      <div className="p-2 border-b">
        <h2 className="text-sm font-semibold">Files</h2>
      </div>
      <div>
        {tree.map(node => renderNode(node))}
      </div>
    </div>
  )
}
```

```typescript
// components/panels/TerminalPanel.tsx

'use client'

import { useEffect, useRef, useState } from 'react'
import { Terminal } from 'lucide-react'

export function TerminalPanel({ sessionId }: { sessionId: string }) {
  const [output, setOutput] = useState<string[]>([])
  const terminalRef = useRef<HTMLDivElement>(null)
  const ws = useRef<WebSocket | null>(null)

  useEffect(() => {
    // Connect to WebSocket for terminal output
    const socket = new WebSocket(`ws://localhost:8000/ws/${sessionId}`)

    socket.onmessage = (event) => {
      const data = JSON.parse(event.data)

      if (data.type === 'terminal_output') {
        setOutput(prev => [...prev, data.content])

        // Auto-scroll to bottom
        if (terminalRef.current) {
          terminalRef.current.scrollTop = terminalRef.current.scrollHeight
        }
      }
    }

    ws.current = socket

    return () => socket.close()
  }, [sessionId])

  return (
    <div className="h-full flex flex-col bg-gray-900 text-gray-100">
      <div className="p-2 border-b border-gray-700 flex items-center gap-2">
        <Terminal className="w-4 h-4" />
        <span className="text-sm font-semibold">Terminal</span>
      </div>

      <div
        ref={terminalRef}
        className="flex-1 overflow-y-auto p-2 font-mono text-sm"
      >
        {output.map((line, i) => (
          <div key={i} className="whitespace-pre-wrap">{line}</div>
        ))}
      </div>
    </div>
  )
}
```

---

#### Week 6: Agent Inspector + Trace Viewer

**Goal**: Visualize agent state and trace data

**Tasks**:
1. Create agent inspector component (shows current plan, active tools)
2. Implement trace viewer (shows TraceStore data)
3. Add real-time updates from backend
4. Add filtering/search in traces

**Deliverables**:

```typescript
// components/panels/AgentInspector.tsx

'use client'

import { useState, useEffect } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'

interface AgentState {
  current_role: 'manager' | 'planner' | 'executor' | 'reflector'
  current_plan: string[]
  active_tools: string[]
  todos: Array<{
    content: string
    status: 'pending' | 'in_progress' | 'completed'
  }>
}

export function AgentInspector({ sessionId }: { sessionId: string }) {
  const [state, setState] = useState<AgentState | null>(null)

  useEffect(() => {
    // Poll for agent state updates
    const interval = setInterval(() => {
      fetch(`http://localhost:8000/api/sessions/${sessionId}/state`)
        .then(res => res.json())
        .then(data => setState(data))
    }, 1000)

    return () => clearInterval(interval)
  }, [sessionId])

  if (!state) return <div>Loading...</div>

  return (
    <div className="p-4 space-y-4 overflow-y-auto">
      {/* Current Role */}
      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Current Agent</CardTitle>
        </CardHeader>
        <CardContent>
          <Badge variant="outline" className="text-sm capitalize">
            {state.current_role}
          </Badge>
        </CardContent>
      </Card>

      {/* Current Plan */}
      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Plan</CardTitle>
        </CardHeader>
        <CardContent>
          <ol className="list-decimal list-inside space-y-1">
            {state.current_plan.map((step, i) => (
              <li key={i} className="text-sm text-gray-700">{step}</li>
            ))}
          </ol>
        </CardContent>
      </Card>

      {/* Active Tools */}
      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Active Tools</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-2">
            {state.active_tools.map(tool => (
              <Badge key={tool} variant="secondary" className="text-xs">
                {tool}
              </Badge>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Todos */}
      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Todos</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-2">
            {state.todos.map((todo, i) => (
              <div key={i} className="flex items-start gap-2">
                <input
                  type="checkbox"
                  checked={todo.status === 'completed'}
                  disabled
                  className="mt-1"
                />
                <span className={`text-sm ${
                  todo.status === 'completed' ? 'line-through text-gray-500' : ''
                }`}>
                  {todo.content}
                </span>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
```

```typescript
// components/panels/TraceViewer.tsx

'use client'

import { useState, useEffect } from 'react'
import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { ChevronRight, ChevronDown } from 'lucide-react'

interface TraceEvent {
  id: string
  timestamp: string
  span_kind: string
  span_name: string
  status: 'started' | 'ok' | 'error'
  attributes: Record<string, any>
  children?: TraceEvent[]
}

export function TraceViewer({ sessionId }: { sessionId: string }) {
  const [events, setEvents] = useState<TraceEvent[]>([])
  const [expanded, setExpanded] = useState<Set<string>>(new Set())

  useEffect(() => {
    // Fetch trace data from TraceStore
    fetch(`http://localhost:8000/api/sessions/${sessionId}/trace`)
      .then(res => res.json())
      .then(data => setEvents(data))
  }, [sessionId])

  const toggleExpand = (id: string) => {
    setExpanded(prev => {
      const next = new Set(prev)
      if (next.has(id)) {
        next.delete(id)
      } else {
        next.add(id)
      }
      return next
    })
  }

  const renderEvent = (event: TraceEvent, depth: number = 0) => {
    const isExpanded = expanded.has(event.id)
    const hasChildren = event.children && event.children.length > 0

    const statusColor = {
      'started': 'bg-blue-100 text-blue-800',
      'ok': 'bg-green-100 text-green-800',
      'error': 'bg-red-100 text-red-800'
    }[event.status]

    return (
      <div key={event.id}>
        <div
          className="flex items-center gap-2 p-2 hover:bg-gray-50 cursor-pointer border-b"
          style={{ paddingLeft: `${depth * 20 + 8}px` }}
          onClick={() => toggleExpand(event.id)}
        >
          {hasChildren && (
            isExpanded ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />
          )}

          <span className="text-xs text-gray-500">{event.timestamp}</span>

          <Badge variant="outline" className={`text-xs ${statusColor}`}>
            {event.status}
          </Badge>

          <span className="text-sm font-mono">{event.span_name}</span>
        </div>

        {isExpanded && (
          <div className="bg-gray-50 p-2 border-b" style={{ paddingLeft: `${depth * 20 + 40}px` }}>
            <pre className="text-xs overflow-x-auto">
              {JSON.stringify(event.attributes, null, 2)}
            </pre>
          </div>
        )}

        {isExpanded && event.children && (
          <div>
            {event.children.map(child => renderEvent(child, depth + 1))}
          </div>
        )}
      </div>
    )
  }

  return (
    <div className="h-full overflow-y-auto">
      <div className="p-2 border-b sticky top-0 bg-white">
        <h2 className="text-sm font-semibold">Execution Trace</h2>
      </div>
      <div>
        {events.map(event => renderEvent(event))}
      </div>
    </div>
  )
}
```

---

### Phase 3: Advanced Features (Weeks 7-9)

#### Week 7: Authentication + User Management

**Goal**: Secure multi-user support

**Tasks**:
1. Implement JWT authentication
2. Add login/signup pages
3. Add user management API
4. Add session ownership checks

**Deliverables**:

```python
# src/compymac/web/auth.py

from datetime import datetime, timedelta, UTC
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
import os

SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against hash."""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """Hash password."""
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: timedelta | None = None):
    """Create JWT token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(UTC) + expires_delta
    else:
        expire = datetime.now(UTC) + timedelta(minutes=15)

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(token: str = Depends(oauth2_scheme)):
    """Get current user from JWT token."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    # Get user from database
    from compymac.web.database import SessionLocal, User
    db = SessionLocal()
    user = db.query(User).filter(User.id == user_id).first()

    if user is None:
        raise credentials_exception

    return user
```

```python
# Add auth endpoints to main.py

from fastapi.security import OAuth2PasswordRequestForm
from compymac.web.auth import (
    verify_password,
    get_password_hash,
    create_access_token,
    get_current_user
)
from compymac.web.database import User

@app.post("/auth/signup")
async def signup(email: str, password: str):
    """Create new user account."""
    db = SessionLocal()

    # Check if user exists
    existing = db.query(User).filter(User.email == email).first()
    if existing:
        raise HTTPException(400, "Email already registered")

    # Create user
    user = User(
        id=str(uuid.uuid4()),
        email=email,
        hashed_password=get_password_hash(password)
    )
    db.add(user)
    db.commit()

    return {"message": "User created successfully"}

@app.post("/auth/login")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """Login and get access token."""
    db = SessionLocal()
    user = db.query(User).filter(User.email == form_data.username).first()

    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(401, "Incorrect email or password")

    access_token = create_access_token(
        data={"sub": user.id},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )

    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/auth/me")
async def get_me(current_user: User = Depends(get_current_user)):
    """Get current user info."""
    return {
        "id": current_user.id,
        "email": current_user.email
    }

@app.post("/sessions/create")
async def create_session(current_user: User = Depends(get_current_user)):
    """Create new session for user."""
    session_id = session_manager.create_session(current_user.id)
    return {"session_id": session_id}
```

```typescript
// app/auth/login/page.tsx

'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'

export default function LoginPage() {
  const router = useRouter()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')

  const handleLogin = async () => {
    try {
      const formData = new FormData()
      formData.append('username', email)  // OAuth2 uses 'username' field
      formData.append('password', password)

      const res = await fetch('http://localhost:8000/auth/login', {
        method: 'POST',
        body: formData
      })

      if (!res.ok) {
        throw new Error('Login failed')
      }

      const data = await res.json()

      // Store token
      localStorage.setItem('token', data.access_token)

      // Create session
      const sessionRes = await fetch('http://localhost:8000/sessions/create', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${data.access_token}`
        }
      })

      const sessionData = await sessionRes.json()

      // Redirect to chat
      router.push(`/chat/${sessionData.session_id}`)

    } catch (err) {
      setError('Invalid email or password')
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-100">
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle>Login to CompyMac</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <label className="block text-sm font-medium mb-1">Email</label>
            <Input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
            />
          </div>

          <div>
            <label className="block text-sm font-medium mb-1">Password</label>
            <Input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
            />
          </div>

          {error && (
            <div className="text-sm text-red-500">{error}</div>
          )}

          <Button onClick={handleLogin} className="w-full">
            Login
          </Button>

          <div className="text-center text-sm">
            Don't have an account?{' '}
            <a href="/auth/signup" className="text-blue-500 hover:underline">
              Sign up
            </a>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
```

---

#### Week 8: File Editor + Code Viewer

**Goal**: View and edit files in browser

**Tasks**:
1. Integrate Monaco Editor (VS Code editor)
2. Add file viewing/editing
3. Add syntax highlighting
4. Add file diff viewer

**Deliverables**:

```bash
# Install Monaco Editor
npm install @monaco-editor/react
```

```typescript
// components/panels/CodeEditor.tsx

'use client'

import { useEffect, useState } from 'react'
import Editor from '@monaco-editor/react'

interface CodeEditorProps {
  sessionId: string
  filePath: string
}

export function CodeEditor({ sessionId, filePath }: CodeEditorProps) {
  const [content, setContent] = useState('')
  const [language, setLanguage] = useState('typescript')
  const [isSaving, setIsSaving] = useState(false)

  useEffect(() => {
    // Fetch file content
    fetch(`http://localhost:8000/api/sessions/${sessionId}/files/${encodeURIComponent(filePath)}`)
      .then(res => res.json())
      .then(data => {
        setContent(data.content)
        setLanguage(detectLanguage(filePath))
      })
  }, [sessionId, filePath])

  const handleSave = async () => {
    setIsSaving(true)

    await fetch(`http://localhost:8000/api/sessions/${sessionId}/files/${encodeURIComponent(filePath)}`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${localStorage.getItem('token')}`
      },
      body: JSON.stringify({ content })
    })

    setIsSaving(false)
  }

  return (
    <div className="h-full flex flex-col">
      <div className="border-b p-2 flex items-center justify-between">
        <span className="text-sm font-mono">{filePath}</span>
        <button
          onClick={handleSave}
          disabled={isSaving}
          className="px-3 py-1 text-sm bg-blue-500 text-white rounded hover:bg-blue-600 disabled:opacity-50"
        >
          {isSaving ? 'Saving...' : 'Save'}
        </button>
      </div>

      <Editor
        height="100%"
        language={language}
        value={content}
        onChange={(value) => setContent(value || '')}
        theme="vs-dark"
        options={{
          minimap: { enabled: false },
          fontSize: 14,
          lineNumbers: 'on',
          scrollBeyondLastLine: false,
          automaticLayout: true,
        }}
      />
    </div>
  )
}

function detectLanguage(filePath: string): string {
  const ext = filePath.split('.').pop()
  const langMap: Record<string, string> = {
    'ts': 'typescript',
    'tsx': 'typescript',
    'js': 'javascript',
    'jsx': 'javascript',
    'py': 'python',
    'json': 'json',
    'md': 'markdown',
    'css': 'css',
    'html': 'html',
    'yaml': 'yaml',
    'yml': 'yaml',
  }
  return langMap[ext || ''] || 'plaintext'
}
```

---

#### Week 9: Deployment + Production Hardening

**Goal**: Deploy to production, add monitoring

**Tasks**:
1. Create Docker containers
2. Set up PostgreSQL + Redis
3. Configure Nginx reverse proxy
4. Add logging and monitoring
5. Deploy to cloud (Vercel for frontend, Railway for backend)

**Deliverables**:

```dockerfile
# Dockerfile (backend)

FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy code
COPY src/ ./src/
COPY pyproject.toml .

# Install package
RUN pip install -e .

# Expose port
EXPOSE 8000

# Run server
CMD ["uvicorn", "compymac.web.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

```dockerfile
# Dockerfile (frontend)

FROM node:20-alpine AS builder

WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY . .
RUN npm run build

FROM node:20-alpine AS runner

WORKDIR /app

COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public

EXPOSE 3000

CMD ["node", "server.js"]
```

```yaml
# docker-compose.yml

version: '3.8'

services:
  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: compymac
      POSTGRES_USER: compymac
      POSTGRES_PASSWORD: changeme
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

  backend:
    build:
      context: .
      dockerfile: Dockerfile
    environment:
      DATABASE_URL: postgresql://compymac:changeme@postgres/compymac
      REDIS_URL: redis://redis:6379
      SECRET_KEY: ${SECRET_KEY}
    ports:
      - "8000:8000"
    depends_on:
      - postgres
      - redis
    volumes:
      - ./workspaces:/workspaces

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    ports:
      - "3000:3000"
    environment:
      NEXT_PUBLIC_API_URL: http://localhost:8000
    depends_on:
      - backend

volumes:
  postgres_data:
```

```nginx
# nginx.conf

upstream backend {
    server backend:8000;
}

upstream frontend {
    server frontend:3000;
}

server {
    listen 80;
    server_name compymac.example.com;

    # Frontend
    location / {
        proxy_pass http://frontend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # Backend API
    location /api/ {
        proxy_pass http://backend/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # WebSocket
    location /ws/ {
        proxy_pass http://backend/ws/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
    }
}
```

```bash
# Deploy script

#!/bin/bash

# Build and push Docker images
docker build -t compymac-backend:latest .
docker build -t compymac-frontend:latest ./frontend

# Deploy to Railway (or your platform)
railway up

# Run migrations
railway run alembic upgrade head

# Restart services
railway restart
```

---

### Phase 4: Polish + Testing (Weeks 10-12)

#### Week 10: UI Polish + Responsive Design

**Tasks**:
- Mobile-friendly layouts
- Dark mode support
- Keyboard shortcuts
- Accessibility (ARIA labels, screen reader support)
- Loading states and error handling

#### Week 11: Performance Optimization

**Tasks**:
- Code splitting (Next.js dynamic imports)
- WebSocket reconnection logic
- Frontend caching (React Query)
- Backend caching (Redis)
- Database query optimization

#### Week 12: Documentation + Launch

**Tasks**:
- User documentation
- API documentation (OpenAPI/Swagger)
- Deployment guide
- Video tutorials
- Beta launch to early users

---

## Success Metrics

### Performance Targets

| Metric | Target |
|--------|--------|
| Initial page load | <2s |
| WebSocket connection time | <500ms |
| Message latency (first token) | <1s |
| Streaming latency (token-by-token) | <50ms |
| File tree load | <1s for 1000 files |
| Database query time | <100ms (95th percentile) |

### User Experience Targets

| Metric | Target |
|--------|--------|
| Uptime | 99.9% |
| Session persistence | 100% (no data loss) |
| Mobile usability score | >90 (Lighthouse) |
| Accessibility score | >95 (Lighthouse) |
| User satisfaction | >4.5/5 |

---

## References

- [How to Build AI-Powered React Apps in 2025 (DEV Community)](https://dev.to/hashan2kk2/how-to-build-ai-powered-react-apps-in-2025-1pcf)
- [Building Modern Web Applications: Node.js Best Practices for 2026](https://www.technology.org/2025/12/22/building-modern-web-applications-node-js-innovations-and-best-practices-for-2026/)
- [AI SDK and React/Next.js (Medium)](https://medium.com/@johngoyason/ai-sdk-and-react-next-js-unlocking-a-new-era-of-interactive-ai-agents-f860326c7e35)
- [Frontend AI Integration in 2025 (Medium)](https://medium.com/@gopesh.jangid/frontend-ai-integration-in-2025-part-i-react-next-js-data-flows-context-streaming-7e9387ca8ced)
- [Building a Real-Time Chat App with Sockets in Next.js (DEV Community)](https://dev.to/hamzakhan/building-a-real-time-chat-app-with-sockets-in-nextjs-1po9)
- [Adding AI Chat Features to Next.js (GetStream)](https://getstream.io/blog/ai-chat-nextjs/)

---

## Next Steps

1. **Week 1**: Start backend implementation (FastAPI + WebSocket)
2. **Week 4**: Start frontend implementation (Next.js + basic chat)
3. **Week 7**: Add authentication and security
4. **Week 10**: Polish and optimize
5. **Week 12**: Deploy and launch beta

**Final deliverable**: Production-ready web interface for CompyMac with modern UI, real-time streaming, and multi-user support.
