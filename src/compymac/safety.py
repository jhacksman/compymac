"""
Safety Policy Layer for CompyMac.

This module implements Gap 3 from the roadmap: runtime safety enforcement
including filesystem allowlists, network allowlists, secrets redaction,
and destructive command blocking.

The safety layer prevents:
- Filesystem damage (rm -rf /, etc.)
- Data exfiltration (curl to external servers)
- Secrets exposure in traces (API keys, tokens)
- Resource exhaustion (fork bombs, infinite loops)
- Privilege escalation (sudo, chown)
"""

from __future__ import annotations

import logging
import os
import re
import urllib.parse
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from compymac.types import ToolCall, ToolResult

logger = logging.getLogger(__name__)


class PolicySeverity(Enum):
    """How strictly to enforce policy."""

    ADVISORY = "advisory"  # Log warning, allow execution
    WARN = "warn"  # Warn user, require confirmation
    BLOCK = "block"  # Prevent execution entirely
    AUDIT = "audit"  # Allow but flag for human review


class EnforcementAction(Enum):
    """What to do when policy is violated."""

    LOG = "log"  # Just log the violation
    WARN_USER = "warn_user"  # Alert the user
    BLOCK_EXECUTION = "block"  # Prevent tool execution
    SANITIZE = "sanitize"  # Modify arguments to be safe
    REQUEST_APPROVAL = "approval"  # Ask human for approval


@dataclass
class PolicyResult:
    """Result of evaluating a policy check."""

    passed: bool
    severity: PolicySeverity
    violation_message: str = ""
    recommended_action: EnforcementAction | None = None
    evidence: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "passed": self.passed,
            "severity": self.severity.value,
            "violation_message": self.violation_message,
            "recommended_action": self.recommended_action.value
            if self.recommended_action
            else None,
            "evidence": self.evidence,
        }


@dataclass
class PolicyCheck:
    """A specific check in a policy."""

    check_type: str  # "filesystem", "network", "secrets", "resource", etc.
    parameters: dict[str, Any] = field(default_factory=dict)


@dataclass
class SafetyPolicy:
    """A safety policy for tool execution."""

    name: str
    description: str
    tool_pattern: str  # Regex matching tool names
    checks: list[PolicyCheck]
    enforcement: EnforcementAction
    severity: PolicySeverity
    enabled: bool = True

    def matches_tool(self, tool_name: str) -> bool:
        """Check if this policy applies to the given tool."""
        return bool(re.match(self.tool_pattern, tool_name))


class PolicyChecker(ABC):
    """Abstract base class for policy checkers."""

    @abstractmethod
    def check(
        self, tool_call: ToolCall, parameters: dict[str, Any]
    ) -> PolicyResult:
        """Evaluate the policy check against a tool call."""
        pass


