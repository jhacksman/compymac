# Browser Tool Design Document: What's Broken and How to Fix It

## Executive Summary

CompyMac's browser tools are correctly implemented and registered, but the agent cannot access them because the menu system gates tool visibility without teaching the agent how to navigate it. The system prompt doesn't mention the menu system, doesn't provide intent-to-mode mapping, and doesn't inject current menu state into context. This is fundamentally a **tool discoverability and state salience failure**, not a browser tool implementation failure.

## Research Findings

### Industry Approaches

#### Manus (Browser Operator)
- Uses Chrome extension running in user's actual browser with authentic local IP, cookies, sessions
- Key principle: **"Mask, Don't Remove"** - tools are always registered, visibility is controlled dynamically
- Avoids dynamically adding/removing tools mid-iteration (breaks KV-cache)
- Context engineering focus: stable prefix + cache breakpoint + dynamic content
- Critical insight: Masking only works if the model knows how to reach masked capabilities

#### Devin (Interactive Browser)
- Browser is part of sandboxed compute environment (alongside shell, code editor)
- **No menu system** - all tools exposed directly to the model
- "Interactive Browser" feature lets users help with CAPTCHAs, MFA, complex navigation
- Trades higher tool overload risk for "never get stuck" reliability

### Relevant ArXiv Research

| Paper | Key Insight | Relevance to CompyMac |
|-------|-------------|----------------------|
| **AnyTool** (2402.04253) | Hierarchical API retriever for 16,000+ APIs with self-reflection mechanism | Validates hierarchical approach; suggests adding retry/reflection when tool routing fails |
| **ScaleMCP** (2505.06416) | "Existing approaches abstract tool selection before the LLM agent is invoked, limiting its autonomy" | Supports giving agent autonomy to navigate menu, not server-side auto-selection |
| **Context Window Overflow** (2511.22729) | Large tool outputs overflow context; solution is memory pointers | Validates menu system's goal of reducing tool schema bloat |
| **Agent-as-Tool** (2507.01489) | Hierarchical framework detaching tool calling from reasoning | Supports ROOT (routing) vs modes (execution) separation |
| **AgentOrchestra** (2506.12508) | Central planning agent decomposes objectives and delegates to specialized agents | Validates mode-based specialization approach |
| **GoalAct** (2504.16563) | Continuously updated global planning + hierarchical execution | Supports explicit mode selection as first action |

## Current Implementation Analysis

### What Works

1. **Browser tools are correctly implemented** (`local_harness.py:1337-1743`)
   - All 13 browser tools registered: `browser_navigate`, `browser_view`, `browser_click`, `browser_type`, `browser_scroll`, `browser_screenshot`, `browser_console`, `browser_press_key`, `browser_move_mouse`, `browser_select_option`, `browser_select_file`, `browser_set_mobile`, `browser_restart`
   - Web citations support added for clickable chips
   - Recording tools included for UI testing evidence

2. **Menu system is correctly designed** (`tool_menu.py`)
   - 2-level hierarchy: ROOT → 9 modes (swe, library, browser, search, git, data, deploy, ai, integrations)
   - Cross-cutting tools appear in multiple modes where semantically appropriate
   - Browser mode includes 13 browser tools + recording + visual_checker
   - `browser_navigate` and `browser_view` also in `search` mode for research workflows

3. **Menu system is enabled** (`api/server.py:235`)
   ```python
   use_menu_system=True,  # Hierarchical tool menu - reduces initial tools
   ```

4. **Menu navigation tools have reasonable descriptions** (`local_harness.py:1256-1312`)
   - `menu_list`: "List the current menu state and available options"
   - `menu_enter`: Lists common modes (swe, library, browser, search, git, ai)
   - `menu_exit`: "Exit the current mode and return to ROOT"

### What's Broken

#### 1. System Prompt Doesn't Mention Menu System

