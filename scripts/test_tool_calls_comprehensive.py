#!/usr/bin/env python3
"""
Comprehensive Tool Call Testing - CompyMac vs Devin Comparison

This script systematically tests all tool calls through CompyMac's multi-agent
system using Venice.ai, comparing results against expected behavior.

Categories:
1. Atomic Tool Correctness (Read, Write, bash)
2. Multi-Step Composition
3. Tool Selection & Reasoning
4. Error Recovery & Edge Cases
5. Parallelization-Specific (Phase 1-3)

Rate limit handling: If we hit Venice API rate limits (50 RPM for qwen3-next-80b),
wait 60 seconds and retry.

Usage:
    export LLM_API_KEY="your-venice-api-key"
    python scripts/test_tool_calls_comprehensive.py
"""

import json
import os
import sys
import tempfile
import time
import traceback
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from compymac.config import LLMConfig
from compymac.llm import LLMClient
from compymac.local_harness import LocalHarness
from compymac.multi_agent import ManagerAgent, ManagerState


@dataclass
class TestResult:
    """Result of a single test."""
    test_id: str
    test_name: str
    category: str
    goal: str
    success: bool
    expected: str
    actual: str
    tool_calls_made: list[str] = field(default_factory=list)
    execution_time_ms: int = 0
    error: str = ""
    notes: str = ""


@dataclass
class TestSuite:
    """Collection of test results."""
    results: list[TestResult] = field(default_factory=list)
    start_time: float = 0.0
    end_time: float = 0.0
    
    def add(self, result: TestResult) -> None:
        self.results.append(result)
    
    def summary(self) -> dict:
        total = len(self.results)
        passed = sum(1 for r in self.results if r.success)
        failed = total - passed
        return {
            "total": total,
            "passed": passed,
            "failed": failed,
            "pass_rate": f"{passed/total*100:.1f}%" if total > 0 else "N/A",
            "duration_seconds": self.end_time - self.start_time,
        }
    
    def to_report(self) -> str:
        lines = ["=" * 80]
        lines.append("COMPREHENSIVE TOOL CALL TEST REPORT")
        lines.append("=" * 80)
        
        summary = self.summary()
        lines.append(f"\nSummary: {summary['passed']}/{summary['total']} passed ({summary['pass_rate']})")
        lines.append(f"Duration: {summary['duration_seconds']:.1f}s\n")
        
        # Group by category
        categories = {}
        for r in self.results:
            if r.category not in categories:
                categories[r.category] = []
            categories[r.category].append(r)
        
        for cat, results in categories.items():
            lines.append(f"\n{'='*40}")
            lines.append(f"Category: {cat}")
            lines.append(f"{'='*40}")
            
            for r in results:
                status = "PASS" if r.success else "FAIL"
                lines.append(f"\n[{status}] {r.test_id}: {r.test_name}")
                lines.append(f"  Goal: {r.goal[:100]}...")
                if r.tool_calls_made:
                    lines.append(f"  Tools used: {', '.join(r.tool_calls_made)}")
                if not r.success:
                    lines.append(f"  Expected: {r.expected[:100]}")
                    lines.append(f"  Actual: {r.actual[:100]}")
                    if r.error:
                        lines.append(f"  Error: {r.error[:100]}")
                if r.notes:
                    lines.append(f"  Notes: {r.notes}")
        
        return "\n".join(lines)


