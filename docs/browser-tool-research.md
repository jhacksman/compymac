# Browser Automation Research for CompyMac Agent Harness

This document summarizes research on browser automation approaches for AI agents, comparing different solutions and recommending a hybrid approach for CompyMac.

## Executive Summary

After researching Devin, Manus, browser-use, ElizaOS, OpenAI Operator, and Claude Computer Use, we recommend a **hybrid approach** that combines:

1. **Playwright** as the browser automation engine (headless mode for our use case)
2. **browser-use** patterns for AI-agent-friendly abstractions
3. **Structured element identification** (similar to Devin's `devinid` approach)
4. **Visual + DOM feedback** for robust page understanding

## Approaches Compared

### 1. Devin (Cognition AI)

**Architecture:**
- Playwright-based browser automation
- Injects `devinid` attributes into HTML elements for reliable targeting
- Returns both **screenshot AND HTML** after each action
- Supports: navigate, click, type, scroll, press_key, move_mouse, select_option, console access
- Multi-tab support via `tab_idx` parameter
- Coordinates as fallback when devinid not available

**Key Insights:**
- Hybrid visual (screenshot) + structured (HTML with devinid) is powerful
- Visual helps understand page layout and state
- devinid provides reliable element targeting without fragile CSS selectors
- Console access allows JavaScript execution for complex interactions

**Strengths:**
- Robust element targeting with injected IDs
- Dual feedback (visual + structured) reduces errors
- Full browser control including console/JS execution

**Limitations:**
- Proprietary implementation
- Requires headful browser for screenshots (we need headless)

### 2. Manus (Monica AI)

**Architecture:**
- Cloud-based virtual computing environment (Ubuntu Linux)
- Uses Playwright for web interaction
- "CodeAct" approach - uses executable Python code as action mechanism
- Agent loop: analyze -> plan -> execute -> observe
- File-based memory for progress tracking
- Multi-model dynamic invocation (Claude, GPT-4, Gemini)

**Browser Operator (Local Extension):**
- Chrome/Edge extension for local browser control
- Leverages existing user sessions and credentials
- Trusted local IP avoids CAPTCHAs
- Real-time monitoring in dedicated tab

**Key Insights:**
- Two-browser strategy: cloud (sandboxed) + local (authenticated)
- CodeAct approach allows complex multi-step operations
- File-based state persistence across operations

**Strengths:**
- Flexible multi-model architecture
- Local browser extension for authenticated workflows
- Robust planning with task decomposition

**Limitations:**
- Complex infrastructure (cloud VMs, extensions)
- Local extension requires user installation

### 3. browser-use (Open Source - 73k+ GitHub stars)

**Architecture:**
- Python library built on Playwright
- LLM-powered agent controls browser via natural language
- Supports multiple LLMs (GPT-4, Claude, etc.)
- DOM extraction and element identification
- Auto-waiting and intelligent element selection

**Key Features:**
- Stealth mode for bypassing detection
- Multi-language support (Python native, TypeScript ready)
- Cloud platform for scaling
- Custom LLM integration
- Session/cookie management

**How It Works:**
1. Extracts DOM structure from page
2. Sends DOM + task to LLM
3. LLM decides action (click, type, navigate, etc.)
4. Executes action via Playwright
5. Observes result, repeats

**Strengths:**
- Open source with large community
- Designed specifically for AI agents
- Handles dynamic content well
- Stealth capabilities

**Limitations:**
- Requires LLM for every action (latency/cost)
- DOM extraction can be large for complex pages

### 4. ElizaOS (ai16z)

**Architecture:**
- TypeScript-based multi-agent framework
- Plugin system for extensibility
- Character-based agent personalities
- Memory and state management built-in

**Browser Plugin (`@elizaos/plugin-browser`):**
- Playwright-based web scraping and automation
- Multiple browser support (Chromium, Firefox, WebKit)
- Headless and headed modes
- Content extraction and parsing
- Screenshot capture
- Network request handling
- Optional CAPTCHA solving (via CAPSolver)

**Plugin Interface:**
```typescript
interface Plugin {
  name: string;
  description: string;
  init?: (runtime: IAgentRuntime) => Promise<void>;
  actions?: Action[];
  providers?: Provider[];
  services?: Service[];
  routes?: Route[];
  events?: EventHandlers;
}
```

**Strengths:**
- Well-designed plugin architecture
- Built-in memory/state management
- Active community
- Web3/crypto focus but general-purpose

**Limitations:**
- TypeScript-only (we're Python)
- Heavy framework for just browser automation

### 5. OpenAI Operator

**Architecture:**
- Computer-Using Agent (CUA) model
- GPT-4o with vision capabilities
- Runs in secure virtual browser environment
- High-level task instructions

**Key Features:**
- Browser-based automation without custom APIs
- User can take control at any time
- Proactive user input for sensitive actions (logins, payments, CAPTCHAs)
- Task categories: food, delivery, shopping, travel

**Strengths:**
- Simple user experience
- Built-in safety for sensitive actions
- No setup required

**Limitations:**
- Closed/proprietary
- Limited to ChatGPT Pro users
- Cannot handle complex/specialized tasks reliably

### 6. Claude Computer Use (Anthropic)

**Architecture:**
- Direct desktop/browser control
- "Sees" screen via screenshots
- Performs actions like mouse/keyboard
- Can control native apps and web

**Key Features:**
- Full desktop automation (not just browser)
- Human-like interaction pattern
- Available via API and Chrome extension

**Strengths:**
- Most human-like approach
- Can handle any visual interface
- Desktop + browser unified

**Limitations:**
- Requires Claude Max subscription ($100-200/month)
- Screenshot-based (slower than DOM)
- Still in research preview

### 7. AgentQL

**Architecture:**
- AI-powered query language for web
- Natural language selectors
- Built on Playwright
- REST API + Python/JS SDKs

**Query Language:**
```
{
  products[] {
    product_name
    product_price(include currency symbol)
  }
}
```

**Strengths:**
- Semantic element selection (resilient to DOM changes)
- Clean query syntax
- Self-healing queries

**Limitations:**
- Requires API key
- Query language learning curve

## Comparison Matrix

| Feature | Devin | Manus | browser-use | ElizaOS | Operator | Claude CU | AgentQL |
|---------|-------|-------|-------------|---------|----------|-----------|---------|
| Open Source | No | No | Yes | Yes | No | No | Partial |
| Python Support | N/A | Yes | Yes | No | N/A | Yes | Yes |
| Headless Mode | Yes | Yes | Yes | Yes | N/A | No | Yes |
| Element IDs | devinid | N/A | DOM index | N/A | N/A | N/A | Semantic |
| Visual Feedback | Yes | Yes | Optional | Optional | Yes | Yes | No |
| LLM Required | Yes | Yes | Yes | Yes | Yes | Yes | Yes |
| Stealth Mode | Unknown | Yes | Yes | Unknown | N/A | N/A | Unknown |
| Multi-tab | Yes | Yes | Yes | Yes | Unknown | Yes | Yes |

## Recommended Approach for CompyMac

### Hybrid Architecture

```
                    +------------------+
                    |   Agent/LLM      |
                    +--------+---------+
                             |
                    +--------v---------+
                    |  BrowserTool     |
                    |  (Abstraction)   |
                    +--------+---------+
                             |
         +-------------------+-------------------+
         |                   |                   |
+--------v-------+  +--------v-------+  +--------v-------+
| DOM Extractor  |  | Action Engine  |  | State Manager  |
| (Structured)   |  | (Playwright)   |  | (Screenshots)  |
+----------------+  +----------------+  +----------------+
```

### Core Components

1. **BrowserService** (Playwright wrapper)
   - Headless Chromium browser management
   - Session/context isolation
   - Network interception capabilities

2. **DOMExtractor**
   - Extract simplified DOM structure
   - Assign stable element identifiers (like devinid)
   - Filter interactive elements
   - Compress for LLM context

3. **ActionEngine**
   - Standard actions: navigate, click, type, scroll, wait
   - Element targeting by ID or selector
   - Coordinate fallback
   - Error handling with retries

4. **StateManager**
   - Page state tracking
   - Screenshot capture (optional, for debugging)
   - History of actions and results
   - Cookie/session persistence

### Implementation Options

**Option A: Build on browser-use**
- Fork/adapt browser-use for our needs
- Leverage existing DOM extraction
- Add our element ID injection
- Integrate with our harness interface

**Option B: Build from scratch with Playwright**
- Direct Playwright integration
- Custom DOM extraction
- Full control over implementation
- More work but cleaner integration

**Option C: Adapt ElizaOS plugin-browser**
- Port TypeScript to Python
- Use their patterns/architecture
- Benefit from their testing

### Recommendation: Option A (browser-use adaptation)

**Rationale:**
1. browser-use is the most mature open-source AI browser agent library
2. Already handles many edge cases we'd need to solve
3. Large community for support
4. Can be customized for our needs
5. Playwright-based (same as Devin, proven approach)

### Implementation Plan

1. **Phase 1: Basic Integration**
   - Install browser-use as dependency
   - Create BrowserTool wrapper for our harness
   - Implement basic actions (navigate, click, type)
   - Add to tool registry

2. **Phase 2: Enhanced Features**
   - Add element ID injection (devinid-style)
   - Implement DOM compression for LLM context
   - Add screenshot capture for debugging
   - Network interception for API monitoring

3. **Phase 3: Agent Integration**
   - Integrate with multi-agent architecture
   - Add browser-specific planning prompts
   - Implement error recovery for browser actions
   - Add browser state to workspace

### Constraints for Our Implementation

1. **Headless only** - We cannot use headful browsers
2. **No CAPTCHA solving** - Cannot solve CAPTCHAs in headless mode
3. **Selenium/ChromeDriver preferred** - Per system notes, though Playwright is acceptable
4. **Python** - Must integrate with our Python codebase

## Open Questions

1. Should we use browser-use directly or extract patterns?
2. How much DOM context should we send to the LLM?
3. Should we support multiple browser engines or just Chromium?
4. How do we handle authentication for sites requiring login?
5. Should we implement a local browser extension option (like Manus)?

## References

- [browser-use GitHub](https://github.com/browser-use/browser-use) - 73k+ stars
- [ElizaOS plugin-browser](https://github.com/elizaos-plugins/plugin-browser)
- [Playwright Documentation](https://playwright.dev/)
- [Manus Technical Report](https://gist.github.com/renschni/4fbc70b31bad8dd57f3370239dccd58f)
- [AgentQL Documentation](https://docs.agentql.com/)
- [OpenAI Operator](https://openai.com/index/computer-using-agent/)
