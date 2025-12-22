"""
Tool Verification Framework for CompyMac.

This module implements contract-driven tool execution with precondition/postcondition
checking to detect false-success failures where tools appear to succeed but actually fail.

Key components:
- ToolContract: Defines preconditions, postconditions, and expected evidence
- Condition: A verifiable condition with check type and parameters
- ConditionResult: Result of checking a single condition
- VerificationResult: Aggregated result of all postcondition checks
- Verifier: Base class for tool-specific verifiers

Design principles:
- Every tool call can have preconditions (what must be true before execution)
- Every tool call can have postconditions (what must be true after execution)
- Verification is deterministic where possible (exit codes, file content, DOM state)
- Verification results are stored in TraceStore for auditability
"""

from __future__ import annotations

import ast
import os
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from compymac.browser import PageState
    from compymac.types import ToolCall, ToolResult


class VerificationStrategy(Enum):
    """How to verify tool execution."""
    EXIT_CODE = "exit_code"
    FILE_CHECKSUM = "file_checksum"
    CONTENT_MATCH = "content_match"
    DOM_STATE = "dom_state"
    API_RESPONSE = "api_response"
    SNAPSHOT_DIFF = "snapshot_diff"


@dataclass
class Condition:
    """A verifiable condition."""
    description: str
    check_type: str
    parameters: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "description": self.description,
            "check_type": self.check_type,
            "parameters": self.parameters,
        }


@dataclass
class ConditionResult:
    """Result of checking a condition."""
    satisfied: bool
    actual_value: Any
    expected_value: Any
    evidence: dict[str, Any] = field(default_factory=dict)
    error_message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "satisfied": self.satisfied,
            "actual_value": str(self.actual_value)[:500],
            "expected_value": str(self.expected_value)[:500],
            "evidence": self.evidence,
            "error_message": self.error_message,
        }


@dataclass
class ToolContract:
    """Contract for a tool execution."""
    tool_name: str
    arguments: dict[str, Any]
    preconditions: list[Condition] = field(default_factory=list)
    postconditions: list[Condition] = field(default_factory=list)
    verification_strategy: VerificationStrategy | None = None
    expected_evidence: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "tool_name": self.tool_name,
            "arguments": self.arguments,
            "preconditions": [c.to_dict() for c in self.preconditions],
            "postconditions": [c.to_dict() for c in self.postconditions],
            "verification_strategy": self.verification_strategy.value if self.verification_strategy else None,
            "expected_evidence": self.expected_evidence,
        }


@dataclass
class VerificationResult:
    """Result of verifying tool execution."""
    tool_name: str
    all_checks_passed: bool
    condition_results: list[ConditionResult]
    confidence_score: float = 1.0
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "tool_name": self.tool_name,
            "all_checks_passed": self.all_checks_passed,
            "condition_results": [r.to_dict() for r in self.condition_results],
            "confidence_score": self.confidence_score,
            "error": self.error,
        }

    def failure_summary(self) -> str:
        """Get summary of failed checks."""
        failed = [r for r in self.condition_results if not r.satisfied]
        if not failed:
            return "All checks passed"
        return "; ".join(r.error_message for r in failed if r.error_message)

    def format_for_agent(self) -> str:
        """Format verification result for agent consumption."""
        lines = []
        for result in self.condition_results:
            status = "PASS" if result.satisfied else "FAIL"
            lines.append(f"[{status}] {result.error_message or 'Check passed'}")
            if not result.satisfied and result.evidence:
                for key, value in result.evidence.items():
                    lines.append(f"  {key}: {str(value)[:200]}")
        return "\n".join(lines)


@dataclass
class PreconditionResult:
    """Result of checking preconditions."""
    all_satisfied: bool
    results: list[ConditionResult]
    summary: str = ""
    failed_conditions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "all_satisfied": self.all_satisfied,
            "results": [r.to_dict() for r in self.results],
            "summary": self.summary,
            "failed_conditions": self.failed_conditions,
        }


class Verifier(ABC):
    """Base class for tool-specific verifiers."""

    @abstractmethod
    def create_contract(self, **kwargs: Any) -> ToolContract:
        """Create a contract for the tool call."""
        pass

    @abstractmethod
    def verify(self, contract: ToolContract, result: ToolResult) -> VerificationResult:
        """Verify the tool execution against the contract."""
        pass

    def _compute_confidence(self, checks: list[ConditionResult]) -> float:
        """Compute confidence score from check results."""
        if not checks:
            return 1.0
        passed = sum(1 for c in checks if c.satisfied)
        return passed / len(checks)


