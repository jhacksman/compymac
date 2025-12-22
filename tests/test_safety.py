"""
Tests for the Safety Policy Layer.

These tests verify that the safety policies correctly detect and block
dangerous operations while allowing legitimate tool calls.
"""

import os
import tempfile

from compymac.safety import (
    FilesystemChecker,
    NetworkChecker,
    PolicyEngine,
    PolicySeverity,
    SecretsRedactor,
)
from compymac.types import ToolCall, ToolResult


class TestFilesystemChecker:
    """Tests for FilesystemChecker."""

    def test_allowlist_valid_path(self):
        """Test that valid paths pass the allowlist check."""
        checker = FilesystemChecker()
        tool_call = ToolCall(
            id="test_1",
            name="Read",
            arguments={"file_path": "/home/ubuntu/repos/test.py"},
        )

        result = checker.check(
            tool_call,
            {
                "check_type": "allowlist",
                "allowed_prefixes": ["/home/ubuntu", "/tmp"],
                "denied_patterns": [],
            },
        )

        assert result.passed
        assert result.severity == PolicySeverity.ADVISORY

    def test_allowlist_denied_path(self):
        """Test that paths outside allowlist are denied."""
        checker = FilesystemChecker()
        tool_call = ToolCall(
            id="test_2",
            name="Read",
            arguments={"file_path": "/etc/passwd"},
        )

        result = checker.check(
            tool_call,
            {
                "check_type": "allowlist",
                "allowed_prefixes": ["/home/ubuntu", "/tmp"],
                "denied_patterns": [],
            },
        )

        assert not result.passed
        assert result.severity == PolicySeverity.BLOCK

    def test_denied_pattern_match(self):
        """Test that denied patterns are blocked."""
        checker = FilesystemChecker()
        tool_call = ToolCall(
            id="test_3",
            name="Read",
            arguments={"file_path": "/home/ubuntu/.ssh/id_rsa"},
        )

        result = checker.check(
            tool_call,
            {
                "check_type": "allowlist",
                "allowed_prefixes": ["/home/ubuntu"],
                "denied_patterns": [r".*\.ssh/.*"],
            },
        )

        assert not result.passed
        assert ".ssh" in result.violation_message

    def test_blocklist_rm_rf_root(self):
        """Test that rm -rf / is blocked."""
        checker = FilesystemChecker()
        tool_call = ToolCall(
            id="test_4",
            name="bash",
            arguments={"command": "rm -rf /"},
        )

        result = checker.check(
            tool_call,
            {
                "check_type": "blocklist",
                "blocked_patterns": [r"rm\s+-rf\s+/\s*$"],
                "blocked_commands": [],
            },
        )

        assert not result.passed
        assert result.severity == PolicySeverity.BLOCK

    def test_blocklist_fork_bomb(self):
        """Test that fork bombs are blocked."""
        checker = FilesystemChecker()
        tool_call = ToolCall(
            id="test_5",
            name="bash",
            arguments={"command": ":(){ :|:& };:"},
        )

        result = checker.check(
            tool_call,
            {
                "check_type": "blocklist",
                "blocked_patterns": [r":\(\)\s*\{\s*:\|:&\s*\}\s*;"],
                "blocked_commands": [],
            },
        )

        assert not result.passed

    def test_safe_command_passes(self):
        """Test that safe commands pass."""
        checker = FilesystemChecker()
        tool_call = ToolCall(
            id="test_6",
            name="bash",
            arguments={"command": "ls -la /home/ubuntu"},
        )

        result = checker.check(
            tool_call,
            {
                "check_type": "blocklist",
                "blocked_patterns": [r"rm\s+-rf\s+/"],
                "blocked_commands": [],
            },
        )

        assert result.passed