The system prompt modules (`prompts/tools/registry.md`, `prompts/control/protocol.md`, `prompts/core/identity.md`) make **no mention** of the menu system:

```markdown
# Tool Registry (prompts/tools/registry.md)

## File Operations
1. **Read** - Read file contents
2. **Edit** - Modify file contents
...
8. **complete** - Mark task as done
```

This creates a **contradictory contract**: the prompt says "these are the tools" but the API provides `menu_enter/menu_list/menu_exit` at ROOT. The agent doesn't believe browser tools exist behind a menu.

#### 2. No Intent-to-Mode Mapping in Prompt

The agent has no guidance on when to enter which mode:
- "Navigate to google.com" → should trigger `menu_enter("browser")`
- "Fix this bug" → should trigger `menu_enter("swe")`
- "Search for documentation" → should trigger `menu_enter("search")`

Without this mapping, the agent defaults to prose responses because it doesn't know tools exist.

#### 3. No Current State Injection

The agent loop (`agent_loop.py:run_step`) swaps tool schemas based on menu state but **doesn't inject state awareness** into the message history:
- No "You are at ROOT" message
- No "Available modes: swe, browser, library..." reminder
- No "You must select a mode before using domain tools" instruction

#### 4. ROOT is a Dead-End

At ROOT, the agent only sees:
- `menu_list`, `menu_enter`, `menu_exit`
- `complete`, `think`, `message_user`

If the agent doesn't understand ROOT is a routing layer, it will:
1. See no relevant tools for the task
2. Default to `message_user` with a prose response
3. Never discover that browser tools exist behind `menu_enter("browser")`

This is exactly the observed behavior: "browser ready, but no navigation yet" instead of calling `browser_navigate`.

## Design Options

### Option A: Teach the Menu (Recommended)

Add menu system awareness to the system prompt and inject state each turn.

**Pros:**
- Preserves agent autonomy (agent decides which mode)
- Maintains tool overload protection
- Aligns with Manus "Mask, Don't Remove" principle
- Consistent with AnyTool/ScaleMCP research

**Cons:**
- Requires prompt engineering
- Adds tokens to context
- May still fail if model ignores instructions

**Implementation:**
1. Add menu system section to `prompts/tools/registry.md`:
   ```markdown
   ## Tool Discovery (Menu System)
   
   Tools are organized into modes to reduce cognitive load. At ROOT, only
   navigation tools are available. You MUST enter a mode to access domain tools.
   
   **Intent → Mode Mapping:**
   - Code changes, debugging, testing → `menu_enter("swe")`
   - Web browsing, clicking, forms, UI testing → `menu_enter("browser")`
   - Web research, documentation lookup → `menu_enter("search")`
   - Document library queries → `menu_enter("library")`
   - Git operations, PRs, CI → `menu_enter("git")`
   
   **First Action Rule:** On most tasks, your first action should be selecting
   a mode. Use `menu_list()` to see available modes if unsure.
   ```

2. Inject menu state into context each turn in `agent_loop.py`:
   ```python
   if self.config.use_menu_system:
       menu_state = self.harness.get_menu_manager().list_menu()
       self.state.messages.append(Message(
           role="user",
           content=f"[MENU_STATE]: {menu_state}"
       ))
   ```

### Option B: Start in Default Mode

Start sessions in `swe` mode instead of ROOT, use menu for switching.

**Pros:**
- Agent can act immediately without mode selection
- Reduces "first action" friction
- Most tasks are coding tasks anyway

**Cons:**
- Changes meaning of ROOT
- May confuse users who expect ROOT
- Doesn't solve the fundamental discoverability issue

**Implementation:**
```python
# In MenuManager.__init__ or session creation
self._current_mode = "swe"
self._state = MenuState.IN_MODE
```

### Option C: Expand Cross-Cutting Tools

Add `browser_navigate` and `browser_view` to more modes (especially `swe`).

**Pros:**
- Reduces mode-switch friction for common workflows
- Docs browsing is common while coding
- Already precedent in `search` mode

