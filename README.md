# CompyMac - Baseline Agent PoC

A proof-of-concept implementation that honestly represents the fundamental constraints of LLM-based agents.

## Philosophy

This is not an idealized system. It's a faithful representation of how LLM-based agents actually work, with all their constraints intact. The goal is to understand these constraints before trying to improve them.

## Core Constraints (Intentionally Preserved)

1. **Session-bounded state**: All state is discarded when a session ends. There is no persistence between sessions.

2. **Fixed context window**: Limited token budget with naive truncation. When context exceeds the budget, the oldest messages are dropped - information is LOST, not summarized.

3. **Tool-mediated actions**: The only way the agent can affect the world is through tools. The agent cannot directly modify files, make HTTP requests, or perform any action except by emitting a tool call.

4. **Turn-based processing**: The agent processes one turn, produces a response, and waits for the next input. There is no background processing.

5. **No learning**: The agent does not update its weights from interactions. Each session uses the same base model.

## Architecture

```
src/compymac/
    types.py      # Core data types (Message, ToolCall, etc.)
    config.py     # Configuration from environment variables
    session.py    # Session - the fundamental unit of state
    context.py    # ContextManager - fixed budget with naive truncation
    llm.py        # LLMClient - abstraction over OpenAI-compatible APIs
    tools.py      # ToolRegistry - the only way to affect the world
    loop.py       # AgentLoop - turn-based execution runtime
```

## LLM Backend Support

The agent works with any OpenAI-compatible API:

- **vLLM**: `LLM_BASE_URL=http://localhost:8000/v1`
- **Ollama**: `LLM_BASE_URL=http://localhost:11434/v1`
- **Venice.ai**: `LLM_BASE_URL=https://api.venice.ai/api/v1`
- **OpenAI**: `LLM_BASE_URL=https://api.openai.com/v1`

## Installation

```bash
pip install -e ".[dev]"
```

## Configuration

Copy `.env.example` to `.env` and configure:

```bash
cp .env.example .env
# Edit .env with your settings
```

## Usage

```python
from compymac import AgentLoop, ToolRegistry, create_mock_tools

# Create with mock tools for demonstration
tools = create_mock_tools()

# Create the agent loop
agent = AgentLoop.create(
    system_prompt="You are a helpful assistant.",
    tools=tools,
)

# Run a turn
result = agent.run("Hello, what can you help me with?")
print(result.response)

# The session tracks truncation events (information loss)
print(f"Truncations: {agent.session.total_truncations}")
print(f"Tokens lost: {agent.session.tokens_lost_to_truncation}")
```

## Why These Constraints Matter

Understanding these constraints is essential before trying to improve them:

- **Session boundaries** force us to think about what information is truly important to persist
- **Context truncation** shows us exactly what information is lost and when
- **Tool mediation** makes side effects explicit and controllable
- **Turn-based processing** defines the interaction model we're working within
- **No learning** means improvements must come from architecture, not training

This baseline is the foundation for understanding what we're working with before we try to make it better.