class TestNetworkChecker:
    """Tests for NetworkChecker."""

    def test_allowed_domain(self):
        """Test that allowed domains pass."""
        checker = NetworkChecker()
        tool_call = ToolCall(
            id="test_7",
            name="browser_navigate",
            arguments={"url": "https://github.com/user/repo"},
        )

        result = checker.check(
            tool_call,
            {
                "allowed_domains": ["github.com", "api.github.com"],
                "allowed_ips": [],
                "block_private_ips": False,
            },
        )

        assert result.passed

    def test_subdomain_allowed(self):
        """Test that subdomains of allowed domains pass."""
        checker = NetworkChecker()
        tool_call = ToolCall(
            id="test_8",
            name="browser_navigate",
            arguments={"url": "https://raw.githubusercontent.com/user/repo/main/file.txt"},
        )

        result = checker.check(
            tool_call,
            {
                "allowed_domains": ["githubusercontent.com"],
                "allowed_ips": [],
                "block_private_ips": False,
            },
        )

        assert result.passed

    def test_unknown_domain_warned(self):
        """Test that unknown domains trigger warnings."""
        checker = NetworkChecker()
        tool_call = ToolCall(
            id="test_9",
            name="browser_navigate",
            arguments={"url": "https://malicious-site.com/steal-data"},
        )

        result = checker.check(
            tool_call,
            {
                "allowed_domains": ["github.com"],
                "allowed_ips": [],
                "block_private_ips": False,
            },
        )

        assert not result.passed
        assert "malicious-site.com" in result.violation_message

    def test_curl_in_bash(self):
        """Test that curl commands are checked."""
        checker = NetworkChecker()
        tool_call = ToolCall(
            id="test_10",
            name="bash",
            arguments={"command": "curl https://api.github.com/users/test"},
        )

        result = checker.check(
            tool_call,
            {
                "allowed_domains": ["github.com", "api.github.com"],
                "allowed_ips": [],
                "block_private_ips": False,
            },
        )

        assert result.passed

    def test_localhost_allowed(self):
        """Test that localhost is allowed."""
        checker = NetworkChecker()
        tool_call = ToolCall(
            id="test_11",
            name="browser_navigate",
            arguments={"url": "http://localhost:3000"},
        )

        result = checker.check(
            tool_call,
            {
                "allowed_domains": ["localhost"],
                "allowed_ips": ["127.0.0.1"],
                "block_private_ips": False,
            },
        )

        assert result.passed


class TestSecretsRedactor:
    """Tests for SecretsRedactor."""

    def test_redact_openai_key(self):
        """Test that OpenAI API keys are redacted."""
        redactor = SecretsRedactor()
        text = "export OPENAI_API_KEY=sk-abcdefghijklmnopqrstuvwxyz1234567890"

        redacted, secrets = redactor.redact(text)

        assert "sk-" not in redacted
        assert "<REDACTED_OPENAI_KEY>" in redacted
        assert len(secrets) > 0

    def test_redact_github_token(self):
        """Test that GitHub tokens are redacted."""
        redactor = SecretsRedactor()
        text = "GITHUB_TOKEN=ghp_abcdefghijklmnopqrstuvwxyz1234567890"

        redacted, secrets = redactor.redact(text)

        assert "ghp_" not in redacted
        assert "<REDACTED_GITHUB_TOKEN>" in redacted

    def test_redact_aws_key(self):
        """Test that AWS access keys are redacted."""
        redactor = SecretsRedactor()
        text = "AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE"

        redacted, secrets = redactor.redact(text)

        assert "AKIA" not in redacted
        assert "<REDACTED_AWS_KEY>" in redacted

    def test_redact_bearer_token(self):
        """Test that Bearer tokens are redacted."""
        redactor = SecretsRedactor()
        text = "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"

        redacted, secrets = redactor.redact(text)

        assert "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9" not in redacted
        assert "<REDACTED_TOKEN>" in redacted

    def test_redact_private_key(self):
        """Test that private keys are redacted."""
        redactor = SecretsRedactor()
        text = """-----BEGIN RSA PRIVATE KEY-----
MIIEpAIBAAKCAQEA0Z3VS5JJcds3xfn/ygWyF8PbnGy
-----END RSA PRIVATE KEY-----"""

        redacted, secrets = redactor.redact(text)

        assert "BEGIN RSA PRIVATE KEY" not in redacted
        assert "<REDACTED_PRIVATE_KEY>" in redacted

    def test_no_false_positives(self):
        """Test that normal text is not redacted."""
        redactor = SecretsRedactor()
        text = "This is a normal log message with no secrets."

        redacted, secrets = redactor.redact(text)

        assert redacted == text
        assert len(secrets) == 0

    def test_redact_tool_result(self):
        """Test redacting a tool result."""
        redactor = SecretsRedactor()
        result = ToolResult(
            tool_call_id="test_12",
            content="API key is sk-abcdefghijklmnopqrstuvwxyz1234567890",
            success=True,
        )

        redacted_result = redactor.redact_tool_result(result)

        assert "sk-" not in redacted_result.content
        assert "<REDACTED_OPENAI_KEY>" in redacted_result.content