class BashVerifier(Verifier):
    """Verifies bash command execution."""

    def create_contract(self, command: str, **kwargs: Any) -> ToolContract:
        """Create contract for bash command."""
        contract = ToolContract(
            tool_name="bash",
            arguments={"command": command},
            verification_strategy=VerificationStrategy.EXIT_CODE,
        )

        if not kwargs.get("allow_nonzero", False):
            contract.postconditions.append(Condition(
                description="Command exited successfully",
                check_type="exit_code",
                parameters={"expected": 0}
            ))

        if "pytest" in command or "npm test" in command or "python -m pytest" in command:
            contract.postconditions.append(Condition(
                description="Tests passed",
                check_type="output_pattern",
                parameters={"pattern": r"(\d+) passed", "min_matches": 1}
            ))
            contract.expected_evidence["test_results"] = "all_passed"

        if "build" in command or "compile" in command or "npm run build" in command:
            contract.postconditions.append(Condition(
                description="Build completed without errors",
                check_type="no_error_pattern",
                parameters={"patterns": [r"error:", r"Error:", r"ERROR:", r"failed"]}
            ))

        if command.startswith("ruff ") or "lint" in command:
            contract.postconditions.append(Condition(
                description="Linting passed",
                check_type="exit_code",
                parameters={"expected": 0}
            ))

        return contract

    def verify(self, contract: ToolContract, result: ToolResult) -> VerificationResult:
        """Verify bash command succeeded."""
        checks: list[ConditionResult] = []

        exit_code = self._extract_exit_code(result.content)

        for postcondition in contract.postconditions:
            if postcondition.check_type == "exit_code":
                expected = postcondition.parameters["expected"]
                checks.append(ConditionResult(
                    satisfied=(exit_code == expected),
                    actual_value=exit_code,
                    expected_value=expected,
                    evidence={"stdout_preview": result.content[:500]},
                    error_message=f"Exit code {exit_code} != {expected}" if exit_code != expected else ""
                ))

            elif postcondition.check_type == "output_pattern":
                pattern = postcondition.parameters["pattern"]
                matches = re.findall(pattern, result.content)
                min_matches = postcondition.parameters.get("min_matches", 1)
                satisfied = len(matches) >= min_matches
                checks.append(ConditionResult(
                    satisfied=satisfied,
                    actual_value=len(matches),
                    expected_value=min_matches,
                    evidence={"matches": matches[:10]},
                    error_message=f"Found {len(matches)} matches, expected {min_matches}" if not satisfied else ""
                ))

            elif postcondition.check_type == "no_error_pattern":
                patterns = postcondition.parameters["patterns"]
                errors_found = []
                for pattern in patterns:
                    if re.search(pattern, result.content, re.IGNORECASE):
                        errors_found.append(pattern)
                satisfied = len(errors_found) == 0
                checks.append(ConditionResult(
                    satisfied=satisfied,
                    actual_value=errors_found,
                    expected_value=[],
                    evidence={"error_patterns_found": errors_found},
                    error_message=f"Error patterns found: {errors_found}" if not satisfied else ""
                ))

        return VerificationResult(
            tool_name=contract.tool_name,
            all_checks_passed=all(c.satisfied for c in checks),
            condition_results=checks,
            confidence_score=self._compute_confidence(checks)
        )

    def _extract_exit_code(self, output: str) -> int:
        """Extract exit code from bash output."""
        match = re.search(r"return code[=:\s]+(\d+)", output, re.IGNORECASE)
        if match:
            return int(match.group(1))
        match = re.search(r"exit code[=:\s]+(\d+)", output, re.IGNORECASE)
        if match:
            return int(match.group(1))
        match = re.search(r"\(return code = (\d+)\)", output)
        if match:
            return int(match.group(1))
        if "error" in output.lower() or "failed" in output.lower():
            return 1
        return 0


