"""
Tests for the Tool Verification Framework.

These tests verify that the contract-driven verification system correctly
detects false-success failures and provides accurate verification results.
"""

import os
import tempfile

from compymac.types import ToolCall, ToolResult
from compymac.verification import (
    BashVerifier,
    BrowserActionVerifier,
    ConditionResult,
    FileEditVerifier,
    FileWriteVerifier,
    VerificationEngine,
    VerificationResult,
    VerificationStrategy,
)


class TestBashVerifier:
    """Tests for BashVerifier."""

    def test_create_contract_basic(self):
        """Test creating a basic bash contract."""
        verifier = BashVerifier()
        contract = verifier.create_contract(command="ls -la")

        assert contract.tool_name == "bash"
        assert contract.arguments["command"] == "ls -la"
        assert contract.verification_strategy == VerificationStrategy.EXIT_CODE
        assert len(contract.postconditions) == 1
        assert contract.postconditions[0].check_type == "exit_code"

    def test_create_contract_pytest(self):
        """Test creating a contract for pytest command."""
        verifier = BashVerifier()
        contract = verifier.create_contract(command="pytest tests/")

        assert len(contract.postconditions) == 2
        check_types = [p.check_type for p in contract.postconditions]
        assert "exit_code" in check_types
        assert "output_pattern" in check_types

    def test_create_contract_build(self):
        """Test creating a contract for build command."""
        verifier = BashVerifier()
        contract = verifier.create_contract(command="npm run build")

        assert len(contract.postconditions) == 2
        check_types = [p.check_type for p in contract.postconditions]
        assert "exit_code" in check_types
        assert "no_error_pattern" in check_types

    def test_verify_success(self):
        """Test verifying a successful bash command."""
        verifier = BashVerifier()
        contract = verifier.create_contract(command="echo hello")

        result = ToolResult(
            tool_call_id="test_1",
            content="hello\n(return code = 0)",
            success=True,
        )

        verification = verifier.verify(contract, result)

        assert verification.all_checks_passed
        assert verification.confidence_score == 1.0
        assert len(verification.condition_results) == 1

    def test_verify_failure_exit_code(self):
        """Test verifying a failed bash command (non-zero exit)."""
        verifier = BashVerifier()
        contract = verifier.create_contract(command="false")

        result = ToolResult(
            tool_call_id="test_2",
            content="(return code = 1)",
            success=True,
        )

        verification = verifier.verify(contract, result)

        assert not verification.all_checks_passed
        assert verification.confidence_score == 0.0
        assert "Exit code 1 != 0" in verification.condition_results[0].error_message

    def test_verify_pytest_output(self):
        """Test verifying pytest output patterns."""
        verifier = BashVerifier()
        contract = verifier.create_contract(command="pytest tests/")

        result = ToolResult(
            tool_call_id="test_3",
            content="===== 5 passed in 1.23s =====\n(return code = 0)",
            success=True,
        )

        verification = verifier.verify(contract, result)

        assert verification.all_checks_passed
        assert verification.confidence_score == 1.0

    def test_verify_build_with_errors(self):
        """Test verifying build output with errors."""
        verifier = BashVerifier()
        contract = verifier.create_contract(command="npm run build")

        result = ToolResult(
            tool_call_id="test_4",
            content="error: Cannot find module 'foo'\n(return code = 0)",
            success=True,
        )

        verification = verifier.verify(contract, result)

        assert not verification.all_checks_passed


class TestFileEditVerifier:
    """Tests for FileEditVerifier."""

    def test_create_contract(self):
        """Test creating a file edit contract."""
        verifier = FileEditVerifier()
        contract = verifier.create_contract(
            file_path="/tmp/test.py",
            old_string="def foo():",
            new_string="def bar():",
        )

        assert contract.tool_name == "Edit"
        assert len(contract.preconditions) == 2
        assert len(contract.postconditions) == 3
        assert contract.verification_strategy == VerificationStrategy.CONTENT_MATCH

    def test_check_preconditions_file_exists(self):
        """Test checking preconditions when file exists."""
        verifier = FileEditVerifier()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("def foo():\n    pass\n")
            temp_path = f.name

        try:
            contract = verifier.create_contract(
                file_path=temp_path,
                old_string="def foo():",
                new_string="def bar():",
            )

            result = verifier.check_preconditions(contract)

            assert result.all_satisfied
            assert len(result.results) == 2
        finally:
            os.unlink(temp_path)

    def test_check_preconditions_file_not_exists(self):
        """Test checking preconditions when file doesn't exist."""
        verifier = FileEditVerifier()
        contract = verifier.create_contract(
            file_path="/nonexistent/path/file.py",
            old_string="def foo():",
            new_string="def bar():",
        )

        result = verifier.check_preconditions(contract)

        assert not result.all_satisfied
        assert len(result.failed_conditions) > 0

    def test_verify_successful_edit(self):
        """Test verifying a successful file edit."""
        verifier = FileEditVerifier()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("def bar():\n    pass\n")
            temp_path = f.name

        try:
            contract = verifier.create_contract(
                file_path=temp_path,
                old_string="def foo():",
                new_string="def bar():",
            )

            result = ToolResult(
                tool_call_id="test_5",
                content="File edited successfully",
                success=True,
            )

            verification = verifier.verify(contract, result)

            assert verification.condition_results[0].satisfied
        finally:
            os.unlink(temp_path)

    def test_verify_syntax_error(self):
        """Test verifying a file with syntax error."""
        verifier = FileEditVerifier()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("def bar(\n    pass\n")
            temp_path = f.name

        try:
            contract = verifier.create_contract(
                file_path=temp_path,
                old_string="def foo():",
                new_string="def bar(",
            )

            result = ToolResult(
                tool_call_id="test_6",
                content="File edited successfully",
                success=True,
            )

            verification = verifier.verify(contract, result)

            syntax_check = [r for r in verification.condition_results if "syntax" in r.error_message.lower() or r.expected_value == "valid"]
            assert len(syntax_check) > 0
            assert not syntax_check[0].satisfied
        finally:
            os.unlink(temp_path)


