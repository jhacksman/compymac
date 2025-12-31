# Gap 1: Interactive UI - Design Document

## Executive Summary

This document outlines the design for CompyMac's web-based interactive UI, inspired by Devin, Manus, and OpenAI Operator. The goal is to provide a production-grade control surface where users can monitor agent activity, review changes, approve actions, and take over control when needed.

**Key Design Principles:**
- Chat + Canvas layout (not a full IDE)
- Real-time streaming via WebSockets
- Interactive takeover without VNC/WebRTC (screenshot + action loop)
- Multi-user authentication via OIDC (Google, Apple, Authentik)

---

## 1. Layout Architecture

### 1.1 Three-Column Layout

```
+------------------+------------------------+--------------------------------+
|                  |                        |                                |
|  HISTORY         |  CONVERSATION          |  CANVAS (Tabbed)               |
|  SIDEBAR         |  PANEL                 |                                |
|  (Collapsible)   |                        |  [Browser] [Terminal] [Code]   |
|                  |                        |  [Todo] [Artifacts] [Diff]     |
|  - Session 1     |  User: "Fix the bug"   |                                |
|  - Session 2     |                        |  +---------------------------+ |
|  - Session 3     |  Agent: "I'll analyze  |  |                           | |
|    ...           |  the codebase..."      |  |   Active Tab Content      | |
|                  |                        |  |                           | |
|  [New Session]   |  [Tool Call: grep]     |  |   (Browser screenshot,    | |
|                  |  [Tool Call: edit]     |  |    Terminal output,       | |
|                  |                        |  |    Code diff, etc.)       | |
|                  |  [Verification Gate]   |  |                           | |
|                  |                        |  +---------------------------+ |
|                  |  [Input Box]           |  [Take Control] [Return to AI] |
+------------------+------------------------+--------------------------------+
     ~200px              ~400px                      ~600px (flexible)
```

### 1.2 Panel Descriptions

**History Sidebar (Far Left, Collapsible)**
- List of past sessions with timestamps
- Search/filter sessions
- Session status indicators (running, completed, failed)
- Quick resume functionality
- Collapsible to maximize workspace

**Conversation Panel (Left)**
- Chat-style message thread
- User messages, agent responses
- Inline tool call summaries (expandable)
- Verification checkpoints with approve/reject buttons
- Streaming token display during generation
- Input box with file attachment support

**Canvas Panel (Right, Tabbed)**
- **Browser Tab**: Live browser view with interactive elements
- **Terminal Tab**: xterm.js terminal with command history
- **Code Tab**: File viewer with syntax highlighting and diffs
- **Todo Tab**: Task list with status indicators
- **Artifacts Tab**: Generated files, screenshots, logs
- **Diff Tab**: Git diff viewer for changes

---

## 2. Technology Stack

### 2.1 Frontend

| Component | Technology | Rationale |
|-----------|------------|-----------|
| Framework | Next.js 14+ (App Router) | SSR, API routes, auth integration, deployment flexibility |
| UI Library | React 18+ | Industry standard, large ecosystem |
| Styling | Tailwind CSS + shadcn/ui | Rapid development, consistent design system |
| Panel Layout | `react-resizable-panels` | Production-tested (Replay browser), VSCode-like UX |
| Terminal | `xterm.js` + `react-xtermjs` | Industry standard (VSCode, Hyper) |
| Code Viewer | CodeMirror 6 | Lighter than Monaco, sufficient for viewing/diffs |
| State Management | Zustand | Lightweight, event-driven updates |
| Real-time | Native WebSocket + custom hooks | Direct control, no abstraction overhead |

### 2.2 Backend

| Component | Technology | Rationale |
|-----------|------------|-----------|
| API Server | FastAPI (Python) | Already used in CompyMac, WebSocket support, async |
| WebSocket Server | FastAPI WebSockets | Native support, integrates with agent loop |
| Database | PostgreSQL | Robust, supports JSON, good for event sourcing |
| Cache | Redis (optional) | Session state, pub/sub for multi-instance |
| Auth | Authentik (OIDC) | Centralized auth, supports Google/Apple/custom |

