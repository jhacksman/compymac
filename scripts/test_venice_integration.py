#!/usr/bin/env python3
"""
Test script for Venice.ai integration with the agent loop.

This script verifies that:
1. LLM client can connect to Venice.ai
2. Basic chat completion works
3. Function calling works
4. Agent loop can execute tool calls through the harness

Usage:
    export LLM_API_KEY="your-venice-api-key"
    python scripts/test_venice_integration.py
"""

import os
import sys

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from compymac.config import LLMConfig
from compymac.llm import LLMClient, LLMError
from compymac.agent_loop import AgentLoop, AgentConfig as AgentLoopConfig
from compymac.harness_simulator import create_default_simulator


def test_basic_chat():
    """Test basic chat completion with Venice.ai."""
    print("\n=== Test 1: Basic Chat Completion ===")
    
    config = LLMConfig(
        base_url="https://api.venice.ai/api/v1",
        api_key=os.environ.get("LLM_API_KEY", ""),
        model="qwen3-coder-480b-a35b-instruct",
        temperature=0.7,
        max_tokens=100,
    )
    
    if not config.api_key:
        print("ERROR: LLM_API_KEY environment variable not set")
        return False
    
    try:
        client = LLMClient(config)
        response = client.chat(
            messages=[{"role": "user", "content": "Say 'Hello from Venice!' in exactly those words."}]
        )
        print(f"Response: {response.content}")
        print(f"Finish reason: {response.finish_reason}")
        client.close()
        return True
    except LLMError as e:
        print(f"ERROR: {e}")
        return False


def test_function_calling():
    """Test function calling with Venice.ai."""
    print("\n=== Test 2: Function Calling ===")
    
    config = LLMConfig(
        base_url="https://api.venice.ai/api/v1",
        api_key=os.environ.get("LLM_API_KEY", ""),
        model="qwen3-coder-480b-a35b-instruct",
        temperature=0.7,
        max_tokens=200,
    )
    
    if not config.api_key:
        print("ERROR: LLM_API_KEY environment variable not set")
        return False
    
    tools = [
        {
            "type": "function",
            "function": {
                "name": "read_file",
                "description": "Read a file from the filesystem",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "file_path": {"type": "string", "description": "Path to the file"}
                    },
                    "required": ["file_path"]
                }
            }
        }
    ]
    
    try:
        client = LLMClient(config)
        response = client.chat(
            messages=[{"role": "user", "content": "Read the file at /tmp/test.txt"}],
            tools=tools,
        )
        
        if response.has_tool_calls:
            print(f"Tool calls: {len(response.tool_calls)}")
            for tc in response.tool_calls:
                print(f"  - {tc.name}({tc.arguments})")
            client.close()
            return True
        else:
            print(f"No tool calls, got text response: {response.content}")
            client.close()
            return False
    except LLMError as e:
        print(f"ERROR: {e}")
        return False


def test_agent_loop():
    """Test agent loop with Venice.ai and harness simulator."""
    print("\n=== Test 3: Agent Loop with Harness ===")
    
    config = LLMConfig(
        base_url="https://api.venice.ai/api/v1",
        api_key=os.environ.get("LLM_API_KEY", ""),
        model="qwen3-coder-480b-a35b-instruct",
        temperature=0.7,
        max_tokens=500,
    )
    
    if not config.api_key:
        print("ERROR: LLM_API_KEY environment variable not set")
        return False
    
    try:
        # Create harness simulator and LLM client
        harness = create_default_simulator()
        client = LLMClient(config)
        
        # Create agent loop
        agent_config = AgentLoopConfig(max_steps=3)
        loop = AgentLoop(harness, client, agent_config)
        
        # Run a simple task
        print("Running agent with task: 'Read the file at /test/example.txt'")
        result = loop.run("Read the file at /test/example.txt and tell me what's in it.")
        
        print(f"\nFinal response: {result[:200]}..." if len(result) > 200 else f"\nFinal response: {result}")
        print(f"Steps taken: {loop.state.step_count}")
        print(f"Tool calls made: {loop.state.tool_call_count}")
        
        # Check event log
        events = harness.get_event_log().events
        print(f"Events logged: {len(events)}")
        
        client.close()
        return True
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    print("=" * 60)
    print("Venice.ai Integration Test")
    print("=" * 60)
    print(f"Model: qwen3-coder-480b-a35b-instruct")
    print(f"Base URL: https://api.venice.ai/api/v1")
    
    results = []
    
    # Run tests
    results.append(("Basic Chat", test_basic_chat()))
    results.append(("Function Calling", test_function_calling()))
    results.append(("Agent Loop", test_agent_loop()))
    
    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    
    all_passed = True
    for name, passed in results:
        status = "PASS" if passed else "FAIL"
        print(f"  {name}: {status}")
        if not passed:
            all_passed = False
    
    print("=" * 60)
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