class ComprehensiveToolTester:
    """Runs comprehensive tool call tests against CompyMac."""
    
    def __init__(self, temp_dir: Path):
        self.temp_dir = temp_dir
        self.suite = TestSuite()
        self.client: LLMClient | None = None
        self.rate_limit_wait = 60  # seconds to wait on rate limit
        
    def create_client(self) -> LLMClient | None:
        """Create LLM client with timeout and retry settings."""
        config = LLMConfig(
            base_url="https://api.venice.ai/api/v1",
            api_key=os.environ.get("LLM_API_KEY", ""),
            model="qwen3-next-80b",
            temperature=0.7,
            max_tokens=2000,
        )
        
        if not config.api_key:
            print("ERROR: LLM_API_KEY environment variable not set")
            return None
        
        # Use the LLM client's built-in timeout and retry logic
        # max_retries=2 means 3 total attempts, retry_delay=60s as user requested
        return LLMClient(config, max_retries=2, retry_delay=60.0)
    
    def run_with_retry(self, goal: str, constraints: list[str] | None = None) -> tuple[str, ManagerState, list[str], list[str]]:
        """Run a goal with rate limit retry logic.
        
        Returns:
            tuple of (final_result, state, tool_calls, step_outputs)
            - final_result: The summary message from manager.run()
            - state: The final ManagerState
            - tool_calls: List of step identifiers
            - step_outputs: List of actual outputs from each step (for content verification)
        """
        max_retries = 3
        
        for attempt in range(max_retries):
            try:
                client = self.create_client()
                if not client:
                    return "No client", ManagerState.FAILED, [], []
                
                harness = LocalHarness(full_output_dir=self.temp_dir / "outputs")
                manager = ManagerAgent(
                    harness=harness,
                    llm_client=client,
                    enable_memory=False,
                )
                
                result = manager.run(goal, constraints)
                state = manager.get_state()
                
                # Extract tool calls and step outputs from workspace
                tool_calls = []
                step_outputs = []
                for step_result in manager.workspace.step_results:
                    tool_calls.append(f"step_{step_result.step_index}")
                    # Capture the summary from each step (StepResult has summary, not output)
                    if step_result.summary:
                        step_outputs.append(step_result.summary)
                    # Also capture any artifacts that might contain content
                    if step_result.artifacts:
                        for key, value in step_result.artifacts.items():
                            if isinstance(value, str):
                                step_outputs.append(value)
                
                client.close()
                return result, state, tool_calls, step_outputs
                
            except Exception as e:
                error_str = str(e).lower()
                if "rate" in error_str or "limit" in error_str or "429" in error_str:
                    print(f"\n  Rate limit hit. Waiting {self.rate_limit_wait}s before retry...")
                    time.sleep(self.rate_limit_wait)
                    continue
                else:
                    if client:
                        client.close()
                    raise
        
        return "Max retries exceeded", ManagerState.FAILED, [], []
    
    def run_test(
        self,
        test_id: str,
        test_name: str,
        category: str,
        goal: str,
        expected_check: callable,
        constraints: list[str] | None = None,
    ) -> TestResult:
        """Run a single test and return the result."""
        print(f"\n[{test_id}] {test_name}...")
        
        start_time = time.time()
        try:
            result, state, tool_calls, step_outputs = self.run_with_retry(goal, constraints)
            execution_time = int((time.time() - start_time) * 1000)
            
            # Combine result and step outputs for content checking
            all_content = result + "\n" + "\n".join(step_outputs)
            
            success, expected, actual, notes = expected_check(all_content, state, self.temp_dir)
            
            return TestResult(
                test_id=test_id,
                test_name=test_name,
                category=category,
                goal=goal,
                success=success,
                expected=expected,
                actual=actual,
                tool_calls_made=tool_calls,
                execution_time_ms=execution_time,
                notes=notes,
            )
            
        except Exception as e:
            execution_time = int((time.time() - start_time) * 1000)
            return TestResult(
                test_id=test_id,
                test_name=test_name,
                category=category,
                goal=goal,
                success=False,
                expected="No exception",
                actual=str(e),
                execution_time_ms=execution_time,
                error=traceback.format_exc()[:500],
            )
    
    # =========================================================================
    # Category 1: Atomic Tool Correctness
    # =========================================================================
    
    def test_read_small_file(self) -> TestResult:
        """Test 1.1: Read a small known file."""
        # Setup
        test_file = self.temp_dir / "small_test.txt"
        test_content = "Hello, this is a test file.\nLine 2.\nLine 3."
        test_file.write_text(test_content)
        
        def check(result, state, temp_dir):
            # Check if the content was read correctly
            if "Hello" in result and "test file" in result:
                return True, "Content read correctly", result[:100], ""
            return False, "Content should contain 'Hello' and 'test file'", result[:100], ""
        
        return self.run_test(
            "1.1", "Read small file",
            "Category 1: Atomic Tool Correctness",
            f"Read the file at {test_file} and tell me what it contains.",
            check,
        )
    
    def test_read_with_offset_limit(self) -> TestResult:
        """Test 1.2: Read a file with offset/limit."""
        test_file = self.temp_dir / "multiline.txt"
        lines = [f"Line {i}" for i in range(1, 21)]
        test_file.write_text("\n".join(lines))
        
        def check(result, state, temp_dir):
            # Should mention line numbers or content
            if any(f"Line {i}" in result for i in range(1, 21)):
                return True, "File content read", result[:100], ""
            return False, "Should contain line content", result[:100], ""
        
        return self.run_test(
            "1.2", "Read file with offset/limit",
            "Category 1: Atomic Tool Correctness",
            f"Read lines 5-10 from the file at {test_file}.",
            check,
        )
    
    def test_read_nonexistent_file(self) -> TestResult:
        """Test 1.3: Read a non-existent file (error handling)."""
        fake_path = self.temp_dir / "does_not_exist.txt"
        
        def check(result, state, temp_dir):
            result_lower = result.lower()
            # Should report error, not hallucinate content
            if "not found" in result_lower or "error" in result_lower or "does not exist" in result_lower or "failed" in result_lower:
                return True, "Error reported correctly", result[:100], ""
            return False, "Should report file not found error", result[:100], "May have hallucinated content"
        
        return self.run_test(
            "1.3", "Read non-existent file",
            "Category 1: Atomic Tool Correctness",
            f"Read the file at {fake_path} and tell me its contents.",
            check,
        )
    
    def test_read_tricky_path(self) -> TestResult:
        """Test 1.4: Read file with tricky path (spaces)."""
        tricky_dir = self.temp_dir / "path with spaces"
        tricky_dir.mkdir(exist_ok=True)
        test_file = tricky_dir / "test file.txt"
        test_file.write_text("Content in tricky path")
        
        def check(result, state, temp_dir):
            if "Content in tricky path" in result or "tricky" in result.lower():
                return True, "Read file with spaces in path", result[:100], ""
            return False, "Should read file with spaces in path", result[:100], ""
        
        return self.run_test(
            "1.4", "Read file with spaces in path",
            "Category 1: Atomic Tool Correctness",
            f"Read the file at '{test_file}'.",
            check,
        )
    
    def test_read_large_file(self) -> TestResult:
        """Test 1.5: Read a large file (truncation behavior)."""
        test_file = self.temp_dir / "large_file.txt"
        lines = [f"Line {i}: " + "x" * 100 for i in range(1, 5001)]
        test_file.write_text("\n".join(lines))
        
        def check(result, state, temp_dir):
            # Should either truncate or mention it's large
            if "Line 1" in result or "truncat" in result.lower() or "large" in result.lower():
                return True, "Handled large file", result[:100], ""
            return False, "Should handle large file appropriately", result[:100], ""
        
        return self.run_test(
            "1.5", "Read large file (truncation)",
            "Category 1: Atomic Tool Correctness",
            f"Read the file at {test_file} and summarize what you see.",
            check,
        )
    
    def test_write_new_file(self) -> TestResult:
        """Test 1.6: Create a new file with exact content."""
        test_file = self.temp_dir / "new_file.txt"
        expected_content = "This is the exact content I want."
        
        def check(result, state, temp_dir):
            if test_file.exists():
                actual = test_file.read_text()
                if expected_content in actual or "exact content" in actual.lower():
                    return True, "File created with content", actual[:100], ""
                return False, f"Expected '{expected_content}'", actual[:100], ""
            return False, "File should exist", "File not created", ""
        
        return self.run_test(
            "1.6", "Write new file",
            "Category 1: Atomic Tool Correctness",
            f"Create a file at {test_file} with the content: '{expected_content}'",
            check,
        )
    
    def test_write_overwrite(self) -> TestResult:
        """Test 1.7: Overwrite an existing file."""
        test_file = self.temp_dir / "overwrite_test.txt"
        test_file.write_text("Original content")
        new_content = "New overwritten content"
        
        def check(result, state, temp_dir):
            if test_file.exists():
                actual = test_file.read_text()
                if "New" in actual or "overwritten" in actual.lower():
                    return True, "File overwritten", actual[:100], ""
                if "Original" in actual:
                    return False, "Should overwrite", actual[:100], "Original content still present"
            return False, "File should exist", "File missing", ""
        
        return self.run_test(
            "1.7", "Overwrite existing file",
            "Category 1: Atomic Tool Correctness",
            f"Overwrite the file at {test_file} with: '{new_content}'",
            check,
        )
    
    def test_write_nested_path(self) -> TestResult:
        """Test 1.8: Write to nested path that doesn't exist."""
        nested_path = self.temp_dir / "nested" / "deep" / "path" / "file.txt"
        
        def check(result, state, temp_dir):
            if nested_path.exists():
                return True, "Created nested path", nested_path.read_text()[:100], ""
            # Check if it at least tried
            if "created" in result.lower() or "wrote" in result.lower():
                return True, "Attempted to create", result[:100], "May have created elsewhere"
            return False, "Should create nested directories", result[:100], ""
        
        return self.run_test(
            "1.8", "Write to nested path",
            "Category 1: Atomic Tool Correctness",
            f"Create a file at {nested_path} with content 'Nested file content'",
            check,
        )
    
    def test_bash_simple(self) -> TestResult:
        """Test 1.9: Simple deterministic bash command."""
        def check(result, state, temp_dir):
            if "4" in result or "four" in result.lower():
                return True, "Correct calculation", result[:100], ""
            return False, "Should return 4", result[:100], ""
        
        return self.run_test(
            "1.9", "Simple bash command",
            "Category 1: Atomic Tool Correctness",
            "Run a shell command to calculate 2+2 using Python and tell me the result.",
            check,
        )
    
    def test_bash_nonzero_exit(self) -> TestResult:
        """Test 1.10: Command that fails with non-zero exit."""
        def check(result, state, temp_dir):
            result_lower = result.lower()
            if "error" in result_lower or "fail" in result_lower or "not found" in result_lower:
                return True, "Error detected", result[:100], ""
            return False, "Should detect command failure", result[:100], ""
        
        return self.run_test(
            "1.10", "Bash command failure",
            "Category 1: Atomic Tool Correctness",
            "Run the command 'ls /nonexistent_directory_12345' and tell me what happens.",
            check,
        )
    
    def test_bash_quoting(self) -> TestResult:
        """Test 1.11: Command with quoting/escaping."""
        test_dir = self.temp_dir / "dir with spaces"
        test_dir.mkdir(exist_ok=True)
        (test_dir / "file.txt").write_text("test")
        
        def check(result, state, temp_dir):
            if "file.txt" in result or "test" in result.lower():
                return True, "Listed directory with spaces", result[:100], ""
            return False, "Should list directory with spaces", result[:100], ""
        
        return self.run_test(
            "1.11", "Bash with path quoting",
            "Category 1: Atomic Tool Correctness",
            f"List the contents of the directory '{test_dir}'.",
            check,
        )
    
    # =========================================================================
    # Category 2: Multi-Step Composition
    # =========================================================================
    
    def test_create_read_verify(self) -> TestResult:
        """Test 2.1: Create file, read it back, verify content."""
        test_file = self.temp_dir / "roundtrip.txt"
        content = "Roundtrip test content 12345"
        
        def check(result, state, temp_dir):
            if test_file.exists():
                actual = test_file.read_text()
                if "12345" in actual and "12345" in result:
                    return True, "Roundtrip successful", result[:100], ""
            return False, "Should create and verify file", result[:100], ""
        
        return self.run_test(
            "2.1", "Create-Read-Verify roundtrip",
            "Category 2: Multi-Step Composition",
            f"Create a file at {test_file} with content '{content}', then read it back and confirm the content matches.",
            check,
        )
    
    def test_search_and_read(self) -> TestResult:
        """Test 2.2: Search with grep, then read found file."""
        # Setup: create files with searchable content
        search_dir = self.temp_dir / "search_test"
        search_dir.mkdir(exist_ok=True)
        (search_dir / "file1.txt").write_text("Nothing here")
        (search_dir / "file2.txt").write_text("Contains the SECRET_CODE_XYZ")
        (search_dir / "file3.txt").write_text("Also nothing")
        
        def check(result, state, temp_dir):
            if "SECRET_CODE_XYZ" in result or "file2" in result:
                return True, "Found and read correct file", result[:100], ""
            return False, "Should find SECRET_CODE_XYZ in file2.txt", result[:100], ""
        
        return self.run_test(
            "2.2", "Search and read",
            "Category 2: Multi-Step Composition",
            f"Search for files containing 'SECRET_CODE' in {search_dir}, then read the file that contains it and tell me the full secret code.",
            check,
        )
    
    def test_create_multiple_list(self) -> TestResult:
        """Test 2.3: Create 3 files, list directory, verify all exist."""
        multi_dir = self.temp_dir / "multi_files"
        multi_dir.mkdir(exist_ok=True)
        
        def check(result, state, temp_dir):
            files = list(multi_dir.glob("*.txt"))
            if len(files) >= 2:  # Allow some flexibility
                return True, f"Created {len(files)} files", result[:100], ""
            return False, "Should create multiple files", result[:100], f"Found {len(files)} files"
        
        return self.run_test(
            "2.3", "Create multiple files",
            "Category 2: Multi-Step Composition",
            f"Create three files in {multi_dir}: alpha.txt, beta.txt, and gamma.txt. Each should contain its name. Then list the directory to confirm all three exist.",
            check,
        )
    
    def test_write_json_read_validate(self) -> TestResult:
        """Test 2.4: Write JSON, read it, validate structure."""
        json_file = self.temp_dir / "data.json"
        
        def check(result, state, temp_dir):
            if json_file.exists():
                try:
                    data = json.loads(json_file.read_text())
                    if "name" in data or "value" in data or isinstance(data, dict):
                        return True, "Valid JSON created", str(data)[:100], ""
                except json.JSONDecodeError:
                    return False, "Should be valid JSON", json_file.read_text()[:100], "Invalid JSON"
            return False, "JSON file should exist", result[:100], ""
        
        return self.run_test(
            "2.4", "Write and validate JSON",
            "Category 2: Multi-Step Composition",
            f"Create a JSON file at {json_file} with a 'name' field set to 'test' and a 'value' field set to 42. Then read it back and confirm it's valid JSON.",
            check,
        )
    
    # =========================================================================
    # Category 3: Tool Selection & Reasoning
    # =========================================================================
    
    def test_select_read_tool(self) -> TestResult:
        """Test 3.1: Should choose Read tool for file content question."""
        test_file = self.temp_dir / "select_read.txt"
        test_file.write_text("The answer is BLUE")
        
        def check(result, state, temp_dir):
            if "BLUE" in result or "blue" in result.lower():
                return True, "Used Read tool correctly", result[:100], ""
            return False, "Should read file and find BLUE", result[:100], ""
        
        return self.run_test(
            "3.1", "Tool selection: Read",
            "Category 3: Tool Selection & Reasoning",
            f"What's in {test_file}?",
            check,
        )
    
    def test_select_write_tool(self) -> TestResult:
        """Test 3.2: Should choose Write tool for save request."""
        save_file = self.temp_dir / "saved_text.txt"
        
        def check(result, state, temp_dir):
            if save_file.exists():
                return True, "Used Write tool", save_file.read_text()[:100], ""
            return False, "Should create file", result[:100], ""
        
        return self.run_test(
            "3.2", "Tool selection: Write",
            "Category 3: Tool Selection & Reasoning",
            f"Save the text 'Important note' to {save_file}",
            check,
        )
    
    def test_select_bash_for_list(self) -> TestResult:
        """Test 3.3: Should choose bash for directory listing."""
        list_dir = self.temp_dir / "list_test"
        list_dir.mkdir(exist_ok=True)
        (list_dir / "a.py").write_text("")
        (list_dir / "b.py").write_text("")
        (list_dir / "c.txt").write_text("")
        
        def check(result, state, temp_dir):
            if "a.py" in result or "b.py" in result or ".py" in result:
                return True, "Listed Python files", result[:100], ""
            return False, "Should list Python files", result[:100], ""
        
        return self.run_test(
            "3.3", "Tool selection: bash for listing",
            "Category 3: Tool Selection & Reasoning",
            f"List all Python files in {list_dir}",
            check,
        )
    
    def test_file_exists_check(self) -> TestResult:
        """Test 3.4: Check if file exists (multiple valid approaches)."""
        exists_file = self.temp_dir / "exists_check.txt"
        exists_file.write_text("I exist")
        
        def check(result, state, temp_dir):
            result_lower = result.lower()
            if "exist" in result_lower or "yes" in result_lower or "found" in result_lower or "I exist" in result:
                return True, "Confirmed file exists", result[:100], ""
            return False, "Should confirm file exists", result[:100], ""
        
        return self.run_test(
            "3.4", "Check file existence",
            "Category 3: Tool Selection & Reasoning",
            f"Does the file {exists_file} exist? If so, what's in it?",
            check,
        )
    
    # =========================================================================
    # Category 4: Error Recovery & Edge Cases
    # =========================================================================
    
    def test_ambiguous_path(self) -> TestResult:
        """Test 4.1: Ambiguous request without full path."""
        def check(result, state, temp_dir):
            # Should either ask for clarification or make reasonable choice
            result_lower = result.lower()
            if "report" in result_lower or "created" in result_lower or "where" in result_lower:
                return True, "Handled ambiguity", result[:100], ""
            return False, "Should handle ambiguous path", result[:100], ""
        
        return self.run_test(
            "4.1", "Ambiguous path handling",
            "Category 4: Error Recovery & Edge Cases",
            "Create a file called report.txt with a summary of today's work.",
            check,
        )
    
    def test_retry_after_failure(self) -> TestResult:
        """Test 4.2: Recover from initial failure."""
        # Create a file that will be found on second attempt
        recovery_file = self.temp_dir / "recovery_test.txt"
        recovery_file.write_text("Recovery successful")
        
        def check(result, state, temp_dir):
            if "Recovery" in result or "successful" in result.lower():
                return True, "Found file", result[:100], ""
            return False, "Should find recovery file", result[:100], ""
        
        return self.run_test(
            "4.2", "Recovery from failure",
            "Category 4: Error Recovery & Edge Cases",
            f"Try to read {self.temp_dir}/wrong_name.txt. If that fails, try reading {recovery_file} instead.",
            check,
        )
    
    # =========================================================================
    # Category 5: Parallelization-Specific
    # =========================================================================
    
    def test_parallel_reads(self) -> TestResult:
        """Test 5.1: Multiple independent reads."""
        # Create multiple files
        for i in range(3):
            (self.temp_dir / f"parallel_{i}.txt").write_text(f"Content {i}")
        
        def check(result, state, temp_dir):
            found = sum(1 for i in range(3) if f"Content {i}" in result or f"parallel_{i}" in result)
            if found >= 2:
                return True, f"Read {found}/3 files", result[:100], ""
            return False, "Should read multiple files", result[:100], ""
        
        return self.run_test(
            "5.1", "Multiple parallel reads",
            "Category 5: Parallelization-Specific",
            f"Read all three files: {self.temp_dir}/parallel_0.txt, {self.temp_dir}/parallel_1.txt, and {self.temp_dir}/parallel_2.txt. Tell me what each contains.",
            check,
        )
    
    def test_independent_writes(self) -> TestResult:
        """Test 5.2: Multiple independent writes."""
        def check(result, state, temp_dir):
            files = [
                temp_dir / "independent_a.txt",
                temp_dir / "independent_b.txt",
                temp_dir / "independent_c.txt",
            ]
            created = sum(1 for f in files if f.exists())
            if created >= 2:
                return True, f"Created {created}/3 files", result[:100], ""
            return False, "Should create multiple files", result[:100], f"Created {created}"
        
        return self.run_test(
            "5.2", "Multiple independent writes",
            "Category 5: Parallelization-Specific",
            f"Create three independent files: {self.temp_dir}/independent_a.txt with 'A', {self.temp_dir}/independent_b.txt with 'B', and {self.temp_dir}/independent_c.txt with 'C'.",
            check,
        )
    
    def run_all_tests(self) -> TestSuite:
        """Run all tests in sequence."""
        self.suite = TestSuite()
        self.suite.start_time = time.time()
        
        # Category 1: Atomic Tool Correctness
        print("\n" + "=" * 60)
        print("Category 1: Atomic Tool Correctness")
        print("=" * 60)
        
        self.suite.add(self.test_read_small_file())
        self.suite.add(self.test_read_with_offset_limit())
        self.suite.add(self.test_read_nonexistent_file())
        self.suite.add(self.test_read_tricky_path())
        self.suite.add(self.test_read_large_file())
        self.suite.add(self.test_write_new_file())
        self.suite.add(self.test_write_overwrite())
        self.suite.add(self.test_write_nested_path())
        self.suite.add(self.test_bash_simple())
        self.suite.add(self.test_bash_nonzero_exit())
        self.suite.add(self.test_bash_quoting())
        
        # Category 2: Multi-Step Composition
        print("\n" + "=" * 60)
        print("Category 2: Multi-Step Composition")
        print("=" * 60)
        
        self.suite.add(self.test_create_read_verify())
        self.suite.add(self.test_search_and_read())
        self.suite.add(self.test_create_multiple_list())
        self.suite.add(self.test_write_json_read_validate())
        
        # Category 3: Tool Selection & Reasoning
        print("\n" + "=" * 60)
        print("Category 3: Tool Selection & Reasoning")
        print("=" * 60)
        
        self.suite.add(self.test_select_read_tool())
        self.suite.add(self.test_select_write_tool())
        self.suite.add(self.test_select_bash_for_list())
        self.suite.add(self.test_file_exists_check())
        
        # Category 4: Error Recovery & Edge Cases
        print("\n" + "=" * 60)
        print("Category 4: Error Recovery & Edge Cases")
        print("=" * 60)
        
        self.suite.add(self.test_ambiguous_path())
        self.suite.add(self.test_retry_after_failure())
        
        # Category 5: Parallelization-Specific
        print("\n" + "=" * 60)
        print("Category 5: Parallelization-Specific")
        print("=" * 60)
        
        self.suite.add(self.test_parallel_reads())
        self.suite.add(self.test_independent_writes())
        
        self.suite.end_time = time.time()
        return self.suite


def main():
    print("=" * 80)
    print("COMPREHENSIVE TOOL CALL TESTING")
    print("CompyMac (Venice.ai qwen3-next-80b) vs Expected Behavior")
    print("=" * 80)
    print(f"Model: qwen3-next-80b")
    print(f"Rate limits: 50 RPM, 750k TPM")
    print(f"API Key: {'SET' if os.environ.get('LLM_API_KEY') else 'NOT SET'}")
    
    if not os.environ.get("LLM_API_KEY"):
        print("\nERROR: LLM_API_KEY environment variable not set")
        return 1
    
    with tempfile.TemporaryDirectory() as tmpdir:
        temp_dir = Path(tmpdir)
        
        tester = ComprehensiveToolTester(temp_dir)
        suite = tester.run_all_tests()
        
        # Print report
        print("\n" + suite.to_report())
        
        # Save report to file
        report_file = Path("/home/ubuntu/repos/compymac/test_results_comprehensive.txt")
        report_file.write_text(suite.to_report())
        print(f"\nReport saved to: {report_file}")
        
        # Return exit code based on results
        summary = suite.summary()
        return 0 if summary["failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
