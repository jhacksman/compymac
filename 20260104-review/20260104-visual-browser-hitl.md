# Visual Browser Feedback with Human-in-the-Loop: Research and Implementation

## Executive Summary

This document provides research findings and an implementation plan for adding visual browser feedback with human-in-the-loop (HITL) capabilities to CompyMac. The goal is to enable users to see browser activity in real-time and intervene when needed (e.g., solving CAPTCHAs, handling authentication).

## Part 1: Research Findings

### 1.1 Industry Approaches

#### Manus Browser Operator (November 2025)

Manus launched "Browser Operator" - a Chrome/Edge extension that runs in the user's LOCAL browser rather than a remote headless instance.

Key features:
- Uses user's real IP, cookies, and login state
- Bypasses CAPTCHAs, login expiration, IP bans automatically
- "Local-first" approach - AI operates in user's actual browser
- User sees everything and can intervene instantly

Source: news.aibase.com, November 2025

#### Devin (Cognition AI)

Devin provides a remote browser with streaming visuals and user interrupt/takeover capabilities.

Key features:
- Browser runs in cloud but streams to user
- User can see what Devin is doing in real-time
- Interrupt and takeover at any point
- "Keeping humans in the loop with progress updates and review points"

Source: devin.ai documentation, realpython.com

#### Browser-Use (Open Source, 74.6k GitHub stars)

Browser-Use is the leading open-source browser automation library for AI agents. It powers Manus and many other agents.

Key features:
- Playwright-based browser automation
- Cloud API with pause/resume endpoints
- Screenshot capture and streaming
- Docker support with VNC for visual access

API endpoints (from docs.browser-use.com):
- `PUT /pause-task` - Pause agent execution
- `PUT /resume-task` - Resume agent execution
- `GET /get-task-screenshots` - Get screenshots from task
- `GET /get-task-media` - Get media from task

Source: github.com/browser-use/browser-use, docs.browser-use.com

### 1.2 Academic Research

#### Human-GUI Agent Collaboration (arXiv:2505.09875)

"Characterizing Unintended Consequences in Human-GUI Agent Collaboration for Web Browsing" (Zhang et al., Tsinghua/Cornell, 2025)

Key findings from social media analysis (N=221 posts) and interviews (N=14):
- Agents have deficiencies in comprehending instructions and planning tasks
- Challenges in executing accurate GUI interactions and adapting to dynamic interfaces
- Generation of unreliable or misaligned outputs
- Shortcomings in error handling and feedback processing

Implications:
- Without visibility, humans cannot detect agent missteps or assist at the right time
- Increases user frustration and failure rates
- Clear feedback and well-designed handoff is central to success

#### CAPTCHA Benchmarking (arXiv:2505.24878)

"Open CaptchaWorld: A Comprehensive Web-based Platform for Testing and Benchmarking Multimodal LLM Agents" (Luo et al., 2025)

Key findings:
- Agent stuck on CAPTCHA is a routine failure mode, not an edge case
- Systems that expect reliability must build explicit escalation-to-human loops
- MLLMs can solve some CAPTCHAs but struggle with complex reasoning types

#### CAPTCHA Defense Research (arXiv:2512.02318)

"COGNITION: From Evaluation to Defense against Multimodal LLM CAPTCHA Solvers" (Wang et al., 2025)

Key findings:
- MLLMs can reliably solve recognition-oriented and low-interaction CAPTCHA tasks
- Tasks requiring fine-grained localization, multi-step spatial reasoning, or cross-frame consistency remain significantly harder
- Platforms should expect agents to fail on complex CAPTCHAs and design for human handoff

### 1.3 Technical Architecture Patterns

#### Pattern 1: VNC + noVNC (Browser-Use MCP Server)

From github.com/co-browser/browser-use-mcp-server:

Architecture:
```
Docker Container
├── Xvfb (X Virtual Framebuffer) - virtual display
├── Openbox (window manager)
├── Chromium (browser)
├── Playwright/Puppeteer (automation)
├── x11vnc (captures display, streams over network)
└── noVNC (HTML5 client for browser viewing)
```

Benefits:
- User can view browser in any web browser via noVNC
- Full interaction capability (click, type, scroll)
- Works with any browser automation library
- Containerized and portable