### 2.3 Deployment Architecture

```
                                    +------------------+
                                    |   Authentik      |
                                    |   (OIDC IdP)     |
                                    +--------+---------+
                                             |
                                             | OIDC
                                             v
+------------------+     HTTPS      +------------------+     WebSocket     +------------------+
|                  | <------------> |                  | <---------------> |                  |
|   User Browser   |                |   Next.js App    |                   |   FastAPI        |
|                  |                |   (Frontend)     |                   |   (Agent API)    |
+------------------+                +------------------+                   +------------------+
                                             |                                      |
                                             | HTTP (API)                           |
                                             v                                      v
                                    +------------------+                   +------------------+
                                    |   PostgreSQL     |                   |   CompyMac       |
                                    |   (Sessions,     |                   |   Agent Runtime  |
                                    |    History)      |                   |   (TraceStore)   |
                                    +------------------+                   +------------------+
```

---

## 3. Real-time Event Architecture

### 3.1 Event-Sourced Model

The UI subscribes to an append-only event stream. All state is derived from events.

**Event Types:**
```typescript
type AgentEvent = 
  | { type: 'token_streamed'; content: string }
  | { type: 'message_complete'; message_id: string; role: 'user' | 'assistant' }
  | { type: 'tool_call_started'; tool_name: string; arguments: object }
  | { type: 'tool_call_finished'; tool_name: string; result: string; success: boolean }
  | { type: 'artifact_created'; artifact_id: string; type: string; uri: string }
  | { type: 'verification_requested'; verification_id: string; description: string }
  | { type: 'verification_resolved'; verification_id: string; approved: boolean }
  | { type: 'browser_state_updated'; url: string; title: string; elements: Element[]; screenshot_url: string }
  | { type: 'terminal_output'; content: string; stream: 'stdout' | 'stderr' }
  | { type: 'session_status_changed'; status: 'running' | 'paused' | 'completed' | 'failed' }
  | { type: 'control_transferred'; to: 'user' | 'agent'; surface: 'browser' | 'terminal' }
```

### 3.2 WebSocket Protocol

**Connection:**
```
wss://api.compymac.app/ws/sessions/{session_id}
Authorization: Bearer {jwt_token}
```

**Client -> Server Messages:**
```typescript
type ClientMessage =
  | { type: 'subscribe'; last_event_id?: string }
  | { type: 'send_message'; content: string; attachments?: string[] }
  | { type: 'approve_verification'; verification_id: string }
  | { type: 'reject_verification'; verification_id: string; reason?: string }
  | { type: 'take_control'; surface: 'browser' | 'terminal' }
  | { type: 'return_control'; surface: 'browser' | 'terminal' }
  | { type: 'browser_action'; action: BrowserAction }
  | { type: 'terminal_input'; content: string }
  | { type: 'pause_agent' }
  | { type: 'resume_agent' }
```

**Server -> Client Messages:**
```typescript
type ServerMessage =
  | { type: 'event'; event: AgentEvent; event_id: string; timestamp: string }
  | { type: 'backfill'; events: AgentEvent[] }
  | { type: 'error'; code: string; message: string }
  | { type: 'ack'; message_id: string }
```

### 3.3 Reconnection Strategy

1. On disconnect, client stores `last_event_id`
2. On reconnect, client sends `{ type: 'subscribe', last_event_id }`
3. Server backfills missed events, then switches to live stream
4. If gap too large, client does HTTP catch-up query first

---

## 4. Interactive Takeover

### 4.1 Browser Takeover (Screenshot + Action Loop)

CompyMac's `BrowserService` already supports:
- Element ID injection (`data-compyid`)
- Click by element ID or coordinates
- Type text, scroll, press keys
- Screenshot capture

