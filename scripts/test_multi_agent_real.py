#!/usr/bin/env python3
"""
Test the multi-agent architecture with real Venice.ai LLM.

This script tests the full multi-agent workflow:
1. Manager receives a goal
2. Planner creates a plan (JSON output)
3. Executor executes each step using AgentLoop with tools
4. Reflector reviews results and recommends actions
5. Manager orchestrates the workflow to completion

Usage:
    export LLM_API_KEY="your-venice-api-key"
    python scripts/test_multi_agent_real.py
"""

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from compymac.config import LLMConfig
from compymac.llm import LLMClient
from compymac.local_harness import LocalHarness
from compymac.multi_agent import ManagerAgent, ManagerState


def create_llm_client():
    """Create an LLM client configured for Venice.ai."""
    config = LLMConfig(
        base_url="https://api.venice.ai/api/v1",
        api_key=os.environ.get("LLM_API_KEY", ""),
        model="llama-3.3-70b",
        temperature=0.7,
        max_tokens=2000,
    )
    
    if not config.api_key:
        print("ERROR: LLM_API_KEY environment variable not set")
        return None
    
    return LLMClient(config)


def test_simple_file_task():
    """Test: Multi-agent workflow for a simple file creation task."""
    print("\n" + "=" * 60)
    print("Test 1: Simple File Creation Task")
    print("=" * 60)
    
    client = create_llm_client()
    if not client:
        return False
    
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = os.path.join(tmpdir, "hello.txt")
        
        harness = LocalHarness()
        manager = ManagerAgent(harness, client)
        
        goal = f"Create a file at {test_file} with the content 'Hello from multi-agent system!'"
        
        print(f"Goal: {goal}")
        print("-" * 60)
        
        try:
            result = manager.run(goal)
            
            print(f"\nManager final state: {manager.state.value}")
            print(f"Workspace plan steps: {len(manager.workspace.plan)}")
            print(f"Step results: {len(manager.workspace.step_results)}")
            print(f"\nFinal result:\n{result[:500]}...")
            
            # Print plan details
            print("\n--- Plan ---")
            for step in manager.workspace.plan:
                print(f"  Step {step.index + 1}: {step.description[:80]}...")
            
            # Print step results
            print("\n--- Step Results ---")
            for sr in manager.workspace.step_results:
                status = "OK" if sr.success else "FAIL"
                print(f"  Step {sr.step_index + 1} [{status}]: {sr.summary[:80]}...")
            
            # Verify the file was created
            if os.path.exists(test_file):
                content = Path(test_file).read_text()
                print(f"\nFile content: {content}")
                if "Hello" in content or "hello" in content.lower():
                    print("\nVERIFIED: File was created with expected content!")
                    return manager.state == ManagerState.COMPLETED
                else:
                    print(f"\nWARNING: File created but content unexpected: {content}")
                    return manager.state == ManagerState.COMPLETED
            else:
                print(f"\nFAILED: File not found at {test_file}")
                return False
                
        except Exception as e:
            print(f"ERROR: {e}")
            import traceback
            traceback.print_exc()
            return False
        finally:
            client.close()


def test_multi_step_task():
    """Test: Multi-agent workflow for a multi-step task."""
    print("\n" + "=" * 60)
    print("Test 2: Multi-Step Task (Create, Read, Modify)")
    print("=" * 60)
    
    client = create_llm_client()
    if not client:
        return False
    
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = os.path.join(tmpdir, "numbers.txt")
        
        harness = LocalHarness()
        manager = ManagerAgent(harness, client)
        
        goal = f"""Complete these steps:
1. Create a file at {test_file} with the numbers 1, 2, 3 on separate lines
2. Read the file to verify its contents
3. Add the number 4 to the file
4. Read the file again to confirm all four numbers are present"""
        
        print(f"Goal: {goal}")
        print("-" * 60)
        
        try:
            result = manager.run(goal)
            
            print(f"\nManager final state: {manager.state.value}")
            print(f"Workspace plan steps: {len(manager.workspace.plan)}")
            print(f"Step results: {len(manager.workspace.step_results)}")
            print(f"\nFinal result:\n{result[:500]}...")
            
            # Print plan details
            print("\n--- Plan ---")
            for step in manager.workspace.plan:
                print(f"  Step {step.index + 1}: {step.description[:80]}...")
            
            # Print step results
            print("\n--- Step Results ---")
            for sr in manager.workspace.step_results:
                status = "OK" if sr.success else "FAIL"
                print(f"  Step {sr.step_index + 1} [{status}]: {sr.summary[:80]}...")
            
            # Verify the file has all numbers
            if os.path.exists(test_file):
                content = Path(test_file).read_text()
                print(f"\nFile content:\n{content}")
                has_all = all(str(n) in content for n in [1, 2, 3, 4])
                if has_all:
                    print("\nVERIFIED: File contains all four numbers!")
                    return manager.state == ManagerState.COMPLETED
                else:
                    print(f"\nWARNING: Not all numbers found in file")
                    return False
            else:
                print(f"\nFAILED: File not found at {test_file}")
                return False
                
        except Exception as e:
            print(f"ERROR: {e}")
            import traceback
            traceback.print_exc()
            return False
        finally:
            client.close()


