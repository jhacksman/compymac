# Menu System Design

## Overview

CompyMac implements a **2-level hierarchical menu system** for tool discovery to address the tool overload problem. Research shows that LLM agents struggle with tool selection when presented with 17+ tools simultaneously (see `docs/research/tool-overload-decision-fatigue.md`). Instead of exposing 60+ tools at once, the agent starts with 6 meta-tools at ROOT and drills into specific modes.

## Architecture

```
ROOT (6 meta-tools)
  |
  +-- menu_enter("swe") --> SWE Mode (30 tools + 6 meta-tools = 36 visible)
  +-- menu_enter("library") --> Library Mode (4 tools + 6 meta-tools = 10 visible)
  +-- menu_enter("browser") --> Browser Mode (16 tools + 6 meta-tools = 22 visible)
  +-- menu_enter("search") --> Search Mode (7 tools + 6 meta-tools = 13 visible)
  +-- menu_enter("git") --> Git Mode (19 tools + 6 meta-tools = 25 visible)
  +-- menu_enter("data") --> Data Mode (10 tools + 6 meta-tools = 16 visible)
  +-- menu_enter("deploy") --> Deploy Mode (5 tools + 6 meta-tools = 11 visible)
  +-- menu_enter("ai") --> AI Mode (9 tools + 6 meta-tools = 15 visible)
  +-- menu_enter("integrations") --> Integrations Mode (3 tools + 6 meta-tools = 9 visible)
```

## Meta-Tools (Always Visible)

These 6 tools are available in all states:

| Tool | Purpose |
|------|---------|
| `menu_list` | Show current mode and available options |
| `menu_enter` | Enter a specific mode |
| `menu_exit` | Return to ROOT from current mode |
| `complete` | Signal task completion |
| `think` | Internal reasoning step |
| `message_user` | Communicate with user |

## Mode Definitions

### Primary Modes (Most Frequently Used)

#### 1. SWE Mode (`swe`) - 30 tools
Software engineering mode for code editing, testing, and commits.

**Tools:**
- Core file ops: `Read`, `Edit`, `Write`, `bash`, `grep`, `glob`
- LSP: `lsp_tool`
- Git subset: `git_status`, `git_diff_unstaged`, `git_diff_staged`, `git_commit`, `git_add`
- Shell management: `bash_output`, `write_to_shell`, `kill_shell`, `wait`
- Cross-cutting research: `web_search`, `web_get_contents`
- Cross-cutting AI: `ask_smart_friend`
- Cross-cutting library: `librarian`, `librarian_search`
- Cross-cutting todos: `TodoCreate`, `TodoRead`, `TodoStart`, `TodoClaim`, `TodoVerify`
- SWE-bench phases: `advance_phase`, `return_to_fix_phase`, `analyze_test_failure`, `get_phase_status`

#### 2. Library Mode (`library`) - 4 tools
Document library for searching uploaded PDFs, EPUBs, and other documents.

**Tools:**
- Library: `librarian`, `librarian_search`
- Cross-cutting web: `web_search`, `web_get_contents`

#### 3. Browser Mode (`browser`) - 16 tools
Browser automation for UI testing and web interaction.

**Tools:**
- Browser: `browser_navigate`, `browser_view`, `browser_click`, `browser_type`, `browser_scroll`, `browser_screenshot`, `browser_console`, `browser_press_key`, `browser_move_mouse`, `browser_select_option`, `browser_select_file`, `browser_set_mobile`, `browser_restart`
- Recording: `recording_start`, `recording_stop`
- Cross-cutting visual: `visual_checker`

#### 4. Search Mode (`search`) - 7 tools
Web research and documentation lookup.

**Tools:**
- Search: `web_search`, `web_get_contents`
- Browser subset: `browser_navigate`, `browser_view`
- Cross-cutting library: `librarian`, `librarian_search`
- Cross-cutting AI: `ask_smart_friend`

### Secondary Modes

#### 5. Git Mode (`git`) - 19 tools
Full version control operations including PRs.

**Tools:**
- Local git: `git_status`, `git_diff_unstaged`, `git_diff_staged`, `git_diff`, `git_commit`, `git_add`, `git_reset`, `git_log`, `git_create_branch`, `git_checkout`, `git_show`, `git_branch_list`
- Remote git: `git_view_pr`, `git_create_pr`, `git_update_pr_description`, `git_pr_checks`, `git_ci_job_logs`, `git_comment_on_pr`, `list_repos`