class FileEditVerifier(Verifier):
    """Verifies file edit operations."""

    def create_contract(self, file_path: str, old_string: str, new_string: str, **kwargs: Any) -> ToolContract:
        """Create contract for file edit."""
        return ToolContract(
            tool_name="Edit",
            arguments={"file_path": file_path, "old_string": old_string, "new_string": new_string},
            preconditions=[
                Condition(
                    description=f"File {file_path} exists",
                    check_type="file_exists",
                    parameters={"path": file_path}
                ),
                Condition(
                    description="File contains old content",
                    check_type="content_contains",
                    parameters={"path": file_path, "content": old_string}
                )
            ],
            postconditions=[
                Condition(
                    description="File contains new content",
                    check_type="content_contains",
                    parameters={"path": file_path, "content": new_string}
                ),
                Condition(
                    description="File does not contain old content",
                    check_type="content_not_contains",
                    parameters={"path": file_path, "content": old_string}
                ),
                Condition(
                    description="File is valid (parseable if code)",
                    check_type="syntax_valid",
                    parameters={"path": file_path}
                )
            ],
            verification_strategy=VerificationStrategy.CONTENT_MATCH
        )

    def check_preconditions(self, contract: ToolContract) -> PreconditionResult:
        """Check preconditions before execution."""
        results: list[ConditionResult] = []
        failed: list[str] = []

        for precondition in contract.preconditions:
            if precondition.check_type == "file_exists":
                path = precondition.parameters["path"]
                exists = os.path.exists(path)
                results.append(ConditionResult(
                    satisfied=exists,
                    actual_value=exists,
                    expected_value=True,
                    error_message=f"File {path} does not exist" if not exists else ""
                ))
                if not exists:
                    failed.append(precondition.description)

            elif precondition.check_type == "content_contains":
                path = precondition.parameters["path"]
                content = precondition.parameters["content"]
                try:
                    with open(path) as f:
                        file_content = f.read()
                    contains = content in file_content
                    results.append(ConditionResult(
                        satisfied=contains,
                        actual_value="present" if contains else "absent",
                        expected_value="present",
                        error_message=f"Content '{content[:50]}...' not found in file" if not contains else ""
                    ))
                    if not contains:
                        failed.append(precondition.description)
                except Exception as e:
                    results.append(ConditionResult(
                        satisfied=False,
                        actual_value=str(e),
                        expected_value="readable file",
                        error_message=f"Failed to read file: {e}"
                    ))
                    failed.append(precondition.description)

        all_satisfied = len(failed) == 0
        return PreconditionResult(
            all_satisfied=all_satisfied,
            results=results,
            summary="; ".join(failed) if failed else "All preconditions satisfied",
            failed_conditions=failed
        )

    def verify(self, contract: ToolContract, result: ToolResult) -> VerificationResult:
        """Verify file edit succeeded."""
        checks: list[ConditionResult] = []
        path = contract.arguments["file_path"]

        try:
            with open(path) as f:
                current_content = f.read()
        except Exception as e:
            return VerificationResult(
                tool_name=contract.tool_name,
                all_checks_passed=False,
                condition_results=[],
                confidence_score=0.0,
                error=f"Failed to read file: {e}"
            )

        for postcondition in contract.postconditions:
            if postcondition.check_type == "content_contains":
                expected = postcondition.parameters["content"]
                satisfied = expected in current_content
                checks.append(ConditionResult(
                    satisfied=satisfied,
                    actual_value="present" if satisfied else "absent",
                    expected_value="present",
                    evidence={"file_path": path},
                    error_message=f"Content '{expected[:50]}...' not found in file" if not satisfied else ""
                ))

            elif postcondition.check_type == "content_not_contains":
                old_content = postcondition.parameters["content"]
                satisfied = old_content not in current_content
                checks.append(ConditionResult(
                    satisfied=satisfied,
                    actual_value="absent" if satisfied else "present",
                    expected_value="absent",
                    evidence={"file_path": path},
                    error_message=f"Old content '{old_content[:50]}...' still in file" if not satisfied else ""
                ))

            elif postcondition.check_type == "syntax_valid":
                valid, error = self._check_syntax(path, current_content)
                checks.append(ConditionResult(
                    satisfied=valid,
                    actual_value="valid" if valid else "invalid",
                    expected_value="valid",
                    evidence={"syntax_error": error} if error else {},
                    error_message=f"Syntax error: {error}" if error else ""
                ))

        return VerificationResult(
            tool_name=contract.tool_name,
            all_checks_passed=all(c.satisfied for c in checks),
            condition_results=checks,
            confidence_score=self._compute_confidence(checks)
        )

    def _check_syntax(self, path: str, content: str) -> tuple[bool, str]:
        """Check if file has valid syntax."""
        if path.endswith(".py"):
            try:
                ast.parse(content)
                return True, ""
            except SyntaxError as e:
                return False, f"Line {e.lineno}: {e.msg}"
        if path.endswith(".json"):
            import json
            try:
                json.loads(content)
                return True, ""
            except json.JSONDecodeError as e:
                return False, str(e)
        return True, ""


