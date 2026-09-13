"""
utils/verhoeff.py — National ID Format Validators & Verhoeff Algorithm.

Verhoeff algorithm — used by UIDAI for Aadhaar checksum validation.
Detects single-digit errors and most transposition/twin errors that
a simple mod-10 or Luhn check would miss.

Validates Indian identity documents (Aadhaar, Virtual IDs, PAN cards).
Format validation according to UIDAI and Income Tax Department specifications.
"""

from __future__ import annotations

import re
from typing import Optional, Tuple

# ── Verhoeff Algorithm Tables ───────────────────────────────────

# Multiplication table (d)
D_TABLE = [
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
    [1, 2, 3, 4, 0, 6, 7, 8, 9, 5],
    [2, 3, 4, 0, 1, 7, 8, 9, 5, 6],
    [3, 4, 0, 1, 2, 8, 9, 5, 6, 7],
    [4, 0, 1, 2, 3, 9, 5, 6, 7, 8],
    [5, 9, 8, 7, 6, 0, 4, 3, 2, 1],
    [6, 5, 9, 8, 7, 1, 0, 4, 3, 2],
    [7, 6, 5, 9, 8, 2, 1, 0, 4, 3],
    [8, 7, 6, 5, 9, 3, 2, 1, 0, 4],
    [9, 8, 7, 6, 5, 4, 3, 2, 1, 0],
]

# Permutation table (p)
P_TABLE = [
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
    [1, 5, 7, 6, 2, 8, 3, 0, 9, 4],
    [5, 8, 0, 3, 7, 9, 6, 1, 4, 2],
    [8, 9, 1, 6, 0, 4, 3, 5, 2, 7],
    [9, 4, 5, 3, 1, 2, 6, 8, 7, 0],
    [4, 2, 8, 6, 5, 7, 3, 9, 0, 1],
    [2, 7, 9, 3, 8, 0, 6, 4, 1, 5],
    [7, 0, 4, 6, 9, 1, 3, 2, 5, 8],
]

# Inverse table
INV_TABLE = [0, 4, 3, 2, 1, 5, 6, 7, 8, 9]


def _checksum(digits: str) -> int:
    """Run the Verhoeff algorithm over a digit string, right to left."""
    cleaned = str(digits).strip().replace(" ", "").replace("-", "")
    if not cleaned.isdigit():
        return -1
    c = 0
    for i, ch in enumerate(reversed(cleaned)):
        c = D_TABLE[c][P_TABLE[i % 8][int(ch)]]
    return c


def generate_check_digit(num_str: str) -> int:
    """
    Given the first 11 digits (or full 12-digit Aadhaar), compute the Verhoeff check digit.
    If 12 digits are passed, automatically slices the first 11 digits to return the 12th check digit.
    """
    cleaned = str(num_str).strip().replace(" ", "").replace("-", "")
    if not cleaned.isdigit():
        raise ValueError(f"Expected numeric digits, got '{num_str}'")
    if len(cleaned) >= 12:
        cleaned = cleaned[:11]
    c = 0
    for i, ch in enumerate(reversed(cleaned)):
        c = D_TABLE[c][P_TABLE[(i + 1) % 8][int(ch)]]
    return INV_TABLE[c]


def is_valid_aadhaar(aadhaar: str) -> bool:
    """
    Validates a 12-digit Aadhaar number's Verhoeff checksum.
    Returns False on anything malformed — no exceptions thrown for bad input.
    """
    aadhaar = str(aadhaar).strip().replace(" ", "").replace("-", "")
    if not aadhaar.isdigit() or len(aadhaar) != 12:
        return False
    return _checksum(aadhaar) == 0


# ── Domain-Specific Identity Validators ─────────────────────────

