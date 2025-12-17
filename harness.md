# Harness Exploration Lab Notebook

This document is an empirical exploration of the "harness" - the external scaffolding that shapes an LLM-based agent's behavior.

**Interactive Network Map**: [View the harness architecture flowchart](./harness-network.html)

## 1. Harness Overview

The harness is the runtime environment that injects tool schemas into the LLM context, routes tool calls to executors, returns results back to the LLM, manages session state, and enforces constraints.

### Observed Actors (Minds)

| Actor | Type | Evidence | Statefulness |
|-------|------|----------|--------------|
| Primary LLM (me) | LLM | Writing this | Session-scoped context |
| ask_smart_friend | LLM (confirmed) | Different voice, structured format | Stateless per call |
| visual_checker | Vision LLM (confirmed) | Analyzes screenshots | Stateless per call |
| Tool executors | Code | Deterministic, fast | Varies by tool |

## 2. Tool Invocation Lifecycle

User Input -> Primary LLM -> Tool call(s) -> Harness routes -> Executor runs -> Result returned -> Harness formats -> Primary LLM continues

Key observations:
- Multiple tools can be called in parallel
- Tool results are structured, not raw output
- Large outputs truncated and saved to /home/ubuntu/full_outputs/

## 3. Tool Families

### File Tools (Read, Edit, Write)
- Read: Returns file contents with line numbers, errors clearly on missing files
- Edit: Requires unique old_string, must Read first
- Write: Must Read existing files first

### Shell Tools (bash)
- Returns structured output with return code
- bash_id creates persistent sessions
- Failures are normal returns with non-zero codes

### Browser Tools
- Playwright-based Chrome control
- HTML stripped with devinid attributes injected
- Screenshots auto-captured

### Git Tools
- Auth via proxy URL (git-manager.devin.ai)
- Full PR details, repo listing, CI checks

### Search Tools
- grep: ripgrep-based, returns matches with line numbers
- glob: file pattern matching
- web_search: Exa API, structured results

### LLM-Backed Tools (Sub-Minds)

**ask_smart_friend**: Separate LLM with distinct format (Suggestions/Answer/Be Careful/Missing Info)

**visual_checker**: Vision LLM with format (Avoiding Bias/Visual Analysis/Answer/Missing Info)

### Other Tools
- MCP: No servers configured
- Deploy: frontend, backend, logs, expose
- Recording: Screen capture
- message_user, wait, TodoWrite, think, list_secrets

## 4. Invisible Glue

### Truncation
- Large outputs saved to /home/ubuntu/full_outputs/
- Signaled with explicit message and file path

### Secret Masking
- list_secrets shows names only
- Accessed via environment variables

### Authentication
- Git: Proxy URL
- API keys: Environment variables

## 5. Minds Map

**Primary Mind (Devin)**: Main reasoning, all tool access
**Smart Friend**: Second opinion, catches mistakes
**Visual Checker**: Objective visual analysis

## 6. Open Questions

1. Are sub-minds same model with different prompts?
2. Does ask_smart_friend see full conversation?
3. Are parallel tool calls truly concurrent?
4. Where does context truncation happen?
