# Venice LLM Tool Calling Fix

## Problem

The Venice LLM (`qwen3-235b-a22b-instruct-2507`) was not invoking the librarian tool when asked to list documents in the library. Instead, it generated text-only responses like "Your library currently contains no documents" without actually calling the tool.

## Root Cause Analysis

The issue had two components:

### 1. Model Behavior
While the agent configuration correctly set `action_gated=True` and the LLM client sent `tool_choice="required"` to the Venice API, the `qwen3-235b-a22b-instruct-2507` model was not consistently honoring this parameter and generated text responses instead of tool calls.

### 2. Weak System Prompt
The original system prompt was descriptive but not prescriptive. It listed available tools but didn't strongly enforce their use:

**Original prompt (weak):**
```
You have access to a document library containing uploaded PDFs and EPUBs.
Use the `librarian` tool to search and retrieve information.
```

This phrasing suggests tool usage but doesn't mandate it, allowing the model to generate speculative responses instead of calling tools.

## Solution

### 1. Strengthened System Prompt (Primary Fix)

Updated the system prompt in `/home/user/compymac/src/compymac/api/server.py` with explicit, mandatory instructions:

**New prompt (strong):**
```
## CRITICAL: Tool Usage Requirements

You MUST use tools for ALL actions. NEVER provide text-only responses when a tool can be used.

**Every response must include at least one tool call.** When asked to perform any action or retrieve information, you must:
1. Identify the appropriate tool(s) to use
2. Call the tool(s) with the correct parameters
3. Wait for the tool results before responding

Do NOT describe what you would do - actually DO it by calling the tools.
```

And specifically for the librarian:
```
**IMPORTANT:** When asked about documents in your library, you MUST call the librarian tool.
Do NOT guess or make assumptions about document content.

**Example workflow:**
1. `librarian(action="list")` - see available documents (REQUIRED when asked about library contents)
```

Key changes:
- **MUST** vs "use" language
- **NEVER** provide text-only responses
- **Every response must include at least one tool call**
- **REQUIRED** annotation on library queries
- **Do NOT guess** - explicit prohibition on speculation

### 2. Enhanced Logging (Diagnostic Aid)

Added comprehensive logging in `/home/user/compymac/src/compymac/llm.py` to detect and diagnose tool calling violations:

```python
# Log when tool_choice is set
if tool_choice:
    logger.info(f"[TOOL_CHOICE] Setting tool_choice={tool_choice} with {len(tools)} tools available")

# Log when model violates tool_choice="required"
if tool_choice == "required" and not chat_response.has_tool_calls:
    logger.warning(f"[TOOL_CHOICE_VIOLATION] Model ignored tool_choice='required' - "
                 f"returned text-only response: {chat_response.content[:100]}")
```

This helps identify when Venice models are not respecting the `tool_choice` parameter.

## Files Modified

1. **`/home/user/compymac/src/compymac/api/server.py`**
   - Lines 78-124: Updated `AGENT_SYSTEM_PROMPT` with mandatory tool usage requirements

2. **`/home/user/compymac/src/compymac/llm.py`**
   - Lines 156-160: Added logging for `tool_choice` parameter
   - Lines 170-171: Added debug logging for tool availability
   - Lines 179-186: Added violation detection and logging for tool_choice enforcement

## Testing Instructions

### Manual Test
1. Start the web server with Venice LLM configured
2. Upload a document via the Library tab
3. Ask the agent: "Use the librarian tool to list all documents in my library"
4. **Expected behavior:** Agent calls `librarian(action="list")` and returns actual document list
5. Check backend logs for `[TOOL_CHOICE]` and `[TOOL_CHOICE_SUCCESS]` messages

### Verify the Fix
Check backend logs for:
- `[TOOL_CHOICE] Setting tool_choice=required with N tools available` - confirms parameter is sent
- `[TOOL_CHOICE_SUCCESS] Model correctly made X tool call(s)` - confirms model compliance
- **No** `[TOOL_CHOICE_VIOLATION]` warnings - confirms no violations

If `[TOOL_CHOICE_VIOLATION]` warnings appear, it indicates the Venice model is still ignoring the parameter despite the strengthened prompt.

## Alternative Models

If `qwen3-235b-a22b-instruct-2507` continues to have issues with function calling, consider testing with:

1. **`qwen3-coder-480b-a35b-instruct`** - Larger coder-focused model that may have better function calling support
2. **Other Venice models** - Check Venice.ai documentation for models with explicit function calling support

Update the `LLM_MODEL` environment variable to test different models:
```bash
export LLM_MODEL="qwen3-coder-480b-a35b-instruct"
```

## Future Improvements

1. **Retry Mechanism:** Add automatic retry when `tool_choice="required"` is violated
2. **Model Validation:** Add startup check to validate model supports function calling
3. **Fallback Behavior:** If model doesn't support `tool_choice`, inject tool enforcement into system prompt
4. **Model Profiles:** Create model-specific configurations that adjust prompts based on known model capabilities

## Related Issues

- Action-gated mode: `/home/user/compymac/src/compymac/agent_loop.py:288-290`
- Tool schema building: `/home/user/compymac/src/compymac/local_harness.py:6244-6265`
- Venice integration tests: `/home/user/compymac/scripts/test_venice_integration.py`

## References

- OpenAI Function Calling API: https://platform.openai.com/docs/guides/function-calling
- Venice.ai API Documentation: https://docs.venice.ai/
- CompyMac Agent Loop: `/home/user/compymac/src/compymac/agent_loop.py`