#### 6. Data Mode (`data`) - 10 tools
File management for non-code files.

**Tools:**
- Filesystem: `fs_read_file`, `fs_write_file`, `fs_list_directory`, `fs_create_directory`, `fs_delete`, `fs_move`, `fs_file_info`
- Cross-cutting search: `grep`, `glob`
- Cross-cutting bash: `bash`

#### 7. Deploy Mode (`deploy`) - 5 tools
Deployment and CI/CD operations.

**Tools:**
- Deploy: `deploy`
- CI: `git_ci_job_logs`, `git_pr_checks`
- Cross-cutting bash: `bash`, `bash_output`

### Utility Modes

#### 8. AI Mode (`ai`) - 9 tools
AI assistance and task management.

**Tools:**
- AI: `ask_smart_friend`, `visual_checker`
- Todos: `TodoCreate`, `TodoRead`, `TodoStart`, `TodoClaim`, `TodoVerify`
- Cross-cutting web: `web_search`, `web_get_contents`

#### 9. Integrations Mode (`integrations`) - 3 tools
External integrations and dynamic tool discovery.

**Tools:**
- MCP: `mcp_tool`
- Secrets: `list_secrets`
- Dynamic: `request_tools`

## Design Principles

### 1. "Mask, Don't Remove" Pattern

Based on Manus research, tools are always registered in the system but visibility is controlled by the current mode. This means:
- Tool schemas are stable (no dynamic loading/unloading)
- The agent can always switch modes to access any tool
- No tools are ever truly "hidden" - just not visible in current mode

### 2. Cross-Cutting Tools

General-purpose tools appear in multiple modes where users semantically expect them:

| Tool | Appears In |
|------|------------|
| `web_search`, `web_get_contents` | swe, library, search, ai |
| `librarian`, `librarian_search` | swe, library, search |
| `ask_smart_friend` | swe, search, ai |
| `bash` | swe, data, deploy |
| `grep`, `glob` | swe, data |
| `visual_checker` | browser, ai |
| `git_ci_job_logs`, `git_pr_checks` | git, deploy |
| Todo tools | swe, ai |

### 3. Mechanical Validation

The `validate_tool_coverage()` function ensures every registered tool appears in at least one mode. This prevents hand-maintenance errors where new tools are added but forgotten in the menu system.

```python
def validate_tool_coverage(registered_tools: set[str]) -> tuple[bool, list[str]]:
    """Validate that all registered tools are in at least one mode."""
    # Returns (is_valid, list_of_unmapped_tools)
```

### 4. Mode Ordering

Modes are ordered by frequency of use:
1. Primary modes first (swe, library, browser, search)
2. Secondary modes next (git, data, deploy)
3. Utility modes last (ai, integrations)

This leverages LLM hypersensitivity to ordering (arxiv:2505.11584).

## Maintenance Contract

When adding a new tool to CompyMac:

1. **Register the tool** in the tool registry (as normal)
2. **Add to at least one mode** in `TOOL_MODES` in `tool_menu.py`
3. **Consider cross-cutting placement** - if the tool is general-purpose, add it to all modes where users would expect it
4. **Run tests** - `validate_tool_coverage()` will fail if any tool is unmapped
5. **Update this doc** if adding a new mode or significantly changing tool distribution

## Implementation

The menu system is implemented in `src/compymac/tool_menu.py`:

- `MenuState` enum: ROOT or IN_MODE
- `ToolMode` dataclass: name, display_name, tool_list, description
- `META_TOOLS` list: always-visible navigation tools
- `TOOL_MODES` dict: mode definitions with tool lists
- `MenuManager` class: tracks current mode, provides navigation methods
- `validate_tool_coverage()`: ensures all tools are reachable

## References

- `docs/research/tool-overload-decision-fatigue.md` - Research on tool overload problem
- arxiv:2505.03275 - RAG-MCP: Mitigating Prompt Bloat
- arxiv:2505.03961 - Narrative priming for tool descriptions
- arxiv:2505.11584 - LLM hypersensitivity to ordering