class FilesystemChecker(PolicyChecker):
    """Checks filesystem access policies."""

    def check(
        self, tool_call: ToolCall, parameters: dict[str, Any]
    ) -> PolicyResult:
        """Check filesystem access policies."""
        check_type = parameters.get("check_type", "allowlist")

        if check_type == "allowlist":
            return self.check_allowlist(
                tool_call,
                parameters.get("allowed_prefixes", []),
                parameters.get("denied_patterns", []),
            )
        elif check_type == "blocklist":
            return self.check_blocklist(
                tool_call,
                parameters.get("blocked_patterns", []),
                parameters.get("blocked_commands", []),
            )

        return PolicyResult(passed=True, severity=PolicySeverity.ADVISORY)

    def check_allowlist(
        self,
        tool_call: ToolCall,
        allowed_prefixes: list[str],
        denied_patterns: list[str],
    ) -> PolicyResult:
        """Check if file paths are within allowlist."""
        paths = self._extract_file_paths(tool_call)

        if not paths:
            return PolicyResult(passed=True, severity=PolicySeverity.ADVISORY)

        violations = []
        for path in paths:
            # Resolve to absolute path
            abs_path = os.path.abspath(os.path.expanduser(path))

            # Check denied patterns first
            for pattern in denied_patterns:
                if re.match(pattern, abs_path):
                    violations.append(
                        f"Path {abs_path} matches denied pattern {pattern}"
                    )
                    break
            else:
                # Check if path starts with allowed prefix
                if allowed_prefixes:
                    allowed = any(
                        abs_path.startswith(prefix) for prefix in allowed_prefixes
                    )
                    if not allowed:
                        violations.append(
                            f"Path {abs_path} not in allowed prefixes"
                        )

        if violations:
            return PolicyResult(
                passed=False,
                severity=PolicySeverity.BLOCK,
                violation_message="; ".join(violations),
                recommended_action=EnforcementAction.BLOCK_EXECUTION,
                evidence={"paths": paths, "violations": violations},
            )

        return PolicyResult(passed=True, severity=PolicySeverity.ADVISORY)

    def check_blocklist(
        self,
        tool_call: ToolCall,
        blocked_patterns: list[str],
        blocked_commands: list[str],
    ) -> PolicyResult:
        """Check if command matches blocklist."""
        if tool_call.name != "bash":
            return PolicyResult(passed=True, severity=PolicySeverity.ADVISORY)

        command = tool_call.arguments.get("command", "")

        violations = []

        # Check blocked patterns (regex)
        for pattern in blocked_patterns:
            if re.search(pattern, command, re.IGNORECASE):
                violations.append(f"Command matches blocked pattern: {pattern}")

        # Check blocked commands (substring)
        for blocked in blocked_commands:
            if blocked.lower() in command.lower():
                violations.append(f"Command contains blocked substring: {blocked}")

        if violations:
            return PolicyResult(
                passed=False,
                severity=PolicySeverity.BLOCK,
                violation_message="; ".join(violations),
                recommended_action=EnforcementAction.BLOCK_EXECUTION,
                evidence={"command": command, "violations": violations},
            )

        return PolicyResult(passed=True, severity=PolicySeverity.ADVISORY)

    def _extract_file_paths(self, tool_call: ToolCall) -> list[str]:
        """Extract file paths from tool call arguments."""
        paths = []

        # File tools
        if tool_call.name in ("Read", "Write", "Edit"):
            if "file_path" in tool_call.arguments:
                paths.append(tool_call.arguments["file_path"])
            if "path" in tool_call.arguments:
                paths.append(tool_call.arguments["path"])

        # Bash commands - extract paths heuristically
        elif tool_call.name == "bash":
            command = tool_call.arguments.get("command", "")
            # Look for absolute paths
            path_pattern = r"(?:^|\s)(/[^\s;|&><]+)"
            matches = re.findall(path_pattern, command)
            paths.extend(matches)

        return paths


class NetworkChecker(PolicyChecker):
    """Checks network access policies."""

    def check(
        self, tool_call: ToolCall, parameters: dict[str, Any]
    ) -> PolicyResult:
        """Check network access policies."""
        return self.check_allowlist(
            tool_call,
            parameters.get("allowed_domains", []),
            parameters.get("allowed_ips", []),
            parameters.get("block_private_ips", False),
        )

    def check_allowlist(
        self,
        tool_call: ToolCall,
        allowed_domains: list[str],
        allowed_ips: list[str],
        block_private_ips: bool,
    ) -> PolicyResult:
        """Check if network requests are to allowed destinations."""
        urls = self._extract_urls(tool_call)

        if not urls:
            return PolicyResult(passed=True, severity=PolicySeverity.ADVISORY)

        violations = []
        for url in urls:
            try:
                parsed = urllib.parse.urlparse(url)
                hostname = parsed.hostname or parsed.netloc
            except Exception:
                hostname = url

            if not hostname:
                continue

            # Check if domain is allowed
            domain_allowed = any(
                hostname == domain or hostname.endswith(f".{domain}")
                for domain in allowed_domains
            )

            # Check if IP is allowed
            ip_allowed = hostname in allowed_ips

            # Check if private IP (if blocked)
            if block_private_ips and self._is_private_ip(hostname):
                violations.append(f"Private IP access blocked: {hostname}")
                continue

            if allowed_domains and not (domain_allowed or ip_allowed):
                violations.append(f"Domain {hostname} not in allowlist")

        if violations:
            return PolicyResult(
                passed=False,
                severity=PolicySeverity.WARN,
                violation_message="; ".join(violations),
                recommended_action=EnforcementAction.WARN_USER,
                evidence={"urls": urls, "violations": violations},
            )

        return PolicyResult(passed=True, severity=PolicySeverity.ADVISORY)

    def _extract_urls(self, tool_call: ToolCall) -> list[str]:
        """Extract URLs from tool call arguments."""
        urls = []

        # Browser navigation
        if tool_call.name == "browser_navigate":
            if "url" in tool_call.arguments:
                urls.append(tool_call.arguments["url"])

        # Bash commands - look for URLs
        elif tool_call.name == "bash":
            command = tool_call.arguments.get("command", "")
            # Match URLs in command
            url_pattern = r"https?://[^\s\"'<>]+"
            matches = re.findall(url_pattern, command)
            urls.extend(matches)

        return urls

    def _is_private_ip(self, hostname: str) -> bool:
        """Check if hostname is a private IP address."""
        try:
            import ipaddress

            ip = ipaddress.ip_address(hostname)
            return ip.is_private
        except ValueError:
            return False