**Takeover Flow:**
1. User clicks "Take Control" on Browser tab
2. UI sends `{ type: 'take_control', surface: 'browser' }`
3. Agent pauses browser actions, emits `control_transferred` event
4. UI displays interactive screenshot with clickable element overlays
5. User clicks element -> UI sends `{ type: 'browser_action', action: { type: 'click', element_id: 'cid-42' } }`
6. Backend executes via `BrowserService.click(element_id='cid-42')`
7. Backend emits `browser_state_updated` with new screenshot + elements
8. User clicks "Return to AI" -> control returns to agent

**Element Overlay Rendering:**
```typescript
// Render clickable boxes over screenshot based on element bounding boxes
elements.filter(e => e.is_visible).map(element => (
  <div
    key={element.element_id}
    className="absolute border-2 border-blue-500 hover:bg-blue-500/20 cursor-pointer"
    style={{
      left: element.bounding_box.x,
      top: element.bounding_box.y,
      width: element.bounding_box.width,
      height: element.bounding_box.height,
    }}
    onClick={() => sendBrowserAction({ type: 'click', element_id: element.element_id })}
    title={`${element.tag}: ${element.text.slice(0, 50)}`}
  />
))
```

### 4.2 Terminal Takeover

**Phase 1: Command Mode (MVP)**
- User types command in input box
- Command sent to backend via WebSocket
- Backend executes via bash tool
- Output streamed back as `terminal_output` events
- Rendered in xterm.js (read-only display)

**Phase 2: Interactive PTY (Future)**
- Full PTY session bridged to WebSocket
- xterm.js in interactive mode
- Supports arrow keys, tab completion, curses apps
- Requires PTY management on backend

### 4.3 Control Arbitration

When user takes control of a surface:
1. Agent is notified and pauses actions to that surface
2. Agent can continue working on other surfaces
3. UI shows clear indicator of who has control
4. User must explicitly return control to agent
5. Timeout option: auto-return after N seconds of inactivity

---

## 5. Authentication

### 5.1 Authentik as Central IdP

Rather than implementing Google/Apple OAuth directly, use Authentik as the OIDC provider:

```
+------------------+     +------------------+     +------------------+
|   Google OAuth   | --> |                  |     |                  |
+------------------+     |   Authentik      | --> |   CompyMac UI    |
+------------------+     |   (OIDC IdP)     |     |   (Next.js)      |
|   Apple Sign-In  | --> |                  |     |                  |
+------------------+     +------------------+     +------------------+
```

**Benefits:**
- Single OIDC integration in CompyMac
- Add/remove social providers via Authentik admin
- Enterprise SSO (SAML, LDAP) without code changes
- Centralized user management

### 5.2 Auth.js (NextAuth) Configuration

```typescript
// app/api/auth/[...nextauth]/route.ts
import NextAuth from 'next-auth'
import AuthentikProvider from 'next-auth/providers/authentik'

export const authOptions = {
  providers: [
    AuthentikProvider({
      clientId: process.env.AUTHENTIK_CLIENT_ID,
      clientSecret: process.env.AUTHENTIK_CLIENT_SECRET,
      issuer: process.env.AUTHENTIK_ISSUER, // https://auth.compymac.app/application/o/compymac/
    }),
  ],
  callbacks: {
    async jwt({ token, account }) {
      if (account) {
        token.accessToken = account.access_token
      }
      return token
    },
    async session({ session, token }) {
      session.accessToken = token.accessToken
      return session
    },
  },
}

export const handler = NextAuth(authOptions)
export { handler as GET, handler as POST }
```

### 5.3 JWT for WebSocket Auth

1. User authenticates via Authentik -> receives session cookie
2. Frontend requests short-lived JWT from `/api/auth/ws-token`
3. JWT includes user_id, session_id, expiry
4. WebSocket connection includes JWT in query param or first message
5. Backend validates JWT before accepting connection

---

## 6. Database Schema

### 6.1 Core Tables