class FileWriteVerifier(Verifier):
    """Verifies file write operations."""

    def create_contract(self, file_path: str, content: str, **kwargs: Any) -> ToolContract:
        """Create contract for file write."""
        return ToolContract(
            tool_name="Write",
            arguments={"file_path": file_path, "content": content},
            postconditions=[
                Condition(
                    description=f"File {file_path} exists",
                    check_type="file_exists",
                    parameters={"path": file_path}
                ),
                Condition(
                    description="File contains written content",
                    check_type="content_equals",
                    parameters={"path": file_path, "content": content}
                ),
                Condition(
                    description="File is valid (parseable if code)",
                    check_type="syntax_valid",
                    parameters={"path": file_path}
                )
            ],
            verification_strategy=VerificationStrategy.CONTENT_MATCH
        )

    def verify(self, contract: ToolContract, result: ToolResult) -> VerificationResult:
        """Verify file write succeeded."""
        checks: list[ConditionResult] = []
        path = contract.arguments["file_path"]
        expected_content = contract.arguments["content"]

        for postcondition in contract.postconditions:
            if postcondition.check_type == "file_exists":
                exists = os.path.exists(path)
                checks.append(ConditionResult(
                    satisfied=exists,
                    actual_value=exists,
                    expected_value=True,
                    evidence={"file_path": path},
                    error_message=f"File {path} does not exist" if not exists else ""
                ))

            elif postcondition.check_type == "content_equals":
                try:
                    with open(path) as f:
                        actual_content = f.read()
                    satisfied = actual_content == expected_content
                    checks.append(ConditionResult(
                        satisfied=satisfied,
                        actual_value=f"length={len(actual_content)}",
                        expected_value=f"length={len(expected_content)}",
                        evidence={"file_path": path},
                        error_message="File content does not match expected" if not satisfied else ""
                    ))
                except Exception as e:
                    checks.append(ConditionResult(
                        satisfied=False,
                        actual_value=str(e),
                        expected_value="readable file",
                        error_message=f"Failed to read file: {e}"
                    ))

            elif postcondition.check_type == "syntax_valid":
                try:
                    with open(path) as f:
                        content = f.read()
                    valid, error = self._check_syntax(path, content)
                    checks.append(ConditionResult(
                        satisfied=valid,
                        actual_value="valid" if valid else "invalid",
                        expected_value="valid",
                        evidence={"syntax_error": error} if error else {},
                        error_message=f"Syntax error: {error}" if error else ""
                    ))
                except Exception as e:
                    checks.append(ConditionResult(
                        satisfied=False,
                        actual_value=str(e),
                        expected_value="readable file",
                        error_message=f"Failed to check syntax: {e}"
                    ))

        return VerificationResult(
            tool_name=contract.tool_name,
            all_checks_passed=all(c.satisfied for c in checks),
            condition_results=checks,
            confidence_score=self._compute_confidence(checks)
        )

    def _check_syntax(self, path: str, content: str) -> tuple[bool, str]:
        """Check if file has valid syntax."""
        if path.endswith(".py"):
            try:
                ast.parse(content)
                return True, ""
            except SyntaxError as e:
                return False, f"Line {e.lineno}: {e.msg}"
        if path.endswith(".json"):
            import json
            try:
                json.loads(content)
                return True, ""
            except json.JSONDecodeError as e:
                return False, str(e)
        return True, ""