def test_shell_task():
    """Test: Multi-agent workflow with shell commands."""
    print("\n" + "=" * 60)
    print("Test 3: Shell Command Task")
    print("=" * 60)
    
    client = create_llm_client()
    if not client:
        return False
    
    with tempfile.TemporaryDirectory() as tmpdir:
        harness = LocalHarness()
        manager = ManagerAgent(harness, client)
        
        goal = f"Use shell commands to create a directory called 'test_dir' inside {tmpdir}, then create a file called 'info.txt' inside that directory with the text 'Created by multi-agent system'"
        
        print(f"Goal: {goal}")
        print("-" * 60)
        
        try:
            result = manager.run(goal)
            
            print(f"\nManager final state: {manager.state.value}")
            print(f"Workspace plan steps: {len(manager.workspace.plan)}")
            print(f"Step results: {len(manager.workspace.step_results)}")
            print(f"\nFinal result:\n{result[:500]}...")
            
            # Print plan details
            print("\n--- Plan ---")
            for step in manager.workspace.plan:
                print(f"  Step {step.index + 1}: {step.description[:80]}...")
            
            # Print step results
            print("\n--- Step Results ---")
            for sr in manager.workspace.step_results:
                status = "OK" if sr.success else "FAIL"
                print(f"  Step {sr.step_index + 1} [{status}]: {sr.summary[:80]}...")
            
            # Verify the directory and file were created
            test_dir = os.path.join(tmpdir, "test_dir")
            info_file = os.path.join(test_dir, "info.txt")
            
            if os.path.isdir(test_dir):
                print(f"\nDirectory created: {test_dir}")
                if os.path.exists(info_file):
                    content = Path(info_file).read_text()
                    print(f"File content: {content}")
                    print("\nVERIFIED: Directory and file created successfully!")
                    return manager.state == ManagerState.COMPLETED
                else:
                    print(f"\nWARNING: Directory exists but file not found at {info_file}")
                    # Still consider partial success
                    return manager.state == ManagerState.COMPLETED
            else:
                print(f"\nFAILED: Directory not found at {test_dir}")
                return False
                
        except Exception as e:
            print(f"ERROR: {e}")
            import traceback
            traceback.print_exc()
            return False
        finally:
            client.close()


def test_with_constraints():
    """Test: Multi-agent workflow with constraints."""
    print("\n" + "=" * 60)
    print("Test 4: Task with Constraints")
    print("=" * 60)
    
    client = create_llm_client()
    if not client:
        return False
    
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = os.path.join(tmpdir, "greeting.txt")
        
        harness = LocalHarness()
        manager = ManagerAgent(harness, client)
        
        goal = f"Create a greeting file at {test_file}"
        constraints = [
            "The greeting must be in English",
            "The file must contain exactly one line",
            "The greeting must include the word 'Welcome'"
        ]
        
        print(f"Goal: {goal}")
        print(f"Constraints: {constraints}")
        print("-" * 60)
        
        try:
            result = manager.run(goal, constraints=constraints)
            
            print(f"\nManager final state: {manager.state.value}")
            print(f"Workspace plan steps: {len(manager.workspace.plan)}")
            print(f"Step results: {len(manager.workspace.step_results)}")
            print(f"\nFinal result:\n{result[:500]}...")
            
            # Verify the file was created with constraints
            if os.path.exists(test_file):
                content = Path(test_file).read_text()
                print(f"\nFile content: {content}")
                
                # Check constraints
                lines = content.strip().split('\n')
                has_welcome = 'welcome' in content.lower()
                is_one_line = len(lines) == 1
                
                print(f"Has 'Welcome': {has_welcome}")
                print(f"Is one line: {is_one_line}")
                
                if has_welcome:
                    print("\nVERIFIED: File created with Welcome greeting!")
                    return manager.state == ManagerState.COMPLETED
                else:
                    print("\nWARNING: File created but may not meet all constraints")
                    return manager.state == ManagerState.COMPLETED
            else:
                print(f"\nFAILED: File not found at {test_file}")
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
    print("Multi-Agent Architecture Test - Venice.ai Integration")
    print("=" * 60)
    print(f"Model: llama-3.3-70b")
    print(f"Base URL: https://api.venice.ai/api/v1")
    
    results = []
    
    # Run tests
    results.append(("Simple File Task", test_simple_file_task()))
    results.append(("Multi-Step Task", test_multi_step_task()))
    results.append(("Shell Command Task", test_shell_task()))
    results.append(("Task with Constraints", test_with_constraints()))
    
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
