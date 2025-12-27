#!/usr/bin/env python3
"""Test evidence-based gating for fail_to_pass_status validation."""

import sys
import time
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

# Import directly from swe_workflow to avoid __init__ dependencies
import importlib.util
spec = importlib.util.spec_from_file_location("swe_workflow", Path(__file__).parent / "src" / "compymac" / "swe_workflow.py")
swe_workflow = importlib.util.module_from_spec(spec)
spec.loader.exec_module(swe_workflow)
SWEPhaseState = swe_workflow.SWEPhaseState

def test_evidence_gating():
    """Test that evidence-based gating prevents claiming all_passed without proof."""

    print("=" * 60)
    print("Testing Evidence-Based Gating (V4)")
    print("=" * 60)

    # Test 1: Claim all_passed without running tests
    print("\nTest 1: Agent claims all_passed without running tests")
    state = SWEPhaseState()
    is_valid, error_msg = state.validate_test_evidence("all_passed", "fail_to_pass")
    assert not is_valid, "Should reject claim without test evidence"
    assert "No evidence of running tests" in error_msg
    print(f"✓ PASS: {error_msg[:80]}...")

    # Test 2: Run tests but they fail
    print("\nTest 2: Agent runs tests but they fail (exit_code=1)")
    state = SWEPhaseState()
    state.record_bash_execution("pytest tests/test_foo.py", exit_code=1, timestamp=time.time())
    is_valid, error_msg = state.validate_test_evidence("all_passed", "fail_to_pass")
    assert not is_valid, "Should reject claim when tests failed"
    assert "exit_code=1" in error_msg
    print(f"✓ PASS: {error_msg[:80]}...")

    # Test 3: Run passing tests, then edit code
    print("\nTest 3: Agent runs passing tests, then edits code")
    state = SWEPhaseState()
    test_time = time.time()
    state.record_bash_execution("pytest tests/test_foo.py", exit_code=0, timestamp=test_time)
    time.sleep(0.01)  # Ensure edit is after test
    state.record_file_edit(timestamp=time.time())
    is_valid, error_msg = state.validate_test_evidence("all_passed", "fail_to_pass")
    assert not is_valid, "Should reject claim when code edited after tests"
    assert "edited after the last test run" in error_msg
    print(f"✓ PASS: {error_msg[:80]}...")

    # Test 4: Edit code, then run passing tests (correct workflow)
    print("\nTest 4: Agent edits code, then runs passing tests (correct)")
    state = SWEPhaseState()
    edit_time = time.time()
    state.record_file_edit(timestamp=edit_time)
    time.sleep(0.01)  # Ensure test is after edit
    state.record_bash_execution("pytest tests/test_foo.py", exit_code=0, timestamp=time.time())
    is_valid, error_msg = state.validate_test_evidence("all_passed", "fail_to_pass")
    assert is_valid, f"Should accept valid claim: {error_msg}"
    print(f"✓ PASS: Evidence validated successfully")

    # Test 5: Claim N_failed (should skip validation)
    print("\nTest 5: Agent claims '3_failed' (validation skipped)")
    state = SWEPhaseState()
    is_valid, error_msg = state.validate_test_evidence("3_failed", "fail_to_pass")
    assert is_valid, "Should not validate when not claiming all_passed"
    print(f"✓ PASS: Validation skipped for non-all_passed status")

    # Test 6: Various test command patterns
    print("\nTest 6: Validate various test command patterns")
    state = SWEPhaseState()
    test_commands = [
        "pytest",
        "python -m pytest tests/",
        "python test_foo.py",
        "npm test",
        "./run_tests.sh",
        "make test",
    ]
    for cmd in test_commands:
        state_temp = SWEPhaseState()
        state_temp.record_bash_execution(cmd, exit_code=0, timestamp=time.time())
        is_valid, _ = state_temp.validate_test_evidence("all_passed", "fail_to_pass")
        assert is_valid, f"Should recognize test command: {cmd}"
        print(f"  ✓ Recognized: {cmd}")

    print("\n" + "=" * 60)
    print("All tests passed! Evidence-based gating is working.")
    print("=" * 60)

if __name__ == "__main__":
    test_evidence_gating()