```sql
-- Users (synced from Authentik)
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255),
    avatar_url TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- OAuth identities (managed by Auth.js)
CREATE TABLE accounts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    provider VARCHAR(50) NOT NULL,
    provider_account_id VARCHAR(255) NOT NULL,
    access_token TEXT,
    refresh_token TEXT,
    expires_at TIMESTAMP,
    UNIQUE(provider, provider_account_id)
);

-- Agent sessions
CREATE TABLE sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    title VARCHAR(255),
    status VARCHAR(20) DEFAULT 'running', -- running, paused, completed, failed
    repo_url TEXT,
    workspace_path TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Chat messages
CREATE TABLE messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID REFERENCES sessions(id) ON DELETE CASCADE,
    role VARCHAR(20) NOT NULL, -- user, assistant, system
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Events (for replay/debugging)
CREATE TABLE events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID REFERENCES sessions(id) ON DELETE CASCADE,
    seq SERIAL,
    type VARCHAR(50) NOT NULL,
    payload JSONB NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX idx_events_session_seq ON events(session_id, seq);

-- Artifacts
CREATE TABLE artifacts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID REFERENCES sessions(id) ON DELETE CASCADE,
    type VARCHAR(50) NOT NULL, -- screenshot, file, diff, log
    uri TEXT NOT NULL,
    metadata JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Verification gates
CREATE TABLE verifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID REFERENCES sessions(id) ON DELETE CASCADE,
    description TEXT NOT NULL,
    status VARCHAR(20) DEFAULT 'pending', -- pending, approved, rejected
    resolved_by UUID REFERENCES users(id),
    resolved_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

-- User preferences
CREATE TABLE user_preferences (
    user_id UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    layout_config JSONB, -- panel widths, collapsed state
    theme VARCHAR(20) DEFAULT 'system',
    notifications_enabled BOOLEAN DEFAULT TRUE
);
```

### 6.2 Integration with TraceStore

CompyMac's existing `TraceStore` handles execution traces. The web UI database stores:
- User-facing data (sessions, messages, preferences)
- Pointers to TraceStore artifacts (via URIs)
- Verification gates and approvals

The two systems are linked by `session_id` which maps to TraceStore's run context.

---

## 7. Component Architecture

### 7.1 Frontend Component Tree

```
App
├── AuthProvider (Auth.js session)
├── WebSocketProvider (connection management)
├── SessionStoreProvider (Zustand)
└── Layout
    ├── HistorySidebar
    │   ├── SessionList
    │   ├── SessionItem
    │   └── NewSessionButton
    ├── ConversationPanel
    │   ├── MessageList
    │   │   ├── UserMessage
    │   │   ├── AssistantMessage
    │   │   ├── ToolCallSummary
    │   │   └── VerificationGate
    │   ├── StreamingIndicator
    │   └── MessageInput
    └── CanvasPanel
        ├── TabBar
        └── TabContent
            ├── BrowserView
            │   ├── Screenshot
            │   ├── ElementOverlays
            │   └── ControlBar
            ├── TerminalView
            │   ├── XTermDisplay
            │   └── CommandInput
            ├── CodeView
            │   ├── FileTree
            │   └── CodeMirrorEditor
            ├── TodoView
            ├── ArtifactsView
            └── DiffView
```

### 7.2 State Management (Zustand)

```typescript
interface SessionState {
  // Session metadata
  sessionId: string | null
  status: 'running' | 'paused' | 'completed' | 'failed'
  
  // Messages
  messages: Message[]
  streamingContent: string
  
  // Browser state
  browserUrl: string
  browserTitle: string
  browserElements: Element[]
  browserScreenshotUrl: string
  browserControl: 'user' | 'agent'
  
  // Terminal state
  terminalOutput: string[]
  terminalControl: 'user' | 'agent'
  
  // Verifications
  pendingVerifications: Verification[]
  
  // Actions
  sendMessage: (content: string) => void
  approveVerification: (id: string) => void
  rejectVerification: (id: string, reason?: string) => void
  takeControl: (surface: 'browser' | 'terminal') => void
  returnControl: (surface: 'browser' | 'terminal') => void
  sendBrowserAction: (action: BrowserAction) => void
  sendTerminalInput: (content: string) => void
}
```