class BrowserActionVerifier(Verifier):
    """Verifies browser automation actions."""

    def create_contract(self, action: str, **kwargs: Any) -> ToolContract:
        """Create contract for browser action."""
        contract = ToolContract(
            tool_name=f"browser_{action}",
            arguments=kwargs,
            verification_strategy=VerificationStrategy.DOM_STATE
        )

        if action == "click":
            element_id = kwargs.get("devinid") or kwargs.get("element_id")
            contract.postconditions.append(Condition(
                description=f"Element {element_id} was clicked",
                check_type="dom_state_changed",
                parameters={"element_id": element_id}
            ))

            if element_id and ("submit" in str(element_id) or "button" in str(element_id)):
                contract.postconditions.append(Condition(
                    description="Page navigation or AJAX occurred",
                    check_type="network_activity",
                    parameters={"timeout_ms": 2000}
                ))

        elif action == "type":
            element_id = kwargs.get("devinid") or kwargs.get("element_id")
            text = kwargs.get("content") or kwargs.get("text")
            contract.postconditions.append(Condition(
                description="Input field contains typed text",
                check_type="input_value",
                parameters={"element_id": element_id, "expected_value": text}
            ))

        elif action == "navigate":
            url = kwargs.get("url")
            contract.postconditions.append(Condition(
                description="Page loaded successfully",
                check_type="page_loaded",
                parameters={"expected_url": url}
            ))

        return contract

    def verify(self, contract: ToolContract, result: ToolResult,
               browser_state: PageState | None = None) -> VerificationResult:
        """Verify browser action succeeded."""
        checks: list[ConditionResult] = []

        if not browser_state:
            return VerificationResult(
                tool_name=contract.tool_name,
                all_checks_passed=result.success,
                condition_results=[ConditionResult(
                    satisfied=result.success,
                    actual_value="executed" if result.success else "failed",
                    expected_value="executed",
                    error_message=result.error or "" if not result.success else ""
                )],
                confidence_score=0.5 if result.success else 0.0
            )

        for postcondition in contract.postconditions:
            if postcondition.check_type == "input_value":
                element_id = postcondition.parameters.get("element_id")
                expected = postcondition.parameters.get("expected_value", "")
                checks.append(ConditionResult(
                    satisfied=result.success,
                    actual_value="typed" if result.success else "failed",
                    expected_value=expected,
                    evidence={"element_id": element_id},
                    error_message="" if result.success else "Failed to type into element"
                ))

            elif postcondition.check_type == "page_loaded":
                expected_url = postcondition.parameters.get("expected_url", "")
                actual_url = getattr(browser_state, "url", "")
                satisfied = self._urls_match(actual_url, expected_url)
                checks.append(ConditionResult(
                    satisfied=satisfied,
                    actual_value=actual_url,
                    expected_value=expected_url,
                    evidence={"page_title": getattr(browser_state, "title", "")},
                    error_message=f"URL '{actual_url}' != '{expected_url}'" if not satisfied else ""
                ))

            elif postcondition.check_type == "dom_state_changed":
                checks.append(ConditionResult(
                    satisfied=result.success,
                    actual_value="changed" if result.success else "unchanged",
                    expected_value="changed",
                    error_message="" if result.success else "DOM state did not change"
                ))

        return VerificationResult(
            tool_name=contract.tool_name,
            all_checks_passed=all(c.satisfied for c in checks),
            condition_results=checks,
            confidence_score=self._compute_confidence(checks)
        )

    def _urls_match(self, actual: str, expected: str) -> bool:
        """Check if URLs match (allowing for normalization)."""
        actual = actual.rstrip("/")
        expected = expected.rstrip("/")
        return actual == expected or actual.endswith(expected) or expected.endswith(actual)


class VerificationEngine:
    """Engine for managing tool verification."""

    def __init__(self, enabled: bool = True):
        self.enabled = enabled
        self.verifiers: dict[str, Verifier] = {
            "bash": BashVerifier(),
            "Bash": BashVerifier(),
            "Edit": FileEditVerifier(),
            "file_edit": FileEditVerifier(),
            "Write": FileWriteVerifier(),
            "file_write": FileWriteVerifier(),
            "browser_click": BrowserActionVerifier(),
            "browser_type": BrowserActionVerifier(),
            "browser_navigate": BrowserActionVerifier(),
        }

    def get_verifier(self, tool_name: str) -> Verifier | None:
        """Get verifier for a tool."""
        return self.verifiers.get(tool_name)

    def register_verifier(self, tool_name: str, verifier: Verifier) -> None:
        """Register a verifier for a tool."""
        self.verifiers[tool_name] = verifier

    def create_contract(self, tool_call: ToolCall) -> ToolContract | None:
        """Create a contract for a tool call."""
        verifier = self.get_verifier(tool_call.name)
        if not verifier:
            return None
        return verifier.create_contract(**tool_call.arguments)

    def verify(self, tool_call: ToolCall, result: ToolResult,
               contract: ToolContract | None = None) -> VerificationResult | None:
        """Verify a tool execution."""
        if not self.enabled:
            return None

        verifier = self.get_verifier(tool_call.name)
        if not verifier:
            return None

        if contract is None:
            contract = verifier.create_contract(**tool_call.arguments)

        return verifier.verify(contract, result)

    def check_preconditions(self, tool_call: ToolCall,
                           contract: ToolContract | None = None) -> PreconditionResult | None:
        """Check preconditions for a tool call."""
        if not self.enabled:
            return None

        verifier = self.get_verifier(tool_call.name)
        if not verifier or not hasattr(verifier, "check_preconditions"):
            return None

        if contract is None:
            contract = verifier.create_contract(**tool_call.arguments)

        return verifier.check_preconditions(contract)
