# Copyright OpenJarvis contributors.
# Licensed under the Apache License, Version 2.0 (the "License"); you may not use
# this file except in compliance with the License. A copy is in ./LICENSE, or at
# http://www.apache.org/licenses/LICENSE-2.0
#
# Source: https://github.com/open-jarvis/OpenJarvis
#         src/openjarvis/security/scanner.py @ 77bff2548ad155ffd29a4d2e0d9c56c1eaaa754b
#
# Modified for Flux (see THIRD_PARTY_NOTICES.md):
#   - kept the SecretScanner.PATTERNS table verbatim and the critical PIIScanner
#     patterns (SSN, card numbers); dropped the email / phone / IPv4 patterns, which
#     every ordinary email would trip;
#   - the original scans through a Rust extension (openjarvis._rust_bridge); this copy
#     scans in pure Python with `re` so it adds no dependency;
#   - ThreatLevel / ScanResult are reduced to a small enum and a list of findings.
"""Secret and PII patterns for outbound text (pure Python port of OpenJarvis' scanner)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import IntEnum
from typing import Dict, List, Tuple


class ThreatLevel(IntEnum):
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


@dataclass(frozen=True)
class Finding:
    pattern: str
    level: ThreatLevel
    description: str


class _Scanner:
    scanner_id = ""
    PATTERNS: Dict[str, Tuple[str, ThreatLevel, str]] = {}

    def __init__(self) -> None:
        self._compiled = {name: (re.compile(rx), lvl, desc) for name, (rx, lvl, desc) in self.PATTERNS.items()}

    def scan(self, text: str) -> List[Finding]:
        """Every pattern that matches ``text`` (one finding per pattern)."""
        return [Finding(name, lvl, desc) for name, (rx, lvl, desc) in self._compiled.items()
                if rx.search(text or "")]

    def redact(self, text: str) -> str:
        """Replace matches with ``[REDACTED:{pattern_name}]``."""
        for name, (rx, _, _) in self._compiled.items():
            text = rx.sub(f"[REDACTED:{name}]", text)
        return text


class SecretScanner(_Scanner):
    """Detect API keys, tokens, passwords, and other secrets in text."""

    scanner_id = "secrets"

    PATTERNS: Dict[str, Tuple[str, ThreatLevel, str]] = {
        "openai_key": (
            r"sk-[A-Za-z0-9_-]{20,}",
            ThreatLevel.CRITICAL,
            "OpenAI API key",
        ),
        "anthropic_key": (
            r"sk-ant-[A-Za-z0-9_-]{20,}",
            ThreatLevel.CRITICAL,
            "Anthropic API key",
        ),
        "aws_access_key": (
            r"AKIA[0-9A-Z]{16}",
            ThreatLevel.CRITICAL,
            "AWS access key",
        ),
        "github_token": (
            r"(?:ghp|gho|ghs|ghr|github_pat)_[A-Za-z0-9_]{36,}",
            ThreatLevel.CRITICAL,
            "GitHub token",
        ),
        "password_assignment": (
            r"""(?:password|passwd|pwd)\s*[=:]\s*['"]([^'"]{4,})['"]""",
            ThreatLevel.HIGH,
            "Password assignment",
        ),
        "db_connection_string": (
            r"(?:postgres|mysql|mongodb|redis)://[^\s]{10,}",
            ThreatLevel.HIGH,
            "Database connection string",
        ),
        "private_key": (
            r"-----BEGIN (?:RSA )?PRIVATE KEY-----",
            ThreatLevel.CRITICAL,
            "Private key",
        ),
        "slack_token": (
            r"xox[bpors]-[A-Za-z0-9\-]{10,}",
            ThreatLevel.HIGH,
            "Slack token",
        ),
        "stripe_key": (
            r"(?:sk|pk)_(?:test|live)_[A-Za-z0-9]{20,}",
            ThreatLevel.CRITICAL,
            "Stripe key",
        ),
        "generic_api_key": (
            r"""(?:api_key|secret_key|auth_token)\s*[=:]\s*['"]([^'"]{8,})['"]""",
            ThreatLevel.HIGH,
            "Generic API key/secret",
        ),
    }


class PIIScanner(_Scanner):
    """Detect high-risk personally identifiable information in text (critical patterns only)."""

    scanner_id = "pii"

    PATTERNS: Dict[str, Tuple[str, ThreatLevel, str]] = {
        "us_ssn": (
            r"\b\d{3}-\d{2}-\d{4}\b",
            ThreatLevel.CRITICAL,
            "US Social Security Number",
        ),
        "credit_card_visa": (
            r"\b4\d{3}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b",
            ThreatLevel.CRITICAL,
            "Visa credit card",
        ),
        "credit_card_mastercard": (
            r"\b5[1-5]\d{2}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b",
            ThreatLevel.CRITICAL,
            "Mastercard credit card",
        ),
        "credit_card_amex": (
            r"\b3[47]\d{2}[\s-]?\d{6}[\s-]?\d{5}\b",
            ThreatLevel.CRITICAL,
            "Amex credit card",
        ),
    }


__all__ = ["Finding", "PIIScanner", "SecretScanner", "ThreatLevel"]
