"""
Security module for CompyMac memory system.

Provides secret scanning and redaction capabilities.
"""

from compymac.security.scanner import SecretMatch, SecretScanner

__all__ = [
    "SecretScanner",
    "SecretMatch",
]
