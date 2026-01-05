# Browser Tab & Web Preview Architecture Research
**Date:** 2026-01-05
**Status:** Research Complete - Ready for Implementation Planning

## Executive Summary

CompyMac currently has:
- ✅ Full browser automation (Playwright-based) with screenshot capture
- ✅ Firecracker-based CLI sandboxing via locale2b
- ✅ Frontend UI with BrowserPanel component
- ❌ **MISSING: Port forwarding from Firecracker VMs to expose web servers**
- ❌ **MISSING: Live web preview (only static screenshots)**
- ❌ **MISSING: Multi-tab browser management**

**The Gap:** You can run `npm start` in the Firecracker VM, but there's no way to access the resulting localhost:3000 server from outside the VM or display it in the browser tab UI.

---

## 1. Current CompyMac Architecture

### What Exists Today

#### locale2b Client (`src/compymac/locale2b.py`)
**Repository:** https://github.com/jhacksman/locale2b (37 commits, MIT license)

**Current API Methods:**
- `create_sandbox()` - Spin up Firecracker microVM
- `destroy_sandbox()` - Tear down VM
- `exec_command()` - Execute commands in sandbox
- `write_file()` / `read_file()` / `list_files()` - File operations
- `pause_sandbox()` / `resume_sandbox()` - Snapshot/restore functionality
- `health_check()` - Service status

**Networking Capabilities (Backend):**
- ✅ vsock communication (host-guest virtio sockets)
- ✅ DHCP-enabled networking for guest VMs
- ✅ Internet access (pip install, git clone, npm install work)
- ✅ Inter-sandbox communication
- ✅ TAP device bridge for network isolation
- ❌ **NO port forwarding/exposure API**
- ❌ **NO public URL generation for services**

#### Browser Service (`src/compymac/browser.py`)
- ✅ Playwright automation (Chromium, Firefox, WebKit)
- ✅ Screenshot capture
- ✅ DOM manipulation with `data-compyid` injection
- ✅ Actions: navigate, click, type, scroll, execute_js
- ✅ Headless and headful modes
- ❌ **NO multi-tab support**
- ❌ **NO pause/resume at browser level**

#### Frontend (`web/src/components/workspace/BrowserPanel.tsx`)
- ✅ Browser UI with URL bar and control toggle (user/agent)
- ✅ Screenshot display from `/screenshots/{filename}`
- ✅ WebSocket integration for browser events
- ✅ State management (Zustand store)
- ❌ **NO live iframe preview**
- ❌ **NO tab bar or tab switching UI**

### The Scenario You're Describing

```
┌─────────────────────────────────────────────────────────┐
│ User Request: "Build a React app and show me preview"  │
└─────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│ Agent Actions (in Firecracker VM via locale2b)         │
│  1. npx create-react-app my-app                         │
│  2. cd my-app && npm start                              │
│     → App runs on localhost:3000 INSIDE the VM         │
└─────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│ ❌ CURRENT PROBLEM:                                     │
│  - No way to access VM's localhost:3000 from outside    │
│  - No public URL to show user                           │
│  - No iframe preview in browser tab                     │
│  - Only option: Take screenshot (not live/interactive)  │
└─────────────────────────────────────────────────────────┘
```

---

## 2. How Devin Solves This

### Port Exposure Tool
Devin provides an **`expose_port` tool** that agents can call:

```python
# Agent calls this inside the sandbox
url = expose_port(3000)
# Returns: "https://abc123.devinapps.com"
```

**Implementation Details:**
- Tunneling service (similar to ngrok) that creates public URLs
- Format: `https://{random-id}.devinapps.com`
- Agent can call this WITHOUT human approval (documented security concern)
- Works from isolated VM environment
- Intended for development testing workflows

**User Experience:**
1. Agent: "I've built the app and it's running"
2. Agent: "You can preview it at https://abc123.devinapps.com"
3. User clicks link → sees live, interactive preview

