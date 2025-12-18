#!/usr/bin/env python3
"""
Test the agent on a real task using LocalHarness with Venice.ai.

This script tests the full agent loop:
1. LLM receives task
2. LLM decides to use tools (Read, Write, bash)
3. LocalHarness executes real file I/O and shell commands
4. Results fed back to LLM
5. LLM completes task

Usage:
    export LLM_API_KEY="your-venice-api-key"
    python scripts/test_real_task.py
"""

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from compymac.config import LLMConfig
from compymac.llm import LLMClient
from compymac.agent_loop import AgentLoop, AgentConfig
from compymac.local_harness import LocalHarness


SYSTEM_PROMPT = """You are a helpful coding assistant. You have access to the following tools:

1. Read - Read the contents of a file
   Parameters: file_path (required), offset (optional), limit (optional)

2. Write - Write content to a file
   Parameters: file_path (required), content (required)

3. bash - Execute a shell command
   Parameters: command (required), exec_dir (required), bash_id (required), timeout (optional)

When given a task, use these tools to complete it. Be concise and efficient.
After completing the task, provide a brief summary of what you did."""


def test_file_manipulation():
    """Test: Create a file, read it, modify it."""
    print("\n" + "=" * 60)
    print("Test 1: File Manipulation")
    print("=" * 60)
    
    config = LLMConfig(
        base_url="https://api.venice.ai/api/v1",
        api_key=os.environ.get("LLM_API_KEY", ""),
        model="qwen3-coder-480b-a35b-instruct",
        temperature=0.7,
        max_tokens=1000,
    )
    
    if not config.api_key:
        print("ERROR: LLM_API_KEY not set")
        return False
    
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = os.path.join(tmpdir, "test.txt")
        
        # Create initial file
        Path(test_file).write_text("Hello World\nThis is line 2\nThis is line 3\n")
        
        harness = LocalHarness()
        client = LLMClient(config)
        
        agent_config = AgentConfig(
            max_steps=5,
            system_prompt=SYSTEM_PROMPT,
        )
        
        loop = AgentLoop(harness, client, agent_config)
        
        task = f"""Read the file at {test_file}, then add a new line at the end that says "Line 4 added by agent", and write it back. Then read it again to confirm the change."""
        
        print(f"Task: {task}")
        print("-" * 60)
        
        try:
            result = loop.run(task)
            print(f"\nAgent response:\n{result[:500]}...")
            print(f"\nSteps: {loop.state.step_count}, Tool calls: {loop.state.tool_call_count}")
            
            # Verify the file was modified
            final_content = Path(test_file).read_text()
            if "Line 4 added by agent" in final_content:
                print("\nVERIFIED: File was correctly modified!")
                return True
            else:
                print(f"\nFAILED: Expected modification not found. Content:\n{final_content}")
                return False
        except Exception as e:
            print(f"ERROR: {e}")
            import traceback
            traceback.print_exc()
            return False
        finally:
            client.close()


def test_shell_command():
    """Test: Run shell commands and process output."""
    print("\n" + "=" * 60)
    print("Test 2: Shell Command Execution")
    print("=" * 60)
    
    config = LLMConfig(
        base_url="https://api.venice.ai/api/v1",
        api_key=os.environ.get("LLM_API_KEY", ""),
        model="qwen3-coder-480b-a35b-instruct",
        temperature=0.7,
        max_tokens=1000,
    )
    
    if not config.api_key:
        print("ERROR: LLM_API_KEY not set")
        return False
    
    with tempfile.TemporaryDirectory() as tmpdir:
        harness = LocalHarness()
        client = LLMClient(config)
        
        agent_config = AgentConfig(
            max_steps=5,
            system_prompt=SYSTEM_PROMPT,
        )
        
        loop = AgentLoop(harness, client, agent_config)
        
        task = f"""Use bash to list the files in /tmp, then create a new directory called 'agent_test' inside {tmpdir}, and list its contents to confirm it was created."""
        
        print(f"Task: {task}")
        print("-" * 60)
        
        try:
            result = loop.run(task)
            print(f"\nAgent response:\n{result[:500]}...")
            print(f"\nSteps: {loop.state.step_count}, Tool calls: {loop.state.tool_call_count}")
            
            # Verify the directory was created
            agent_test_dir = os.path.join(tmpdir, "agent_test")
            if os.path.isdir(agent_test_dir):
                print("\nVERIFIED: Directory was correctly created!")
                return True
            else:
                print(f"\nFAILED: Directory not found at {agent_test_dir}")
                return False
        except Exception as e:
            print(f"ERROR: {e}")
            import traceback
            traceback.print_exc()
            return False
        finally:
            client.close()


def test_code_generation():
    """Test: Generate and run a simple Python script."""
    print("\n" + "=" * 60)
    print("Test 3: Code Generation and Execution")
    print("=" * 60)
    
    config = LLMConfig(
        base_url="https://api.venice.ai/api/v1",
        api_key=os.environ.get("LLM_API_KEY", ""),
        model="qwen3-coder-480b-a35b-instruct",
        temperature=0.7,
        max_tokens=1500,
    )
    
    if not config.api_key:
        print("ERROR: LLM_API_KEY not set")
        return False
    
    with tempfile.TemporaryDirectory() as tmpdir:
        harness = LocalHarness()
        client = LLMClient(config)
        
        agent_config = AgentConfig(
            max_steps=6,
            system_prompt=SYSTEM_PROMPT,
        )
        
        loop = AgentLoop(harness, client, agent_config)
        
        script_path = os.path.join(tmpdir, "fibonacci.py")
        task = f"""Write a Python script to {script_path} that calculates the first 10 Fibonacci numbers and prints them. Then run the script using bash and tell me the output."""
        
        print(f"Task: {task}")
        print("-" * 60)
        
        try:
            result = loop.run(task)
            print(f"\nAgent response:\n{result[:800]}...")
            print(f"\nSteps: {loop.state.step_count}, Tool calls: {loop.state.tool_call_count}")
            
            # Verify the script was created
            if os.path.exists(script_path):
                print(f"\nScript created at {script_path}")
                content = Path(script_path).read_text()
                print(f"Script content:\n{content[:300]}...")
                return True
            else:
                print(f"\nFAILED: Script not found at {script_path}")
                return False
        except Exception as e:
            print(f"ERROR: {e}")
            import traceback
            traceback.print_exc()
            return False
        finally:
            client.close()


def main():
    print("=" * 60)
    print("Real Task Test - Agent with LocalHarness + Venice.ai")
    print("=" * 60)
    
    results = []
    
    results.append(("File Manipulation", test_file_manipulation()))
    results.append(("Shell Commands", test_shell_command()))
    results.append(("Code Generation", test_code_generation()))
    
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