#### Pattern 2: Screenshot Polling

Simple approach used by many agents:
```
while task_running:
    screenshot = browser.screenshot()
    send_to_ui(screenshot)
    sleep(interval)
```

Benefits:
- Simple to implement
- Low bandwidth
- Works with headless browsers

Drawbacks:
- Not real-time
- No interaction capability
- Latency in feedback

#### Pattern 3: CDP (Chrome DevTools Protocol) Streaming

Used by some advanced implementations:
```
cdp_session.send("Page.startScreencast", {
    format: "jpeg",
    quality: 80,
    everyNthFrame: 1
})
```

Benefits:
- Real-time frame streaming
- Lower latency than polling
- Native Chrome support

#### Pattern 4: WebRTC Streaming

Most advanced approach for real-time streaming:
```
Browser → WebRTC → User's Browser
```

Benefits:
- Lowest latency
- Bi-directional communication
- Industry standard for real-time video

Drawbacks:
- Complex to implement
- Requires STUN/TURN servers for NAT traversal

### 1.4 LangGraph Human-in-the-Loop

LangGraph (LangChain) provides first-class support for human-in-the-loop workflows.

Key concepts:
- **Persistence**: Every step reads from and writes to a checkpoint
- **Interrupt**: `interrupt()` function pauses execution and waits for human input
- **Resume**: Human provides input, execution continues from checkpoint

Example pattern:
```python
from langgraph.types import interrupt

def browser_step(state):
    # Check if human intervention needed
    if needs_captcha_help(state):
        human_input = interrupt("Please solve the CAPTCHA")
        return {"captcha_solution": human_input}
    return state
```

Source: langchain-ai.github.io/langgraph

---

## Part 2: CompyMac Current State

### 2.1 Existing Browser Module

CompyMac has a full Playwright-based browser automation module at `src/compymac/browser.py` (1100+ lines).