**Source:** [AI Kill Chain: Devin AI Exposes Ports](https://embracethered.com/blog/posts/2025/devin-ai-kill-chain-exposing-ports/)

---

## 3. How Manus Solves This

### Dual Architecture Approach

**A. Cloud Browser (Primary for web tasks)**
- Browser runs in cloud sandbox
- Agent navigates and tests remotely
- **Live, interactive preview available from the beginning**
- User can "take over" for sensitive operations (logins, payments)
- Integrated with E2B sandbox infrastructure

**B. Browser Operator (Local Chrome/Edge extension)**
- Launched November 2025
- Uses Chrome DevTools Protocol (CDP)
- Creates dedicated tab groups for agent tasks
- User retains full control, can pause/resume
- Secure access to authenticated sessions

### Tab Management
- Opens new tab in dedicated tab group titled with task name
- Agent can work across multiple tabs
- User can switch between cloud browser and local browser

**Key Quote from Manus:**
> "A live, interactive preview of your application is available from the very beginning, allowing you to instantly see the results of your requests. With its integrated browser, Manus can actively test what it builds — launching the application, interacting with it like a real user, detecting issues, and fixing them autonomously."

**Sources:**
- [Manus Browser Operator](https://manus.im/blog/manus-browser-operator)
- [Manus 1.5 Release](https://manus.im/blog/manus-1.5-release)

---

## 4. How ChatGPT Operator Handles Control Handoff

### Pause/Resume Mechanism

**Architecture:**
- **Computer-Using Agent (CUA)** model combines GPT-4o vision + reasoning
- Runs in **Linux VM on Microsoft Azure**
- Virtual browser takes screenshots, clicks, fills forms remotely

**Control Handoff:**
1. **Monitor Model:** Dedicated model watches for suspicious behavior, can pause
2. **Explicit Pauses:** Agent pauses when user intervention needed (login, critical decision)
3. **User Takeover:** User takes over browser, authenticates, hands control back
4. **Agent Resumes:** Continues from where it left off

**Example Flow:**
```
Agent working → Detects login screen → Pause
→ Notify user: "Login required"
→ User takes over browser → Enters credentials
→ User clicks "Give control back to agent"
→ Agent continues task
```

**Safety Features:**
- Multiple safeguards requiring user permission for major actions
- Monitor model can interrupt at any time
- User can take control during sensitive operations

**Sources:**
- [Introducing Operator - OpenAI](https://openai.com/index/introducing-operator/)
- [ChatGPT Agent Mode Guide](https://www.spurnow.com/en/blogs/how-to-use-chatgpt-agent-mode)

---

## 5. How E2B Does Port Forwarding (Best Reference)

E2B is the infrastructure that powers Manus and provides the exact pattern you should follow.

### Port Exposure API

```javascript
// JavaScript SDK
const sandbox = await Sandbox.create()
const host = sandbox.getHost(3000)
const url = `https://${host}`
// Returns: https://3000-{sandbox-id}.{domain}
```

```python
# Python SDK
sandbox = Sandbox()
host = sandbox.get_host(3000)
url = f"https://{host}"
# Returns: https://3000-{sandbox-id}.{domain}
```

### URL Format
- Pattern: `https://{port}-{sandbox-id}.{domain}`
- Example: `https://3000-sb-abc123xyz.e2b.dev`

### Features
- ✅ Public URLs by default
- ✅ Can restrict with authentication (`allowPublicTraffic: false`)
- ✅ Internet access enabled by default
- ✅ Custom host masking with `${PORT}` variable replacement
- ✅ WebSocket support
- ✅ Long-lived URLs (persist with sandbox)

### Architecture
E2B sandboxes have:
- Internet access from inside the VM
- Public-facing URLs for exposed ports
- Automatic URL generation per sandbox
- Domain-based routing to correct sandbox

**Sources:**
- [E2B Internet Access Docs](https://e2b.dev/docs/sandbox/internet-access)
- [E2B GitHub](https://github.com/e2b-dev/E2B)

---

## 6. Firecracker Port Forwarding (Technical Implementation)

### Standard TAP Device Setup

```bash
# 1. Create TAP device for VM networking
sudo ip tuntap add tap0 mode tap
sudo ip addr add 172.16.0.1/30 dev tap0
sudo ip link set tap0 up

# 2. Enable IP forwarding on host
sudo sh -c "echo 1 > /proc/sys/net/ipv4/ip_forward"

# 3. Set up NAT for internet access from VM
sudo iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE
sudo iptables -A FORWARD -m conntrack --ctstate RELATED,ESTABLISHED -j ACCEPT
sudo iptables -A FORWARD -i tap0 -o eth0 -j ACCEPT
```

### Port Forwarding (VM → Host)

```bash
# Forward host port 8080 to VM's 172.16.0.2:8080
sudo iptables -t nat -A PREROUTING -p tcp --dport 8080 \
  -j DNAT --to-destination 172.16.0.2:8080

# For localhost access, also need OUTPUT chain
sudo iptables -t nat -A OUTPUT -p tcp --dport 8080 \
  -j DNAT --to-destination 172.16.0.2:8080
```

### Alternative: vsock (virtio socket)
- Direct host-guest communication without TAP devices
- Requires both host and guest to support vsock API
- Lower latency, simpler setup
- locale2b already uses this for command execution

**Sources:**
- [Firecracker Network Setup](https://github.com/firecracker-microvm/firecracker/blob/main/docs/network-setup.md)
- [Networking for Firecracker Lab](https://blog.0x74686d.com/posts/networking-firecracker-lab/)

---

## 7. Playwright CDP Integration (Browser Control)

### Connecting to External Browser

```python
# Connect to existing Chrome instance via CDP
browser = await playwright.chromium.connect_over_cdp("http://localhost:9222")

# Start Chrome with debugging port
chrome --remote-debugging-port=9222
```

### Pause/Resume Browser Automation

CDP allows:
- Pausing network requests
- Modifying requests/responses
- Full control over browser lifecycle
- Listening to browser events in real-time

### Recent Trend (2025)
Some teams are **switching from Playwright to raw CDP** because:
- 5-10x faster element extraction
- Faster screenshots
- Direct control without abstraction
- Lower memory overhead

**Libraries for raw CDP:**
- **pydoll** (Python)
- **go-rod** (Go)
- **chromedp** (Go)
- **puppeteer** (JavaScript/TypeScript)

**Sources:**
- [Playwright CDPSession Docs](https://playwright.dev/docs/api/class-cdpsession)
- [Closer to the Metal: Playwright to CDP](https://browser-use.com/posts/playwright-to-cdp)

---

## 8. Recommendations for CompyMac

### Phase 1: Port Forwarding (Critical Path)

**Option A: ngrok-style Tunneling** (Fastest to implement)
- Use existing service like ngrok, cloudflared, or bore
- Add `expose_port()` method to locale2b client
- Pros: Quick implementation, works anywhere, no infrastructure
- Cons: External dependency, potential rate limits, security concerns

**Option B: Custom Reverse Proxy** (E2B-style, recommended)
- Set up nginx/caddy on locale2b server
- Route `{port}-{sandbox-id}.yourdomain.com` → VM ports
- Requires wildcard DNS and domain ownership
- Pros: Full control, better security, professional URLs
- Cons: More complex setup, requires infrastructure

**Recommended Implementation for locale2b:**

```python
# Add to src/compymac/locale2b.py

class Locale2bClient:
    async def expose_port(
        self,
        sandbox_id: str,
        port: int,
        public: bool = True
    ) -> dict[str, str]:
        """Expose a port from the sandbox to external access.

        Args:
            sandbox_id: ID of sandbox
            port: Internal port number (e.g., 3000)
            public: Allow public internet access (default True)

        Returns:
            Dict with 'url' key containing public URL
            Example: {'url': 'https://3000-sb-abc123.compymac.dev'}
        """
        payload = {
            "port": port,
            "public": public
        }

        response = self._client.post(
            f"/sandboxes/{sandbox_id}/ports/expose",
            json=payload
        )
        response.raise_for_status()
        return response.json()

    async def list_exposed_ports(self, sandbox_id: str) -> list[dict]:
        """List all exposed ports for a sandbox."""
        response = self._client.get(f"/sandboxes/{sandbox_id}/ports")
        response.raise_for_status()
        return response.json().get("ports", [])

    async def close_port(self, sandbox_id: str, port: int) -> bool:
        """Close an exposed port."""
        response = self._client.delete(
            f"/sandboxes/{sandbox_id}/ports/{port}"
        )
        response.raise_for_status()
        return True
```

**Backend changes needed in locale2b server:**
1. Add port forwarding endpoints to API
2. Implement iptables rules or nginx routing
3. Generate unique URLs per sandbox+port
4. Track exposed ports in sandbox state
5. Clean up port forwards when sandbox destroyed

### Phase 2: Service Auto-Discovery

```python
# Add to src/compymac/browser.py or new service_discovery.py

class ServiceDiscovery:
    """Detect web servers running in sandbox."""

    COMMON_PORTS = [3000, 3001, 4200, 5000, 5173, 8000, 8080, 8081, 8888]

    async def scan_ports(self, locale2b_client, sandbox_id: str) -> list[int]:
        """Scan for open ports in sandbox."""
        open_ports = []
        for port in self.COMMON_PORTS:
            # Use locale2b to check if port is listening
            result = await locale2b_client.exec_command(
                sandbox_id,
                f"timeout 1 bash -c 'cat < /dev/null > /dev/tcp/127.0.0.1/{port}'"
            )
            if result.exit_code == 0:
                open_ports.append(port)
        return open_ports

    async def detect_framework(self, port: int, url: str) -> str:
        """Detect what framework is running based on HTTP headers."""
        # Check for React, Vue, Next.js, Flask, FastAPI, etc.
        # Return framework name
        pass
```

### Phase 3: Multi-Tab Browser Support

**Extend BrowserService:**

```python
# In src/compymac/browser.py

class BrowserService:
    def __init__(self, config: BrowserConfig):
        self.config = config
        self.browser: Browser | None = None
        self.tabs: dict[str, Page] = {}  # tab_id → Page
        self.active_tab_id: str | None = None

    async def create_tab(self, url: str = "about:blank") -> str:
        """Create new tab, return tab ID."""
        tab_id = f"tab-{uuid.uuid4()}"
        page = await self.browser.new_page()
        await page.goto(url)
        self.tabs[tab_id] = page
        self.active_tab_id = tab_id
        return tab_id

    async def switch_tab(self, tab_id: str):
        """Switch to specific tab."""
        if tab_id not in self.tabs:
            raise ValueError(f"Tab {tab_id} not found")
        self.active_tab_id = tab_id

    async def close_tab(self, tab_id: str):
        """Close tab."""
        if tab_id in self.tabs:
            await self.tabs[tab_id].close()
            del self.tabs[tab_id]
            if self.active_tab_id == tab_id:
                self.active_tab_id = next(iter(self.tabs.keys()), None)

    async def get_active_tab(self) -> Page:
        """Get currently active tab."""
        if not self.active_tab_id or self.active_tab_id not in self.tabs:
            # Create default tab if none exist
            await self.create_tab()
        return self.tabs[self.active_tab_id]
```

**Frontend State (extend `web/src/store/session.ts`):**

```typescript
interface BrowserTab {
  id: string
  url: string
  title: string
  screenshotUrl: string | null
  control: 'user' | 'agent'
  isActive: boolean
  serviceInfo?: {
    port: number
    framework: string
    exposedUrl: string
  }
}

interface SessionState {
  // ... existing state
  browserTabs: BrowserTab[]
  activeBrowserTabId: string | null

  // Actions
  createBrowserTab: (url?: string) => void
  closeBrowserTab: (tabId: string) => void
  switchBrowserTab: (tabId: string) => void
}
```

**Frontend UI (extend `BrowserPanel.tsx`):**

```tsx
// Add tab bar
<div className="tab-bar">
  {browserTabs.map(tab => (
    <div
      key={tab.id}
      className={tab.isActive ? 'tab active' : 'tab'}
      onClick={() => switchBrowserTab(tab.id)}
    >
      <span className="tab-title">{tab.title || 'New Tab'}</span>
      <button onClick={(e) => {
        e.stopPropagation()
        closeBrowserTab(tab.id)
      }}>×</button>
    </div>
  ))}
  <button onClick={createBrowserTab}>+ New Tab</button>
</div>
```

### Phase 4: Live Preview (iframe-based)

Replace screenshot-based preview with live iframe:

```tsx
// In BrowserPanel.tsx

const PreviewContent = ({ tab }: { tab: BrowserTab }) => {
  const [mode, setMode] = useState<'live' | 'screenshot'>('live')

  if (mode === 'live' && tab.serviceInfo?.exposedUrl) {
    return (
      <iframe
        src={tab.serviceInfo.exposedUrl}
        className="browser-preview-iframe"
        sandbox="allow-scripts allow-same-origin allow-forms"
      />
    )
  }

  return (
    <img
      src={tab.screenshotUrl || '/placeholder.png'}
      alt="Browser screenshot"
    />
  )
}
```

**When to use iframe vs screenshot:**
- **iframe**: For exposed services (localhost apps you're building)
- **screenshot**: For external websites (google.com, github.com, etc.)

### Phase 5: Control Handoff (Pause/Resume)

**Backend additions:**

```python
# In src/compymac/browser.py

class BrowserService:
    async def pause(self, tab_id: str, reason: str):
        """Pause automation, hand control to user."""
        await self.emit_event('browser_paused', {
            'tab_id': tab_id,
            'reason': reason  # 'login_required', 'user_decision_needed'
        })
        # Optionally: switch to headful mode for user interaction

    async def resume(self, tab_id: str):
        """Resume automation after user handoff."""
        await self.emit_event('browser_resumed', {'tab_id': tab_id})
        # Switch back to headless mode
```

**Frontend UI:**

```tsx
// Control toggle in BrowserPanel
<div className="control-toggle">
  {browserControl === 'user' ? (
    <>
      <span className="badge">You're in control</span>
      <button onClick={() => handControlToAgent(activeTabId)}>
        Give Control to Agent
      </button>
    </>
  ) : (
    <>
      <span className="badge agent">Agent is working</span>
      <button onClick={() => takeControl(activeTabId)}>
        Take Control
      </button>
    </>
  )}
</div>
```

---

## 9. Implementation Roadmap

### Week 1-2: Port Forwarding Foundation
**Priority: CRITICAL** (blocks all other features)

1. **Research locale2b backend implementation**
   - Check if jhacksman/locale2b server already has port forwarding
   - If not, plan backend API additions

2. **Choose implementation strategy**
   - Option A: Quick win with ngrok/cloudflared
   - Option B: Production-ready with custom reverse proxy

3. **Extend locale2b client**
   - Add `expose_port()`, `list_exposed_ports()`, `close_port()` methods
   - Add tests

4. **Validation test**
   - Create sandbox
   - Run `python -m http.server 8000` in sandbox
   - Call `expose_port(8000)`
   - Access via returned URL from browser

### Week 3-4: Service Discovery & Auto-Preview
**Priority: HIGH** (improves UX significantly)

1. **Implement ServiceDiscovery class**
   - Port scanning (common ports: 3000, 5000, 8000, etc.)
   - Framework detection (React, Vue, Flask, FastAPI)

2. **Auto-expose on detection**
   - When agent runs `npm start`, auto-detect port 3000 opening
   - Auto-call `expose_port(3000)`
   - Notify user with URL

3. **Add "Open Preview" button in UI**
   - Show exposed services in sidebar
   - One-click to open preview in browser tab

### Week 5-6: Multi-Tab Management
**Priority: MEDIUM** (nice-to-have, not blocking)

1. **Backend: Extend BrowserService**
   - Tab creation, switching, closing
   - Tab state tracking

2. **Frontend: Tab UI**
   - Tab bar component
   - Active tab highlighting
   - Close buttons

3. **WebSocket: Tab events**
   - `tab_created`, `tab_closed`, `tab_switched`
   - Sync tab state across UI

### Week 7-8: Live Preview
**Priority: MEDIUM** (better than screenshots, but screenshots work)

1. **iframe integration**
   - Replace screenshot display with iframe option
   - Toggle between live/screenshot modes

2. **Security considerations**
   - iframe sandbox attributes
   - CSP headers
   - CORS handling

3. **Hot reload support**
   - WebSocket for live updates
   - Refresh iframe on file changes

### Week 9-10: Control Handoff
**Priority: LOW** (polish feature)

1. **Pause detection logic**
   - Detect login screens (look for password fields)
   - Detect payment forms
   - Detect CAPTCHA

2. **UI for handoff**
   - Pause notification
   - Control toggle button
   - Resume button

3. **State preservation**
   - Maintain browser state during handoff
   - Sync cookies/localStorage

---

## 10. Open Questions for Next Steps

### For You to Decide:

1. **Do you control the locale2b backend server?**
   - If yes → Can add port forwarding endpoints directly
   - If no → Need to work around or fork

2. **Do you have a domain for public URLs?**
   - If yes → Can do E2B-style `{port}-{sandbox-id}.yourdomain.com`
   - If no → Need to use ngrok/cloudflared

3. **Priority order?**
   - Quick MVP with ngrok first, then migrate to custom?
   - Or build custom infrastructure from the start?

4. **Where does compymac run?**
   - Local machine → simpler networking
   - Cloud server → need public IPs and DNS
   - Container → need to configure network modes

### Technical Investigations Needed:

1. **Check jhacksman/locale2b server code:**
   - Does it already support port forwarding?
   - What's the networking setup?
   - Can we extend it easily?

2. **Network topology:**
   - Where does locale2b server run?
   - How are Firecracker VMs networked?
   - What IP ranges are used?

3. **Security model:**
   - Should exposed ports require auth?
   - Rate limiting?
   - Automatic cleanup on sandbox destroy?

---

## 11. Quick Win: ngrok Implementation (Deferred Feature)

**Good news:** You already have notes on this in `docs/future-expansion-notes.md`!

The deferred ngrok expose feature is EXACTLY what you need. Here's how to revive it:

```python
# Add to locale2b client as temporary solution

class Locale2bClient:
    async def expose_port_ngrok(
        self,
        sandbox_id: str,
        port: int
    ) -> str:
        """Expose port via ngrok (temporary solution).

        Requires NGROK_AUTHTOKEN in environment.
        """
        # Execute ngrok inside the sandbox
        result = await self.exec_command(
            sandbox_id,
            f"ngrok http {port} --log=stdout",
            timeout_ms=5000
        )

        # Parse ngrok output for public URL
        # Returns something like: https://abc123.ngrok.io
        url = self._parse_ngrok_url(result.stdout)
        return url
```

**Pros:**
- Immediate implementation (1-2 days)
- No infrastructure needed
- Works from anywhere

**Cons:**
- Requires NGROK_AUTHTOKEN
- Free tier limitations (random URLs, connection limits)
- External dependency

**Better Alternative: cloudflared**
- Free forever
- No account required for basic use
- More reliable than ngrok free tier
- `cloudflared tunnel --url localhost:3000`

---

## 12. Key Architectural Insights

### From Manus Blog Post on Context Engineering

These are critical for your agent loop design:

1. **KV-cache optimization matters** (10x cost difference)
   - Keep prompt prefix stable (no timestamps at start)
   - Context is append-only (don't modify previous actions)
   - Tool masking over removal

2. **One sandbox per session** (not per command)
   - Sandbox persists across multiple commands
   - State lives in files, not just memory

3. **Pause/resume for human intervention**
   - Don't block the agent loop
   - Allow async user input when needed

### From E2B Architecture

1. **Firecracker > Docker for sandboxing**
   - Docker: 10-20 seconds spawn time
   - Firecracker: ~150ms spawn time
   - Better security boundary for untrusted code

2. **Port exposure is a first-class feature**
   - Not an afterthought
   - Built into the sandbox API from day one

### From ChatGPT Operator

1. **Monitor model pattern**
   - Separate model watches for issues
   - Can pause main agent at any time
   - Safety layer without blocking functionality

2. **Explicit pause points**
   - Login screens
   - Payment forms
   - Critical decisions

---

## 13. Sources

### Manus
- [Introducing Manus Browser Operator](https://manus.im/blog/manus-browser-operator)
- [Manus Browser Operator Features](https://manus.im/features/manus-browser-operator)
- [Manus 1.5 Release](https://manus.im/blog/manus-1.5-release)
- [Browser Use powering Manus - TechCrunch](https://techcrunch.com/2025/03/12/browser-use-one-of-the-tools-powering-manus-is-also-going-viral/)
- [Manus AI Analytical Guide 2025](https://www.baytechconsulting.com/blog/manus-ai-an-analytical-guide-to-the-autonomous-ai-agent-2025)

### Devin
- [AI Kill Chain: Devin AI Exposes Ports](https://embracethered.com/blog/posts/2025/devin-ai-kill-chain-exposing-ports/)
- [Devin AI Review 2025](https://techpoint.africa/guide/devin-ai-review/)
- [Software Development With Devin - DataCamp](https://www.datacamp.com/tutorial/devin-ai-security-deployment)
- [Introducing Devin - Official Docs](https://docs.devin.ai/get-started/devin-intro)

### ChatGPT Operator
- [Introducing Operator - OpenAI](https://openai.com/index/introducing-operator/)
- [How to Use ChatGPT Agent Mode 2025](https://www.spurnow.com/en/blogs/how-to-use-chatgpt-agent-mode)
- [State of AI Browser Agents 2025](https://fillapp.ai/blog/the-state-of-ai-browser-agents-2025)

### E2B
- [E2B Internet Access Documentation](https://e2b.dev/docs/sandbox/internet-access)
- [E2B GitHub Repository](https://github.com/e2b-dev/E2B)
- [Why Every Agent needs Cloud Sandboxes](https://www.latent.space/p/e2b)
- [New Era of Cloud Agent Infrastructure](https://jimmysong.io/blog/e2b-browserbase-report/)

### Firecracker
- [Firecracker Network Setup](https://github.com/firecracker-microvm/firecracker/blob/main/docs/network-setup.md)
- [Networking for Firecracker Lab](https://blog.0x74696d.com/posts/networking-firecracker-lab/)
- [AWS Firecracker Networking Guide](https://medium.com/@Pawlrus/aws-firecracker-configure-host-guest-networking-b08b90d4f48d)

### Playwright & CDP
- [Playwright CDPSession Documentation](https://playwright.dev/docs/api/class-cdpsession)
- [Closer to the Metal: Playwright to CDP](https://browser-use.com/posts/playwright-to-cdp)
- [Supercharging Playwright with CDP](https://www.thegreenreport.blog/articles/supercharging-playwright-tests-with-chrome-devtools-protocol/supercharging-playwright-tests-with-chrome-devtools-protocol.html)

### Research Papers
- [Agentic Web - arXiv 2507.21206](https://arxiv.org/abs/2507.21206)
- [OpenHands Software Agent SDK - arXiv 2511.03690](https://arxiv.org/html/2511.03690v1)
- [Agent-E: Autonomous Web Navigation - arXiv 2407.13032](https://arxiv.org/html/2407.13032v1)

---

## Next Actions

1. **Decide on port forwarding strategy** (ngrok quick win vs. custom infrastructure)
2. **Check locale2b server capabilities** (clone jhacksman/locale2b and review backend code)
3. **Define your domain setup** (do you have `*.compymac.dev` or similar?)
4. **Prioritize features** (which phases to implement first?)

Once you decide on these, I can help with detailed implementation plans for each phase.