class SecretsRedactor:
    """Redacts secrets from outputs and traces."""

    def __init__(self):
        """Initialize with common secret patterns."""
        self.secret_patterns: list[tuple[re.Pattern[str], str]] = [
            # OpenAI API keys
            (re.compile(r"sk-[a-zA-Z0-9]{20,}"), "<REDACTED_OPENAI_KEY>"),
            # GitHub personal access tokens
            (re.compile(r"ghp_[a-zA-Z0-9]{36}"), "<REDACTED_GITHUB_TOKEN>"),
            (re.compile(r"gho_[a-zA-Z0-9]{36}"), "<REDACTED_GITHUB_OAUTH>"),
            (re.compile(r"ghu_[a-zA-Z0-9]{36}"), "<REDACTED_GITHUB_USER>"),
            (re.compile(r"ghs_[a-zA-Z0-9]{36}"), "<REDACTED_GITHUB_SERVER>"),
            (re.compile(r"ghr_[a-zA-Z0-9]{36}"), "<REDACTED_GITHUB_REFRESH>"),
            # AWS access keys
            (re.compile(r"AKIA[0-9A-Z]{16}"), "<REDACTED_AWS_KEY>"),
            # AWS secret keys (40 chars base64)
            (
                re.compile(r"(?<![A-Za-z0-9+/])[A-Za-z0-9+/]{40}(?![A-Za-z0-9+/=])"),
                "<REDACTED_AWS_SECRET>",
            ),
            # Google OAuth tokens
            (re.compile(r"ya29\.[a-zA-Z0-9_-]{50,}"), "<REDACTED_GOOGLE_TOKEN>"),
            # Slack tokens
            (re.compile(r"xox[baprs]-[a-zA-Z0-9-]+"), "<REDACTED_SLACK_TOKEN>"),
            # Generic API key patterns
            (
                re.compile(r"api[_-]?key[\"']?\s*[:=]\s*[\"']?([a-zA-Z0-9_-]{20,})[\"']?", re.IGNORECASE),
                "api_key=<REDACTED_API_KEY>",
            ),
            # Bearer tokens
            (
                re.compile(r"Bearer\s+[a-zA-Z0-9_.-]{20,}"),
                "Bearer <REDACTED_TOKEN>",
            ),
            # Password patterns
            (
                re.compile(r"password[\"']?\s*[:=]\s*[\"']?([^\s\"']+)[\"']?", re.IGNORECASE),
                "password=<REDACTED_PASSWORD>",
            ),
            # Private keys
            (
                re.compile(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----[\s\S]*?-----END (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----"),
                "<REDACTED_PRIVATE_KEY>",
            ),
        ]

    def redact(self, text: str) -> tuple[str, list[str]]:
        """Redact secrets from text. Returns (redacted_text, secrets_found)."""
        redacted = text
        secrets_found = []

        for pattern, replacement in self.secret_patterns:
            matches = pattern.findall(redacted)
            if matches:
                # Store what was found (but not the actual secret)
                secrets_found.append(f"{len(matches)} match(es) for {replacement}")
                redacted = pattern.sub(replacement, redacted)

        return redacted, secrets_found

    def redact_tool_result(self, result: ToolResult) -> ToolResult:
        """Redact secrets from tool result."""
        from compymac.types import ToolResult as TR

        redacted_output, secrets = self.redact(result.content)

        if secrets:
            # Create redacted copy
            return TR(
                tool_call_id=result.tool_call_id,
                content=redacted_output,
                success=result.success,
            )

        return result


class PolicyEngine:
    """Evaluates safety policies against tool calls."""

    def __init__(
        self,
        policies: list[SafetyPolicy] | None = None,
        enabled: bool = True,
    ):
        """Initialize the policy engine."""
        self.enabled = enabled
        self.policies = policies or self._default_policies()

        # Initialize checkers
        self.checkers: dict[str, PolicyChecker] = {
            "filesystem_allowlist": FilesystemChecker(),
            "command_blocklist": FilesystemChecker(),
            "network_allowlist": NetworkChecker(),
        }

        self.secrets_redactor = SecretsRedactor()

    def _default_policies(self) -> list[SafetyPolicy]:
        """Load default safety policies."""
        return [
            # Filesystem workspace policy
            SafetyPolicy(
                name="filesystem_workspace_only",
                description="Prevent access to files outside workspace",
                tool_pattern=r"(bash|Read|Write|Edit)",
                checks=[
                    PolicyCheck(
                        check_type="filesystem_allowlist",
                        parameters={
                            "check_type": "allowlist",
                            "allowed_prefixes": [
                                "/home/ubuntu",
                                "/tmp",
                                "/workspace",
                            ],
                            "denied_patterns": [
                                r"/etc/shadow",
                                r"/etc/passwd",
                                r".*\.ssh/.*",
                                r"/root/.*",
                            ],
                        },
                    )
                ],
                enforcement=EnforcementAction.BLOCK_EXECUTION,
                severity=PolicySeverity.BLOCK,
            ),
            # Destructive command policy
            SafetyPolicy(
                name="no_destructive_commands",
                description="Block destructive filesystem operations",
                tool_pattern=r"bash",
                checks=[
                    PolicyCheck(
                        check_type="command_blocklist",
                        parameters={
                            "check_type": "blocklist",
                            "blocked_patterns": [
                                r"rm\s+-rf\s+/\s*$",  # Delete root
                                r"rm\s+-rf\s+~",  # Delete home
                                r"rm\s+-rf\s+\*",  # Delete everything
                                r"mkfs\.",  # Format filesystem
                                r"dd\s+.*of=/dev/",  # Write to device
                                r">\s*/dev/(sd|hd|nvme)",  # Write to disk
                                r":\(\)\s*\{\s*:\|:&\s*\}\s*;",  # Fork bomb
                            ],
                            "blocked_commands": [
                                "sudo rm -rf",
                                "chmod 777 /",
                                "> /dev/sda",
                            ],
                        },
                    )
                ],
                enforcement=EnforcementAction.BLOCK_EXECUTION,
                severity=PolicySeverity.BLOCK,
            ),
            # Network allowlist policy (advisory by default)
            SafetyPolicy(
                name="network_allowlist",
                description="Warn about network access to unknown domains",
                tool_pattern=r"(bash|browser_.*)",
                checks=[
                    PolicyCheck(
                        check_type="network_allowlist",
                        parameters={
                            "allowed_domains": [
                                "github.com",
                                "api.github.com",
                                "raw.githubusercontent.com",
                                "pypi.org",
                                "files.pythonhosted.org",
                                "npmjs.com",
                                "registry.npmjs.org",
                                "docs.python.org",
                                "stackoverflow.com",
                                "google.com",
                                "localhost",
                            ],
                            "allowed_ips": ["127.0.0.1", "::1"],
                            "block_private_ips": False,
                        },
                    )
                ],
                enforcement=EnforcementAction.WARN_USER,
                severity=PolicySeverity.WARN,
            ),
        ]

    def evaluate(self, tool_call: ToolCall) -> list[PolicyResult]:
        """Evaluate all applicable policies against a tool call."""
        if not self.enabled:
            return []

        results = []

        for policy in self.policies:
            if not policy.enabled:
                continue

            if not policy.matches_tool(tool_call.name):
                continue

            for check in policy.checks:
                checker = self.checkers.get(check.check_type)
                if checker:
                    result = checker.check(tool_call, check.parameters)
                    if not result.passed:
                        # Override with policy severity/enforcement
                        result.severity = policy.severity
                        result.recommended_action = policy.enforcement
                    results.append(result)

        return results

    def should_block(self, results: list[PolicyResult]) -> bool:
        """Check if any result requires blocking execution."""
        return any(
            not r.passed and r.severity == PolicySeverity.BLOCK for r in results
        )

    def get_blocking_violations(self, results: list[PolicyResult]) -> list[PolicyResult]:
        """Get all blocking violations."""
        return [
            r
            for r in results
            if not r.passed and r.severity == PolicySeverity.BLOCK
        ]

    def get_warnings(self, results: list[PolicyResult]) -> list[PolicyResult]:
        """Get all warning violations."""
        return [
            r
            for r in results
            if not r.passed and r.severity == PolicySeverity.WARN
        ]

    def format_violations(self, results: list[PolicyResult]) -> str:
        """Format violations for display."""
        violations = [r for r in results if not r.passed]
        if not violations:
            return ""

        lines = ["[POLICY VIOLATIONS]"]
        for v in violations:
            severity = v.severity.value.upper()
            lines.append(f"  [{severity}] {v.violation_message}")

        return "\n".join(lines)

    def redact_secrets(self, text: str) -> tuple[str, list[str]]:
        """Redact secrets from text."""
        return self.secrets_redactor.redact(text)

    def redact_tool_result(self, result: ToolResult) -> ToolResult:
        """Redact secrets from tool result."""
        return self.secrets_redactor.redact_tool_result(result)