Current capabilities:
- Element ID injection (`data-compyid`, like Devin's `devinid`)
- Navigate, click, type, scroll, screenshot, JS execution
- DOM extraction for LLM context
- Headless and headful mode support
- Screenshot capture to `/tmp/browser_screenshots`

Key classes:
- `BrowserService` - Main async browser automation
- `SyncBrowserService` - Synchronous wrapper
- `BrowserConfig` - Configuration including mode (headless/headful)
- `PageState` - Current page state with elements
- `BrowserAction` - Result of browser actions

### 2.2 Current Gaps

1. **No visual streaming**: Browser runs headless by default, no frames sent to UI
2. **No pause/resume**: No mechanism to pause agent and let human intervene
3. **No takeover**: User cannot take control of browser mid-task
4. **No CAPTCHA escalation**: No automatic detection and escalation for CAPTCHAs
5. **UI panel disconnected**: Browser panel in UI is not wired to BrowserService

---

## Part 3: Implementation Plan

### Phase 1: Visual Feedback (Screenshot Streaming)

**Goal**: Stream browser screenshots to UI in near-real-time

**Approach**: Screenshot polling with WebSocket delivery

**Implementation**:

1. Add screenshot streaming to BrowserService:
```python
# In browser.py
async def start_streaming(self, interval_ms: int = 500) -> None:
    """Start streaming screenshots at specified interval."""
    self._streaming = True
    while self._streaming and self._page:
        screenshot = await self._page.screenshot(type="jpeg", quality=70)
        await self._on_screenshot(screenshot)
        await asyncio.sleep(interval_ms / 1000)

async def stop_streaming(self) -> None:
    """Stop screenshot streaming."""
    self._streaming = False
```

2. Add WebSocket endpoint for streaming:
```python
# In api/server.py
@app.websocket("/ws/browser/{session_id}")
async def browser_stream(websocket: WebSocket, session_id: str):
    await websocket.accept()
    browser = get_browser_for_session(session_id)
    
    async def on_screenshot(data: bytes):
        await websocket.send_bytes(data)
    
    browser._on_screenshot = on_screenshot
    await browser.start_streaming()
```

3. UI integration:
```javascript
// Browser panel component
const ws = new WebSocket(`ws://localhost:8000/ws/browser/${sessionId}`);
ws.onmessage = (event) => {
    const blob = new Blob([event.data], { type: 'image/jpeg' });
    browserImage.src = URL.createObjectURL(blob);
};
```

**Estimated effort**: 2-3 days

### Phase 2: Pause/Resume

**Goal**: Allow pausing agent execution for human intervention

**Approach**: Event-based pause mechanism inspired by browser-use

**Implementation**:

1. Add pause state to AgentLoop:
```python
# In agent_loop.py
class AgentState:
    # ... existing fields ...
    paused: bool = False
    pause_reason: str | None = None
    pause_event: asyncio.Event = field(default_factory=asyncio.Event)

async def pause(self, reason: str = "User requested pause") -> None:
    """Pause agent execution."""
    self.state.paused = True
    self.state.pause_reason = reason
    self.state.pause_event.clear()

async def resume(self) -> None:
    """Resume agent execution."""
    self.state.paused = False
    self.state.pause_reason = None
    self.state.pause_event.set()

async def _check_pause(self) -> None:
    """Check if paused and wait for resume."""
    if self.state.paused:
        await self.state.pause_event.wait()
```

2. Add pause check in run_step:
```python
async def run_step(self) -> tuple[str | None, list[ToolResult]]:
    # Check for pause before each step
    await self._check_pause()
    # ... existing step logic ...
```

3. Add API endpoints:
```python
@app.put("/api/sessions/{session_id}/pause")
async def pause_session(session_id: str, reason: str = "User requested"):
    agent = get_agent_for_session(session_id)
    await agent.pause(reason)
    return {"status": "paused"}

@app.put("/api/sessions/{session_id}/resume")
async def resume_session(session_id: str):
    agent = get_agent_for_session(session_id)
    await agent.resume()
    return {"status": "resumed"}
```

**Estimated effort**: 2-3 days

### Phase 3: Human Takeover

**Goal**: Allow user to take control of browser and perform actions

**Approach**: Headful mode with VNC streaming (like browser-use MCP server)

**Implementation**:

1. Add VNC support via Docker:
```dockerfile
# Dockerfile.browser
FROM mcr.microsoft.com/playwright/python:v1.40.0

# Install VNC
RUN apt-get update && apt-get install -y \
    x11vnc \
    xvfb \
    openbox \
    novnc \
    websockify

# Start script
COPY start-vnc.sh /start-vnc.sh
RUN chmod +x /start-vnc.sh

EXPOSE 5900 6080
CMD ["/start-vnc.sh"]
```

2. Start script:
```bash
#!/bin/bash
# start-vnc.sh
Xvfb :99 -screen 0 1280x720x24 &
export DISPLAY=:99
openbox &
x11vnc -display :99 -forever -shared -rfbport 5900 &
websockify --web /usr/share/novnc 6080 localhost:5900 &
python -m compymac.browser --headful
```

3. Add takeover mode to BrowserService:
```python
async def enable_takeover(self) -> dict:
    """Enable human takeover mode."""
    # Pause automation
    self._takeover_mode = True
    
    # Return VNC connection info
    return {
        "vnc_url": f"http://localhost:6080/vnc.html",
        "status": "takeover_enabled"
    }

async def disable_takeover(self) -> None:
    """Return control to agent."""
    self._takeover_mode = False
```

**Estimated effort**: 3-5 days

### Phase 4: CAPTCHA Detection and Escalation

**Goal**: Automatically detect CAPTCHAs and escalate to human

**Approach**: Visual detection + automatic pause

**Implementation**:

1. Add CAPTCHA detection:
```python
# In browser.py
CAPTCHA_INDICATORS = [
    "captcha",
    "recaptcha",
    "hcaptcha",
    "challenge",
    "verify you are human",
    "i'm not a robot",
]

async def detect_captcha(self) -> bool:
    """Detect if current page has a CAPTCHA."""
    if not self._page:
        return False
    
    # Check page content
    content = await self._page.content()
    content_lower = content.lower()
    
    for indicator in CAPTCHA_INDICATORS:
        if indicator in content_lower:
            return True
    
    # Check for common CAPTCHA iframes
    frames = self._page.frames
    for frame in frames:
        url = frame.url.lower()
        if "recaptcha" in url or "hcaptcha" in url:
            return True
    
    return False
```

2. Add automatic escalation in browser tools:
```python
async def navigate(self, url: str, ...) -> BrowserAction:
    # ... existing navigation logic ...
    
    # Check for CAPTCHA after navigation
    if await self.detect_captcha():
        # Trigger human escalation
        await self._escalate_to_human(
            reason="CAPTCHA detected",
            action_needed="Please solve the CAPTCHA"
        )
    
    return result
```

3. Escalation handler:
```python
async def _escalate_to_human(self, reason: str, action_needed: str) -> None:
    """Escalate to human for intervention."""
    # Enable visual streaming if not already
    if not self._streaming:
        await self.start_streaming()
    
    # Notify UI
    await self._notify_ui({
        "type": "human_intervention_needed",
        "reason": reason,
        "action_needed": action_needed,
        "vnc_url": self._vnc_url if self._vnc_enabled else None,
    })
    
    # Wait for human to complete action
    await self._human_intervention_event.wait()
```

**Estimated effort**: 2-3 days

---

## Part 4: Open Source References

### 4.1 Browser-Use

Repository: https://github.com/browser-use/browser-use (74.6k stars, MIT license)

Key files to study:
- `browser_use/agent/service.py` - Agent service with pause/resume
- `browser_use/browser/browser.py` - Browser automation
- `browser_use/controller/service.py` - Controller with human intervention
- `examples/features/pause_agent.py` - Pause/resume example

### 4.2 Browser-Use MCP Server

Repository: https://github.com/co-browser/browser-use-mcp-server

Key features:
- Dockerized Playwright + Chromium + VNC
- Supports stdio & resumable HTTP
- noVNC for browser viewing

### 4.3 Playwright VNC

Repository: https://github.com/Grommash9/playwright_vnc

Simple example of Playwright with VNC for visual access.

### 4.4 LangGraph

Documentation: https://langchain-ai.github.io/langgraph/agents/human-in-the-loop/

Key concepts:
- `interrupt()` function for pausing
- Persistence for state management
- Checkpointing for resume

---

## Part 5: Implementation Priorities

### Recommended Order

1. **Phase 1: Screenshot Streaming** (Highest priority)
   - Immediate value: users can see what's happening
   - Foundation for other phases
   - Relatively simple to implement

2. **Phase 2: Pause/Resume** (High priority)
   - Enables basic human intervention
   - Required for CAPTCHA handling
   - Builds on Phase 1

3. **Phase 4: CAPTCHA Detection** (Medium priority)
   - Automatic escalation improves UX
   - Reduces failed tasks
   - Requires Phase 2

4. **Phase 3: Human Takeover** (Lower priority)
   - Full VNC is complex
   - May not be needed if pause/resume works well
   - Consider as future enhancement

### Minimum Viable Implementation

For fastest time-to-value, implement:
1. Screenshot streaming via WebSocket
2. Pause/resume API endpoints
3. Basic CAPTCHA detection with manual escalation

This provides the core "see and intervene" capability without the complexity of full VNC takeover.

---

## Part 6: Memory Constraint Consideration

**Note**: There is a constraint conflict in the project documentation:
- User note claims "64GB VRAM limit"
- Jack explicitly corrected to "128GB unified RAM" in PR #228

The browser streaming implementation has minimal memory impact:
- JPEG screenshots: ~50-200KB per frame
- WebSocket buffer: ~1MB
- VNC (if used): ~50-100MB for x11vnc + noVNC

This should not significantly impact the memory budget regardless of which constraint is authoritative.

---

## References

1. Browser-Use GitHub: https://github.com/browser-use/browser-use
2. Browser-Use Docs: https://docs.browser-use.com
3. Browser-Use MCP Server: https://github.com/co-browser/browser-use-mcp-server
4. LangGraph Human-in-the-Loop: https://langchain-ai.github.io/langgraph/agents/human-in-the-loop/
5. arXiv:2505.09875 - Human-GUI Agent Collaboration
6. arXiv:2505.24878 - Open CaptchaWorld
7. arXiv:2512.02318 - COGNITION CAPTCHA Defense
8. Manus Browser Operator: news.aibase.com (November 2025)
9. Devin Documentation: docs.devin.ai
10. Playwright VNC: https://github.com/Grommash9/playwright_vnc