def validate_aadhaar(number: str) -> Tuple[bool, str]:
    """
    Validate an Indian Aadhaar number format:
    1. Exactly 12 numeric digits.
    2. Cannot begin with '0' or '1'.
    3. Cannot be all identical digits (e.g. 222222222222).
    4. Verhoeff checksum validation.

    Returns:
        (is_valid, reason_or_message)
    """
    cleaned = str(number).strip().replace(" ", "").replace("-", "")

    if len(cleaned) != 12 or not cleaned.isdigit():
        return False, f"Aadhaar must be exactly 12 digits (found {len(cleaned)})"

    if cleaned[0] in ("0", "1"):
        return False, "Aadhaar number cannot start with 0 or 1"

    if len(set(cleaned)) == 1:
        return False, "Aadhaar number cannot be all identical digits"

    if not is_valid_aadhaar(cleaned):
        return False, "Invalid Aadhaar checksum (Verhoeff check failed)"

    return True, "Valid UIDAI Aadhaar number format (Verhoeff checksum passed)"


def validate_vid(vid: str) -> Tuple[bool, str]:
    """
    Validate a 16-digit UIDAI Virtual ID (VID) format.

    Returns:
        (is_valid, reason_or_message)
    """
    cleaned = str(vid).strip().replace(" ", "").replace("-", "")

    if len(cleaned) != 16 or not cleaned.isdigit():
        return False, f"Virtual ID (VID) must be exactly 16 digits (found {len(cleaned)})"

    return True, "Valid UIDAI Virtual ID format"


def validate_pan(pan: str) -> Tuple[bool, str]:
    """
    Validate an Indian Permanent Account Number (PAN):
    - Exactly 10 alphanumeric characters.
    - Pattern: [A-Z]{5}[0-9]{4}[A-Z].
    - 4th character must be a valid entity code:
      P (Individual), C (Company), H (HUF), A (AOP), B (BOI),
      G (Government), J (Artificial Juridical), L (Local Authority),
      F (Firm/LLP), T (Trust).

    Returns:
        (is_valid, reason_or_message)
    """
    cleaned = str(pan).strip().upper()
    if not re.match(r"^[A-Z]{5}[0-9]{4}[A-Z]$", cleaned):
        return False, "PAN must follow format: 5 letters, 4 digits, 1 letter"

    entity_code = cleaned[3]
    valid_entities = {
        "P": "Individual",
        "C": "Company",
        "H": "Hindu Undivided Family (HUF)",
        "A": "Association of Persons (AOP)",
        "B": "Body of Individuals (BOI)",
        "G": "Government Agency",
        "J": "Artificial Juridical Person",
        "L": "Local Authority",
        "F": "Firm / LLP",
        "T": "Trust",
    }

    if entity_code not in valid_entities:
        return False, f"Invalid 4th character '{entity_code}' — not a recognized Income Tax entity code"

    return True, f"Valid PAN format (Entity: {valid_entities[entity_code]})"


if __name__ == "__main__":
    # Test vector 1: UIDAI sample sanity vector
    test_valid = "234123412346"
    test_invalid = "234123412340"

    print(f"Sanity test: {test_valid} -> valid: {is_valid_aadhaar(test_valid)}")
    print(f"Sanity test: {test_invalid} -> valid: {is_valid_aadhaar(test_invalid)}")

    first_11 = "23412341234"
    cd = generate_check_digit(first_11)
    print(f"Check digit for {first_11} -> {cd}")

    print("\n--- Card Verification (Synthetic Test Vector) ---")
    card_aadhaar = "9999 1234 5678"
    print(f"Aadhaar Number: {card_aadhaar}")
    print(f"is_valid_aadhaar: {is_valid_aadhaar(card_aadhaar)}")
    is_val, msg = validate_aadhaar(card_aadhaar)
    print(f"validate_aadhaar: {is_val} ({msg})")

    # Compute check digit on leading 11 digits or full card number
    computed_cd = generate_check_digit("9999 1234 567")
    print(f"Computed 12th check digit for '9999 1234 567' -> {computed_cd} (Matches card's last digit: {card_aadhaar[-1]})")