---

## 8. Implementation Phases

### Phase 1: Foundation (2-3 weeks)
- [ ] Next.js project setup with Tailwind + shadcn/ui
- [ ] Auth.js integration with Authentik
- [ ] Basic three-column layout with `react-resizable-panels`
- [ ] PostgreSQL schema and migrations
- [ ] FastAPI WebSocket endpoint (basic events)
- [ ] Session list and creation

### Phase 2: Conversation (1-2 weeks)
- [ ] Message display with streaming
- [ ] Tool call summaries (expandable)
- [ ] Verification gates with approve/reject
- [ ] Message input with send functionality
- [ ] Event backfill on reconnect

### Phase 3: Browser Canvas (2 weeks)
- [ ] Screenshot display with auto-refresh
- [ ] Element overlay rendering
- [ ] Click/type/scroll actions
- [ ] Take control / return control flow
- [ ] URL bar and navigation

### Phase 4: Terminal Canvas (1 week)
- [ ] xterm.js integration
- [ ] Command mode (MVP)
- [ ] Output streaming
- [ ] Take control flow

### Phase 5: Additional Tabs (1-2 weeks)
- [ ] Code viewer with syntax highlighting
- [ ] Todo list display
- [ ] Artifacts browser
- [ ] Diff viewer

### Phase 6: Polish (1 week)
- [ ] Layout persistence
- [ ] Dark/light theme
- [ ] Keyboard shortcuts
- [ ] Mobile responsiveness (basic)
- [ ] Error handling and reconnection UX

---

## 9. API Endpoints

### 9.1 REST API (Next.js API Routes)

```
GET    /api/sessions              - List user's sessions
POST   /api/sessions              - Create new session
GET    /api/sessions/:id          - Get session details
DELETE /api/sessions/:id          - Delete session
GET    /api/sessions/:id/messages - Get message history
GET    /api/sessions/:id/artifacts - Get artifacts list
GET    /api/auth/ws-token         - Get JWT for WebSocket auth
```

### 9.2 WebSocket API (FastAPI)

```
WS /ws/sessions/:id - Real-time event stream and commands
```

---

## 10. Security Considerations

### 10.1 Authentication
- All API routes require valid session
- WebSocket requires valid JWT (short-lived, ~5 min)
- JWT refresh handled automatically

### 10.2 Authorization
- Users can only access their own sessions
- Session sharing (future): explicit invite model

### 10.3 Input Validation
- All WebSocket messages validated against schema
- Browser actions sanitized (no arbitrary JS execution from UI)
- Terminal commands logged for audit

### 10.4 Rate Limiting
- WebSocket message rate limiting
- API endpoint rate limiting
- Browser action throttling (prevent click spam)

---

## 11. Open Questions

1. **Local vs Hosted**: Is this UI for local CompyMac (localhost agent) or hosted multi-tenant SaaS?
   - Affects: Auth complexity, WebSocket scaling, artifact storage

2. **Artifact Storage**: How are artifacts (screenshots, files) stored and served?
   - Options: Local filesystem, S3/R2, database BLOBs

3. **Multi-session**: Can users run multiple sessions simultaneously?
   - Affects: Resource allocation, UI complexity

4. **Collaboration**: Should multiple users be able to view/control the same session?
   - Future feature, but affects schema design now

---

## 12. References

- [react-resizable-panels](https://react-resizable-panels.vercel.app/) - Panel layout library
- [xterm.js](https://xtermjs.org/) - Terminal emulator
- [Auth.js](https://authjs.dev/) - Authentication library
- [Authentik](https://goauthentik.io/) - Identity provider
- [Devin IDE Docs](https://docs.devin.ai/work-with-devin/devin-ide) - Reference implementation
- [Liveblocks AI Copilots](https://liveblocks.io/blog/why-we-built-our-ai-agents-on-websockets-instead-of-http) - WebSocket architecture