**Cons:**
- Doesn't fix ROOT dead-end
- Increases tool count in modes
- Partial solution only

**Implementation:**
```python
# In tool_menu.py, add to swe mode:
"browser_navigate", "browser_view",  # For docs browsing
```

### Option D: Remove Menu System (Devin Approach)

Expose all tools directly, no menu gating.

**Pros:**
- Simplest to reason about
- Highest reliability (never get stuck)
- Matches Devin's approach

**Cons:**
- Loses tool overload protection
- 60+ tools in context every turn
- Higher token cost
- Jack has invested in menu system

**Implementation:**
```python
# In api/server.py
use_menu_system=False,
```

### Option E: RAG-Based Tool Retrieval (Future)

Replace static modes with embedding-based tool router.

**Pros:**
- Dynamic tool discovery
- Scales to unlimited tools
- Agent autonomy preserved

**Cons:**
- Larger implementation effort
- Requires embedding infrastructure
- Still needs state visibility

**Implementation:** Create a `tool_router` tool that takes a query and returns relevant tool schemas or suggests a mode.

## Recommended Approach

**Implement Option A (Teach the Menu) with elements of Option C (Cross-Cutting).**

### Phase 1: Fix Prompt Contract (Immediate)

1. Add menu system documentation to `prompts/tools/registry.md`
2. Include intent-to-mode mapping
3. Add "first action rule" guidance

### Phase 2: Add State Injection (Immediate)

1. Inject `[MENU_STATE]` into context at ROOT
2. Include available modes and current state
3. Add reminder that mode selection is required

### Phase 3: Expand Cross-Cutting (Short-term)

1. Add `browser_navigate`, `browser_view` to `swe` mode
2. Keep full browser interaction in `browser` mode
3. Treat `search` mode as "read-only web + light browsing"

### Phase 4: Self-Reflection (Medium-term)

1. If agent responds with prose at ROOT, inject retry prompt
2. "You are at ROOT with no domain tools. Did you mean to enter a mode?"
3. Aligns with AnyTool's self-reflection mechanism

## Anti-Patterns to Avoid

1. **Server-side auto-mode selection** - Bypasses agent autonomy, "cheating"
2. **Removing menu system entirely** - Loses tool overload protection
3. **Adding all browser tools to META_TOOLS** - Undermines hierarchy
4. **Guessing mode from keywords** - Fragile, doesn't teach agent

## Success Criteria

1. Agent at ROOT understands it must select a mode
2. Agent correctly maps "navigate to X" → `menu_enter("browser")` → `browser_navigate(X)`
3. Agent can switch modes mid-task when needed
4. Tool overload protection maintained (7-15 tools per mode)
5. KV-cache optimization preserved (stable prompt prefix)

## Files to Modify

| File | Change |
|------|--------|
| `prompts/tools/registry.md` | Add menu system documentation |
| `agent_loop.py` | Inject menu state into context |
| `tool_menu.py` | Add browser subset to swe mode |
| `local_harness.py` | No changes needed (tools correctly registered) |

## References

- Manus Context Engineering Blog: https://manus.im/blog/Context-Engineering-for-AI-Agents-Lessons-from-Building-Manus
- Manus Technical Report: https://gist.github.com/renschni/4fbc70b31bad8dd57f3370239dccd58f
- Devin Interactive Browser: https://docs.devin.ai/product-guides/interactive-browser
- AnyTool (arXiv:2402.04253): Hierarchical API retrieval
- ScaleMCP (arXiv:2505.06416): Dynamic MCP tool selection
- Context Window Overflow (arXiv:2511.22729): Memory pointer approach
- Agent-as-Tool (arXiv:2507.01489): Hierarchical decision making
- AgentOrchestra (arXiv:2506.12508): Multi-agent orchestration
- GoalAct (arXiv:2504.16563): Global planning + hierarchical execution
