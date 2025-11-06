"""
PII (Personally Identifiable Information) detection for cascadeflow.

Detects common PII patterns in text using regex.
"""

import re
from dataclasses import dataclass


@dataclass
class PIIMatch:
    """A detected PII match"""

    pii_type: str
    value: str  # Redacted version
    position: tuple[int, int]  # Start, end positions


class PIIDetector:
    """
    Basic PII detector using regex patterns.

    Detects common PII types:
    - Email addresses
    - Phone numbers (US format)
    - Social Security Numbers (US)
    - Credit card numbers
    - IP addresses

    Note: This is a basic v0.2.1 implementation.
    For production, consider using dedicated PII detection services.
    """

    def __init__(self):
        """Initialize PII detector with patterns"""

        # Email pattern
        self._email_pattern = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b")

        # Phone number patterns (US)
        self._phone_patterns = [
            re.compile(r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b"),  # 123-456-7890
            re.compile(r"\(\d{3}\)\s*\d{3}[-.]?\d{4}\b"),  # (123) 456-7890
        ]

        # SSN pattern (US)
        self._ssn_pattern = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")

        # Credit card patterns (basic)
        self._cc_patterns = [
            re.compile(r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b"),  # 16 digit
            re.compile(r"\b\d{4}[-\s]?\d{6}[-\s]?\d{5}\b"),  # 15 digit (Amex)
        ]

        # IP address pattern
        self._ip_pattern = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")

    def detect(self, text: str) -> list[PIIMatch]:
        """
        Detect PII in text.

        Args:
            text: Text to scan for PII

        Returns:
            List of PIIMatch objects
        """
        matches = []

        # Detect emails
        for match in self._email_pattern.finditer(text):
            matches.append(
                PIIMatch(
                    pii_type="email",
                    value=f"{match.group()[:3]}***@***",
                    position=(match.start(), match.end()),
                )
            )

        # Detect phone numbers
        for pattern in self._phone_patterns:
            for match in pattern.finditer(text):
                matches.append(
                    PIIMatch(
                        pii_type="phone",
                        value="***-***-****",
                        position=(match.start(), match.end()),
                    )
                )

        # Detect SSN
        for match in self._ssn_pattern.finditer(text):
            matches.append(
                PIIMatch(pii_type="ssn", value="***-**-****", position=(match.start(), match.end()))
            )

        # Detect credit cards
        for pattern in self._cc_patterns:
            for match in pattern.finditer(text):
                # Basic Luhn check to reduce false positives
                digits = "".join(c for c in match.group() if c.isdigit())
                if self._luhn_check(digits):
                    matches.append(
                        PIIMatch(
                            pii_type="credit_card",
                            value="****-****-****-****",
                            position=(match.start(), match.end()),
                        )
                    )

        # Detect IP addresses
        for match in self._ip_pattern.finditer(text):
            # Validate IP format
            parts = match.group().split(".")
            if all(0 <= int(p) <= 255 for p in parts):
                matches.append(
                    PIIMatch(
                        pii_type="ip_address",
                        value="***.***.***.***",
                        position=(match.start(), match.end()),
                    )
                )

        return matches

    def redact(self, text: str) -> tuple[str, list[PIIMatch]]:
        """
        Redact PII from text.

        Args:
            text: Text to redact

        Returns:
            Tuple of (redacted_text, pii_matches)
        """
        matches = self.detect(text)

        # Sort by position (reverse order to preserve positions)
        matches.sort(key=lambda m: m.position[0], reverse=True)

        redacted_text = text
        for match in matches:
            start, end = match.position
            redacted_text = (
                redacted_text[:start] + f"[{match.pii_type.upper()}]" + redacted_text[end:]
            )

        return redacted_text, matches

    async def detect_async(self, text: str) -> list[PIIMatch]:
        """Async version of detect (for future API integration)"""
        return self.detect(text)

    def _luhn_check(self, card_number: str) -> bool:
        """Luhn algorithm for credit card validation"""

        def digits_of(n):
            return [int(d) for d in str(n)]

        digits = digits_of(card_number)
        odd_digits = digits[-1::-2]
        even_digits = digits[-2::-2]
        checksum = sum(odd_digits)
        for d in even_digits:
            checksum += sum(digits_of(d * 2))
        return checksum % 10 == 0