class TestPolicyEngine:
    """Tests for PolicyEngine."""

    def test_default_policies_loaded(self):
        """Test that default policies are loaded."""
        engine = PolicyEngine()

        assert len(engine.policies) > 0
        policy_names = [p.name for p in engine.policies]
        assert "filesystem_workspace_only" in policy_names
        assert "no_destructive_commands" in policy_names

    def test_evaluate_safe_command(self):
        """Test evaluating a safe command."""
        engine = PolicyEngine()
        tool_call = ToolCall(
            id="test_13",
            name="bash",
            arguments={"command": "ls -la /home/ubuntu"},
        )

        results = engine.evaluate(tool_call)

        # Should pass all checks
        assert not engine.should_block(results)

    def test_evaluate_dangerous_command(self):
        """Test evaluating a dangerous command."""
        engine = PolicyEngine()
        tool_call = ToolCall(
            id="test_14",
            name="bash",
            arguments={"command": "rm -rf /"},
        )

        results = engine.evaluate(tool_call)

        # Should be blocked
        assert engine.should_block(results)
        blocking = engine.get_blocking_violations(results)
        assert len(blocking) > 0

    def test_disabled_engine(self):
        """Test that disabled engine returns empty results."""
        engine = PolicyEngine(enabled=False)
        tool_call = ToolCall(
            id="test_15",
            name="bash",
            arguments={"command": "rm -rf /"},
        )

        results = engine.evaluate(tool_call)

        assert len(results) == 0

    def test_format_violations(self):
        """Test formatting violations for display."""
        engine = PolicyEngine()
        tool_call = ToolCall(
            id="test_16",
            name="bash",
            arguments={"command": "rm -rf /"},
        )

        results = engine.evaluate(tool_call)
        formatted = engine.format_violations(results)

        assert "[POLICY VIOLATIONS]" in formatted
        assert "[BLOCK]" in formatted

    def test_secrets_redaction(self):
        """Test secrets redaction through engine."""
        engine = PolicyEngine()
        text = "API key: sk-abcdefghijklmnopqrstuvwxyz1234567890"

        redacted, secrets = engine.redact_secrets(text)

        assert "sk-" not in redacted
        assert len(secrets) > 0


class TestPolicyIntegration:
    """Integration tests for the policy system."""

    def test_file_read_in_workspace(self):
        """Test reading a file in the workspace."""
        engine = PolicyEngine()

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", dir="/tmp", delete=False
        ) as f:
            f.write("print('hello')")
            temp_path = f.name

        try:
            tool_call = ToolCall(
                id="test_17",
                name="Read",
                arguments={"file_path": temp_path},
            )

            results = engine.evaluate(tool_call)

            assert not engine.should_block(results)
        finally:
            os.unlink(temp_path)

    def test_file_read_outside_workspace(self):
        """Test reading a file outside the workspace."""
        engine = PolicyEngine()
        tool_call = ToolCall(
            id="test_18",
            name="Read",
            arguments={"file_path": "/etc/shadow"},
        )

        results = engine.evaluate(tool_call)

        assert engine.should_block(results)

    def test_browser_navigate_allowed(self):
        """Test navigating to an allowed domain."""
        engine = PolicyEngine()
        tool_call = ToolCall(
            id="test_19",
            name="browser_navigate",
            arguments={"url": "https://github.com/user/repo"},
        )

        results = engine.evaluate(tool_call)

        # Should not block (might warn)
        assert not engine.should_block(results)

    def test_multiple_policies_evaluated(self):
        """Test that multiple policies are evaluated."""
        engine = PolicyEngine()
        tool_call = ToolCall(
            id="test_20",
            name="bash",
            arguments={"command": "curl https://github.com/api && cat /home/ubuntu/file.txt"},
        )

        results = engine.evaluate(tool_call)

        # Multiple policies should have been checked
        assert len(results) >= 1
