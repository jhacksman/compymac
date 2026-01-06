# Session Permalinks Research and Implementation Plan

## Overview

This document covers the implementation of **session permalinks** (also called **deep links**) for CompyMac, enabling shareable URLs like `https://compymac.example.com/chat/77e5ffb7-b332-451f-8d15-2664623419d1`.

## Terminology

The URL pattern `example.com/chat/{uuid}` is commonly called:

1. **Permalink** (permanent link) - A URL that remains valid indefinitely and points to a specific resource
2. **Deep link** - A URL that links directly to specific content within an app rather than the homepage
3. **Canonical URL** - The authoritative URL for a resource
4. **Resource URL** / **Entity URL** - A URL that identifies a specific entity (session, chat, document)

The UUID portion (`77e5ffb7-b332-451f-8d15-2664623419d1`) is typically a **v4 UUID** (random) or **v7 UUID** (time-ordered, newer standard).

## Industry Patterns

### Slack
- Channel: `https://slack.com/app_redirect?channel=C123ABC456`
- Message permalink: `https://workspace.slack.com/archives/C123ABC456/p1234567890123456`
- API: `chat.getPermalink` method returns friendly HTTP permalink for any message

### Chatwoot
- Conversation: `https://app.chatwoot.com/app/accounts/{account_id}/conversations/{conversation_id}`
- Deep linking implemented for mobile apps using URL schemes and intent filters

### ChatGPT / Claude
- Conversation: `https://chat.openai.com/c/{conversation_id}`
- Share link: `https://chat.openai.com/share/{share_id}`

### Devin
- Session: `https://app.devin.ai/sessions/{session_id}`

### Common Pattern
```
https://{domain}/{resource_type}/{resource_id}
```

Where:
- `resource_type` = `chat`, `c`, `session`, `conversation`, etc.
- `resource_id` = UUID v4 (most common), nanoid, or custom ID

## Current CompyMac State

### Frontend Structure
```
web/src/app/
├── page.tsx          # Main page (creates session on mount)
├── layout.tsx
├── globals.css
└── favicon.ico
```

### Current Session Flow
1. User visits `/` (root)
2. `page.tsx` creates a new session via `POST /sessions`
3. Session ID stored in local state and Zustand store
4. No URL-based session routing exists

### Session Store
- `currentSessionId: string | null` - Current active session
- `sessions: Session[]` - List of all sessions
- `fetchSessions()` - Load sessions from API
- `resumeSession(sessionId)` - Resume a paused session

## Implementation Plan

### Phase 1: Next.js Dynamic Routes (Frontend)

Create a dynamic route for sessions:

```
web/src/app/
├── page.tsx                    # Landing page (session list or redirect)
├── chat/
│   └── [sessionId]/
│       └── page.tsx            # Session view page
└── layout.tsx
```

**New file: `web/src/app/chat/[sessionId]/page.tsx`**
```typescript
'use client'

import { useEffect } from 'react'
import { useParams, useRouter } from 'next/navigation'
import { useSessionStore } from '@/store/session'
// ... existing imports from page.tsx

export default function SessionPage() {
  const params = useParams()
  const router = useRouter()
  const sessionId = params.sessionId as string
  
  const { setCurrentSession, fetchSessions, sessions } = useSessionStore()
  
  useEffect(() => {
    // Validate UUID format
    const uuidRegex = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i
    if (!uuidRegex.test(sessionId)) {
      router.push('/') // Invalid ID, redirect to home
      return
    }
    
    // Set the session ID and load session data
    setCurrentSession(sessionId)
    fetchSessions()
  }, [sessionId, setCurrentSession, fetchSessions, router])
  
  // ... rest of the component (same as current page.tsx)
}
```

**Update: `web/src/app/page.tsx`**
```typescript
'use client'

import { useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { useSessionStore } from '@/store/session'

export default function Home() {
  const router = useRouter()
  const { sessions, fetchSessions, isLoadingSessions } = useSessionStore()
  
  useEffect(() => {
    fetchSessions()
  }, [fetchSessions])
  
  // Option A: Auto-create new session and redirect
  useEffect(() => {
    const createAndRedirect = async () => {
      const response = await fetch('http://localhost:8000/sessions', { method: 'POST' })
      const data = await response.json()
      router.push(`/chat/${data.id}`)
    }
    createAndRedirect()
  }, [router])
  
  // Option B: Show session list (better for returning users)
  // return <SessionListPage />
  
  return <div>Loading...</div>
}
```

### Phase 2: URL Synchronization

Keep URL in sync with session state:

```typescript
// In session store or a custom hook
const syncUrlWithSession = (sessionId: string | null) => {
  if (sessionId && window.location.pathname !== `/chat/${sessionId}`) {
    window.history.pushState({}, '', `/chat/${sessionId}`)
  }
}
```

### Phase 3: Backend Support

The backend already has session persistence. Ensure these endpoints work correctly:

- `GET /api/sessions/{session_id}` - Get session details
- `POST /api/sessions/{session_id}/resume` - Resume a session
- `GET /api/sessions` - List all sessions

Add a new endpoint for session validation:
```python
@app.get("/api/sessions/{session_id}/exists")
async def session_exists(session_id: str) -> dict:
    """Check if a session exists (for URL validation)"""
    return {"exists": session_id in sessions}
```

### Phase 4: Share Links (Optional)

For public sharing (like ChatGPT's share feature):

1. Create a separate `share_id` that maps to `session_id`
2. Share links are read-only views
3. URL pattern: `/share/{share_id}`

### Phase 5: Mobile Deep Linking (Future)

For mobile apps, implement:
- iOS: Universal Links (`apple-app-site-association`)
- Android: App Links (`assetlinks.json`)

## File Changes Summary

| File | Change |
|------|--------|
| `web/src/app/chat/[sessionId]/page.tsx` | NEW - Dynamic session page |
| `web/src/app/page.tsx` | MODIFY - Landing/redirect logic |
| `web/src/store/session.ts` | MODIFY - Add URL sync helper |
| `web/src/components/layout/HistorySidebar.tsx` | MODIFY - Use Link for session navigation |

## Implementation Effort

| Phase | Effort | Priority |
|-------|--------|----------|
| Phase 1: Dynamic Routes | 2-3 hours | High |
| Phase 2: URL Sync | 1 hour | High |
| Phase 3: Backend Validation | 30 min | Medium |
| Phase 4: Share Links | 4-6 hours | Low |
| Phase 5: Mobile Deep Links | 8+ hours | Future |

## Recommended Approach

Start with **Phase 1 + Phase 2** for immediate value:

1. Create `web/src/app/chat/[sessionId]/page.tsx`
2. Move existing page logic to the new dynamic route
3. Update root page to create session and redirect
4. Update HistorySidebar to use `<Link href="/chat/{id}">` for navigation
5. Test URL-based session loading

This gives you shareable session URLs like:
```
https://compymac.example.com/chat/77e5ffb7-b332-451f-8d15-2664623419d1
```

## Security Considerations

1. **Session ownership** - Ensure users can only access their own sessions
2. **UUID guessing** - v4 UUIDs are cryptographically random (122 bits of entropy), making guessing infeasible
3. **Rate limiting** - Prevent enumeration attacks on session endpoints
4. **Share vs. Private** - If implementing share links, use separate IDs and explicit sharing consent
