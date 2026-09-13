"""
config.py — Centralised Configuration & Constants.

All tunable thresholds, regex patterns, filesystem paths, and Tesseract
settings live here so that every module pulls from a single source of truth.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Any, Callable, Dict, List, Set, Tuple

# ─────────────────────────────────────────────────────────────
# Filesystem Paths
# ─────────────────────────────────────────────────────────────

BASE_DIR: Path = Path(__file__).resolve().parent
ROOT_DIR: Path = BASE_DIR.parent
TEMP_DIR: Path = BASE_DIR / "temp_uploads"
TEMP_DIR.mkdir(exist_ok=True)
FRONTEND_DIST_DIR: Path = ROOT_DIR / "frontend" / "dist"
PORTAL_DIR: Path = ROOT_DIR / "frontend" / "portal"
_DEFAULT_LOCAL_CORS: str = "http://127.0.0.1:5173,http://localhost:5173,http://127.0.0.1:8000,http://localhost:8000"
_cors_raw = os.environ.get("CORS_ORIGINS", _DEFAULT_LOCAL_CORS)
CORS_ORIGINS: List[str] = [orig.strip() for orig in _cors_raw.split(",") if orig.strip()]



# ─────────────────────────────────────────────────────────────
# Tesseract OCR Binary
# ─────────────────────────────────────────────────────────────

TESSERACT_CMD: str = (
    os.environ.get("TESSERACT_CMD")
    or shutil.which("tesseract")
    or (r"C:\Program Files\Tesseract-OCR\tesseract.exe" if os.name == "nt" else "/usr/bin/tesseract")
)
TESSERACT_CONFIG: str = "--oem 3 --psm 6"
OCR_CONFIDENCE_THRESHOLD: float = 40.0
MRZ_FILLER_MIN_RUN: int = 5


# ─────────────────────────────────────────────────────────────
# Biometric Verification Thresholds
# ─────────────────────────────────────────────────────────────

BIOMETRIC_REJECT_THRESHOLD: float = 50.0
"""Biometric match below 50% → instant REJECT (Gatekeeper blocks the pipeline)."""

BIOMETRIC_REVIEW_THRESHOLD: float = 60.0
"""Biometric match between 50–60% → MANUAL REVIEW. Above 60% → APPROVED."""

# Note: DeepFace variables removed. InsightFace handles its own config.


# ─────────────────────────────────────────────────────────────
# Deepfake / AI-Generated Image Detection Thresholds
# ─────────────────────────────────────────────────────────────

DEEPFAKE_REJECT_THRESHOLD: float = 80.0
"""AI-generated possibility / confidence > 80% -> immediate REJECT (flagged as AI Generated)."""

DEEPFAKE_REVIEW_THRESHOLD: float = 66.0
"""AI-generated possibility / confidence > 66% -> MANUAL REVIEW (flagged as Suspicious). <= 66% approved as real."""

# Toggle for neural classifier. Set ENABLE_NEURAL_DEEPFAKE=false to conserve memory
# and run strictly on lightweight local computer-vision heuristics (texture, FFT, skin, symmetry).
ENABLE_NEURAL_DEEPFAKE: bool = os.environ.get("ENABLE_NEURAL_DEEPFAKE", "true").strip().lower() not in ("0", "false", "no")


# Model repository identifier
DEEPFAKE_MODEL_NAME: str = "prithivMLmods/deepfake-detector-model-v1"

# Weights for the ensemble deepfake signal combiner (must sum to 1.0)
DEEPFAKE_SIGNAL_WEIGHTS: dict = {
    "neural_detector":    0.60,  # prithivMLmods/deepfake-detector-model-v1 (SigLIP-based binary classifier)
    "texture_uniformity": 0.15,  # Face crop sharpness uniformity
    "fft_score":          0.10,  # FFT high-frequency smoothness
    "skin_uniformity":    0.10,  # YCbCr skin tone uniformity
    "symmetry_score":     0.05,  # Facial landmark symmetry
}



# ─────────────────────────────────────────────────────────────
# Error Level Analysis (ELA) Settings
# ─────────────────────────────────────────────────────────────

ELA_QUALITY: int = 90
ELA_SENSITIVITY: int = 25
ELA_SCALE_FACTOR: int = 15
ELA_MIN_REGION_AREA: int = 500


# ─────────────────────────────────────────────────────────────
# Regex Patterns — Domestic National ID Documents
# ─────────────────────────────────────────────────────────────

RegexSpec = Dict[str, Any]

REGEX_PATTERNS: Dict[str, RegexSpec] = {
    "AADHAAR": {
        "pattern": r"[2-9]\d{3}\s?\d{4}\s?\d{4}",
        "description": "12-digit Aadhaar (cannot start with 0 or 1)",
        "clean": lambda m: m.replace(" ", ""),
    },
    "PAN": {
        "pattern": r"[A-Z]{5}[0-9]{4}[A-Z]",
        "description": "10-character PAN (ABCDE1234F format)",
        "clean": lambda m: m.upper().strip(),
    },
    "VOTER_ID": {
        "pattern": r"[A-Z]{3}\d{7}",
        "description": "10-character Voter ID",
        "clean": lambda m: m.upper().strip(),
    },
}

DOB_PATTERNS: List[str] = [
    r"\d{2}[/\-\.]\d{2}[/\-\.]\d{4}",
    r"\d{4}[/\-\.]\d{2}[/\-\.]\d{2}",
]


# ─────────────────────────────────────────────────────────────
# Document Field Zones  (approximate % of image)
# ─────────────────────────────────────────────────────────────

ZoneMap = Dict[str, Tuple[float, float, float, float]]

ID_DOCUMENT_ZONES: ZoneMap = {
    "Photo area":  (0.05, 0.55, 0.02, 0.40),
    "Name field":  (0.10, 0.30, 0.42, 0.98),
    "DOB field":   (0.30, 0.45, 0.42, 0.98),
    "ID Number":   (0.60, 0.85, 0.10, 0.90),
    "Footer/Logo": (0.85, 1.00, 0.00, 1.00),
}

AADHAAR_LETTER_ZONES: ZoneMap = {
    "Top Header / Emblem": (0.00, 0.15, 0.05, 0.95),
    "Address / Demographic": (0.20, 0.45, 0.10, 0.90),
    "QR code area": (0.44, 0.63, 0.50, 0.95),
    "Card Photo area": (0.72, 0.88, 0.12, 0.38),
    "Card Name & DOB": (0.72, 0.86, 0.38, 0.95),
    "Card Aadhaar Number": (0.90, 0.98, 0.15, 0.85),
}

PASSPORT_ZONES: ZoneMap = {
    "Photo area":  (0.05, 0.55, 0.02, 0.35),
    "Data fields": (0.05, 0.55, 0.38, 0.98),
    "MRZ zone":    (0.82, 1.00, 0.02, 0.98),
}

CRITICAL_FIELDS_ID: Set[str] = {"Name field", "DOB field", "ID Number"}
CRITICAL_FIELDS_AADHAAR_LETTER: Set[str] = {"Card Photo area", "Card Name & DOB", "Card Aadhaar Number", "QR code area"}
CRITICAL_FIELDS_PASSPORT: Set[str] = {"Data fields", "MRZ zone", "Photo area"}


# ─────────────────────────────────────────────────────────────
# EXIF — Editing Software Signatures
# ─────────────────────────────────────────────────────────────

SUSPICIOUS_SOFTWARE: List[str] = [
    "photoshop", "gimp", "paint.net", "pixlr",
    "canva", "fotor", "snapseed", "lightroom",
    "affinity", "corel",
]


# ─────────────────────────────────────────────────────────────
# Decision Matrix Specification
# ─────────────────────────────────────────────────────────────

DECISION_MATRIX_SPEC: str = """
Forensic Document Inspector — Fast-Fail Gatekeeper Logic

1. Biometric verification runs FIRST. If score < 50%, REJECT immediately and halt the pipeline.
2. Deepfake check:
   - If AI possibility > 80%, flag as AI Generated and REJECT immediately.
   - If AI possibility > 66%, flag as Suspicious and route for MANUAL REVIEW.
3. Extract and validate the document's text (OCR / MRZ).
4. Analyse the document for digital manipulation (ELA + EXIF metadata).

Decision Matrix:
- REJECT:        Biometric match < 50%, OR AI possibility > 80% (AI Generated), OR
                 tampering in a critical field, OR document format / checksum fails.
- MANUAL REVIEW: AI possibility > 66% (Suspicious), OR OCR/MRZ confidence too low,
                 OR biometric match is 50–60%.
- APPROVED:      All checks pass, AI possibility <= 66%, biometric match > 60%, no tampering detected.
""".strip()