class TestFileWriteVerifier:
    """Tests for FileWriteVerifier."""

    def test_create_contract(self):
        """Test creating a file write contract."""
        verifier = FileWriteVerifier()
        contract = verifier.create_contract(
            file_path="/tmp/test.txt",
            content="Hello, World!",
        )

        assert contract.tool_name == "Write"
        assert len(contract.postconditions) == 3
        assert contract.verification_strategy == VerificationStrategy.CONTENT_MATCH

    def test_verify_successful_write(self):
        """Test verifying a successful file write."""
        verifier = FileWriteVerifier()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("Hello, World!")
            temp_path = f.name

        try:
            contract = verifier.create_contract(
                file_path=temp_path,
                content="Hello, World!",
            )

            result = ToolResult(
                tool_call_id="test_7",
                content="File written successfully",
                success=True,
            )

            verification = verifier.verify(contract, result)

            assert verification.all_checks_passed
        finally:
            os.unlink(temp_path)


class TestBrowserActionVerifier:
    """Tests for BrowserActionVerifier."""

    def test_create_contract_click(self):
        """Test creating a click action contract."""
        verifier = BrowserActionVerifier()
        contract = verifier.create_contract(
            action="click",
            devinid="submit-button",
        )

        assert contract.tool_name == "browser_click"
        assert len(contract.postconditions) >= 1
        assert contract.verification_strategy == VerificationStrategy.DOM_STATE

    def test_create_contract_navigate(self):
        """Test creating a navigate action contract."""
        verifier = BrowserActionVerifier()
        contract = verifier.create_contract(
            action="navigate",
            url="https://example.com",
        )

        assert contract.tool_name == "browser_navigate"
        assert len(contract.postconditions) == 1
        assert contract.postconditions[0].check_type == "page_loaded"

    def test_verify_without_browser_state(self):
        """Test verifying without browser state (fallback)."""
        verifier = BrowserActionVerifier()
        contract = verifier.create_contract(
            action="click",
            devinid="button-1",
        )

        result = ToolResult(
            tool_call_id="test_8",
            content="Clicked element",
            success=True,
        )

        verification = verifier.verify(contract, result)

        assert verification.confidence_score == 0.5


class TestVerificationEngine:
    """Tests for VerificationEngine."""

    def test_get_verifier(self):
        """Test getting verifiers for different tools."""
        engine = VerificationEngine()

        assert engine.get_verifier("bash") is not None
        assert engine.get_verifier("Edit") is not None
        assert engine.get_verifier("Write") is not None
        assert engine.get_verifier("browser_click") is not None
        assert engine.get_verifier("unknown_tool") is None

    def test_create_contract(self):
        """Test creating contracts through the engine."""
        engine = VerificationEngine()

        tool_call = ToolCall(
            id="test_9",
            name="bash",
            arguments={"command": "echo hello"},
        )

        contract = engine.create_contract(tool_call)

        assert contract is not None
        assert contract.tool_name == "bash"

    def test_verify_through_engine(self):
        """Test verification through the engine."""
        engine = VerificationEngine()

        tool_call = ToolCall(
            id="test_10",
            name="bash",
            arguments={"command": "echo hello"},
        )

        result = ToolResult(
            tool_call_id="test_10",
            content="hello\n(return code = 0)",
            success=True,
        )

        verification = engine.verify(tool_call, result)

        assert verification is not None
        assert verification.all_checks_passed

    def test_disabled_engine(self):
        """Test that disabled engine returns None."""
        engine = VerificationEngine(enabled=False)

        tool_call = ToolCall(
            id="test_11",
            name="bash",
            arguments={"command": "echo hello"},
        )

        result = ToolResult(
            tool_call_id="test_11",
            content="hello",
            success=True,
        )

        verification = engine.verify(tool_call, result)

        assert verification is None


class TestVerificationResult:
    """Tests for VerificationResult."""

    def test_failure_summary(self):
        """Test failure summary generation."""
        result = VerificationResult(
            tool_name="bash",
            all_checks_passed=False,
            condition_results=[
                ConditionResult(
                    satisfied=False,
                    actual_value=1,
                    expected_value=0,
                    error_message="Exit code 1 != 0",
                ),
                ConditionResult(
                    satisfied=True,
                    actual_value="present",
                    expected_value="present",
                    error_message="",
                ),
            ],
        )

        summary = result.failure_summary()
        assert "Exit code 1 != 0" in summary

    def test_format_for_agent(self):
        """Test formatting for agent consumption."""
        result = VerificationResult(
            tool_name="bash",
            all_checks_passed=False,
            condition_results=[
                ConditionResult(
                    satisfied=False,
                    actual_value=1,
                    expected_value=0,
                    error_message="Exit code 1 != 0",
                    evidence={"stdout_preview": "error output"},
                ),
            ],
        )

        formatted = result.format_for_agent()
        assert "[FAIL]" in formatted
        assert "Exit code 1 != 0" in formatted

    def test_to_dict(self):
        """Test serialization to dict."""
        result = VerificationResult(
            tool_name="bash",
            all_checks_passed=True,
            condition_results=[],
            confidence_score=1.0,
        )

        d = result.to_dict()
        assert d["tool_name"] == "bash"
        assert d["all_checks_passed"] is True
        assert d["confidence_score"] == 1.0
