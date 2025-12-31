"""
Secret Scanner for detecting and redacting sensitive information.

Detects:
- API keys (sk-*, api_key=*, etc.)
- Passwords in common formats
- Private keys (BEGIN RSA PRIVATE KEY, etc.)
- AWS credentials
- GitHub tokens
- Generic high-entropy strings
"""

import re
from dataclasses import dataclass
from typing import Any


@dataclass
class SecretMatch:
    """A detected secret in text."""

    pattern_name: str
    matched_text: str
    start: int
    end: int
    confidence: float  # 0.0 to 1.0


class SecretScanner:
    """
    Scans text for secrets and provides redaction.

    Features:
    - Multiple pattern types for common secrets
    - Configurable patterns
    - Confidence scoring
    - Redaction with placeholder
    """

    # Default patterns for secret detection
    DEFAULT_PATTERNS: dict[str, tuple[str, float]] = {
        # API Keys
        "openai_key": (r"sk-[a-zA-Z0-9]{20,}", 0.95),
        "anthropic_key": (r"sk-ant-[a-zA-Z0-9\-]{20,}", 0.95),
        "api_key_assignment": (r"(?:api[_-]?key|apikey)\s*[=:]\s*['\"]?([a-zA-Z0-9\-_]{16,})['\"]?", 0.85),
        "bearer_token": (r"Bearer\s+[a-zA-Z0-9\-_\.]{20,}", 0.90),

        # AWS
        "aws_access_key": (r"AKIA[0-9A-Z]{16}", 0.95),
        "aws_secret_key": (r"(?:aws[_-]?secret[_-]?(?:access[_-]?)?key)\s*[=:]\s*['\"]?([a-zA-Z0-9/+=]{40})['\"]?", 0.90),

        # GitHub
        "github_token": (r"gh[pousr]_[a-zA-Z0-9]{36,}", 0.95),
        "github_pat": (r"github_pat_[a-zA-Z0-9]{22}_[a-zA-Z0-9]{59}", 0.95),

        # Private Keys
        "private_key_header": (r"-----BEGIN\s+(?:RSA\s+)?PRIVATE\s+KEY-----", 0.99),
        "private_key_block": (r"-----BEGIN\s+(?:RSA\s+)?PRIVATE\s+KEY-----[\s\S]*?-----END\s+(?:RSA\s+)?PRIVATE\s+KEY-----", 0.99),

        # Passwords
        "password_assignment": (r"(?:password|passwd|pwd)\s*[=:]\s*['\"]?([^\s'\"]{4,})['\"]?", 0.80),
        "secret_assignment": (r"(?:secret|token)\s*[=:]\s*['\"]?([a-zA-Z0-9\-_]{8,})['\"]?", 0.75),

        # Database URLs
        "postgres_url": (r"postgres(?:ql)?://[^:]+:[^@]+@[^\s]+", 0.90),
        "mysql_url": (r"mysql://[^:]+:[^@]+@[^\s]+", 0.90),
        "mongodb_url": (r"mongodb(?:\+srv)?://[^:]+:[^@]+@[^\s]+", 0.90),

        # Generic high-entropy
        "hex_secret": (r"(?:secret|key|token|password)[_-]?[=:]\s*['\"]?([a-fA-F0-9]{32,})['\"]?", 0.70),
        "base64_secret": (r"(?:secret|key|token)[_-]?[=:]\s*['\"]?([a-zA-Z0-9+/]{32,}={0,2})['\"]?", 0.65),
    }

    def __init__(
        self,
        patterns: dict[str, tuple[str, float]] | None = None,
        redaction_placeholder: str = "[REDACTED]",
        min_confidence: float = 0.5,
        enabled: bool = True,
    ):
        """
        Initialize secret scanner.

        Args:
            patterns: Custom patterns dict {name: (regex, confidence)}
            redaction_placeholder: Text to replace secrets with
            min_confidence: Minimum confidence to report a match
            enabled: Whether scanning is enabled
        """
        self.patterns = patterns or self.DEFAULT_PATTERNS
        self.redaction_placeholder = redaction_placeholder
        self.min_confidence = min_confidence
        self.enabled = enabled

        # Compile patterns
        self._compiled: dict[str, tuple[re.Pattern[str], float]] = {}
        for name, (pattern, confidence) in self.patterns.items():
            try:
                self._compiled[name] = (re.compile(pattern, re.IGNORECASE), confidence)
            except re.error:
                # Skip invalid patterns
                pass

    def scan(self, text: str) -> list[SecretMatch]:
        """
        Scan text for secrets.

        Args:
            text: Text to scan

        Returns:
            List of SecretMatch objects for detected secrets
        """
        if not self.enabled or not text:
            return []

        matches: list[SecretMatch] = []
        seen_ranges: set[tuple[int, int]] = set()

        for name, (pattern, confidence) in self._compiled.items():
            if confidence < self.min_confidence:
                continue

            for match in pattern.finditer(text):
                start, end = match.start(), match.end()

                # Skip if overlapping with existing match
                if any(
                    (start >= s and start < e) or (end > s and end <= e)
                    for s, e in seen_ranges
                ):
                    continue

                # Get the matched text (use group 1 if available, else full match)
                matched_text = match.group(1) if match.lastindex else match.group(0)

                matches.append(SecretMatch(
                    pattern_name=name,
                    matched_text=matched_text,
                    start=start,
                    end=end,
                    confidence=confidence,
                ))
                seen_ranges.add((start, end))

        # Sort by position
        matches.sort(key=lambda m: m.start)
        return matches

    def redact(self, text: str) -> str:
        """
        Redact secrets from text.

        Args:
            text: Text to redact

        Returns:
            Text with secrets replaced by redaction placeholder
        """
        if not self.enabled or not text:
            return text

        matches = self.scan(text)
        if not matches:
            return text

        # Build redacted text by replacing matches in reverse order
        result = text
        for match in reversed(matches):
            result = result[:match.start] + self.redaction_placeholder + result[match.end:]

        return result

    def scan_dict(self, data: dict[str, Any]) -> list[SecretMatch]:
        """
        Scan a dictionary for secrets in string values.

        Args:
            data: Dictionary to scan

        Returns:
            List of SecretMatch objects with key paths
        """
        matches: list[SecretMatch] = []

        def scan_value(value: Any, path: str = "") -> None:
            if isinstance(value, str):
                for match in self.scan(value):
                    match.pattern_name = f"{path}.{match.pattern_name}" if path else match.pattern_name
                    matches.append(match)
            elif isinstance(value, dict):
                for k, v in value.items():
                    scan_value(v, f"{path}.{k}" if path else k)
            elif isinstance(value, list):
                for i, v in enumerate(value):
                    scan_value(v, f"{path}[{i}]")

        scan_value(data)
        return matches

    def redact_dict(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Redact secrets from a dictionary.

        Args:
            data: Dictionary to redact

        Returns:
            New dictionary with secrets redacted
        """
        import copy

        def redact_value(value: Any) -> Any:
            if isinstance(value, str):
                return self.redact(value)
            elif isinstance(value, dict):
                return {k: redact_value(v) for k, v in value.items()}
            elif isinstance(value, list):
                return [redact_value(v) for v in value]
            else:
                return copy.deepcopy(value)

        return redact_value(data)

    def add_pattern(self, name: str, pattern: str, confidence: float = 0.8) -> None:
        """
        Add a custom pattern.

        Args:
            name: Pattern name
            pattern: Regex pattern
            confidence: Confidence score (0.0 to 1.0)
        """
        self.patterns[name] = (pattern, confidence)
        self._compiled[name] = (re.compile(pattern, re.IGNORECASE), confidence)

    def remove_pattern(self, name: str) -> bool:
        """
        Remove a pattern.

        Args:
            name: Pattern name to remove

        Returns:
            True if pattern was removed, False if not found
        """
        if name in self.patterns:
            del self.patterns[name]
            del self._compiled[name]
            return True
        return False
