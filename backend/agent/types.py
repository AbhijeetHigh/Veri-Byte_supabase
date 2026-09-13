"""
agent/types.py
SIH26188 — Pipeline Data Contracts

TypedDict definitions for every structured dictionary that flows through the
forensic analysis pipeline. These serve as documentation-as-code: any module
that produces or consumes these dicts should reference these types so readers
(and type checkers) know exactly what keys to expect.

Usage::

    from agent.types import OcrResult, TamperResult, BiometricResult

Note: TypedDict is a *static* typing construct — it has zero runtime cost and
does not enforce anything at runtime. It exists purely so that type checkers
(mypy, pyright) and IDEs can catch key-name typos and missing fields.
"""

from __future__ import annotations

from typing import Dict, List, Literal, Optional, TypedDict


# ── OCR / MRZ Extraction ────────────────────────────────────

class OcrFields(TypedDict, total=False):
    """Key-value fields extracted from the document (varies by doc type)."""
    id_number: Optional[str]
    name: Optional[str]
    passport_number: Optional[str]
    nationality: Optional[str]
    date_of_birth: Optional[str]
    date_of_expiry: Optional[str]
    gender: Optional[str]
    vid: Optional[str]
    enrolment_no: Optional[str]
    checksum_status: Optional[str]
    qr_code_status: Optional[str]


class OcrResult(TypedDict):
    """Output of ``_extract_document_data()``."""
    id_type: str                # e.g. "Passport", "AADHAAR", "PAN", ...
    confidence: float           # 0–100, average Tesseract word confidence
    raw_text: str               # full OCR dump (for display / debugging)
    fields: OcrFields           # parsed key-value data
    format_valid: bool          # did the ID number / MRZ checksum pass?
    validation_reasons: List[str]  # Detailed checksum and format validation reasons



# ── Tampering Detection ─────────────────────────────────────

IntegrityStatus = Literal["CLEAN", "SUSPICIOUS", "TAMPERED"]


class TamperResult(TypedDict):
    """Output of ``_detect_tampering()``."""
    integrity_status: IntegrityStatus
    flagged_zones: List[str]            # zone names that exceeded ELA threshold
    critical_flagged: List[str]         # subset of flagged_zones in the critical set
    suspicious_software: Optional[str]  # EXIF software tag, if suspicious
    ela_image_path: str                 # path to the saved ELA heatmap image


# ── Biometric Face Verification ─────────────────────────────

class BiometricResult(TypedDict, total=False):
    """
    Output of ``_verify_face()`` in ``forensic_agent.py``.

    Uses the in-process InsightFace engine (``agent.face_engine.compare_faces``).
    Empty dict when selfie was not provided or face detection failed.
    """
    match_confidence: float     # 0–100 cosine similarity as a percentage
    raw_verified: bool          # True if match_confidence >= BIOMETRIC_REJECT_THRESHOLD
    error: str                  # present only if verification failed


# ── Deepfake / AI-Generated Image Detection ──────────────────

class DeepfakeSignals(TypedDict, total=False):
    """Individual sub-signal scores contributing to the deepfake verdict."""
    neural_detector: float        # SigLIP neural deepfake classifier (higher = more AI-like)
    texture_uniformity: float     # Face crop sharpness uniformity (higher = more AI-like)
    fft_score: float              # FFT frequency smoothness score (higher = more AI-like)
    skin_uniformity: float        # YCbCr chrominance uniformity (higher = more AI-like)
    symmetry_score: float         # Facial landmark symmetry (higher = more AI-like)


class DeepfakeResult(TypedDict, total=False):
    """
    Output of ``_detect_deepfake()`` in ``agent.deepfake_detector``.
    """
    is_ai_generated: bool         # True if image is flagged AI-generated (> 80%)
    is_suspicious: bool           # True if image is flagged suspicious (> 66%)
    confidence: float             # 0–100, probability of being AI-generated
    signals: DeepfakeSignals      # breakdown of each detection sub-signal
    error: str                    # present only if detection failed entirely


# ── Pipeline Step Update (yielded by ``run_analysis()``) ────

StepId = Literal["ocr", "tampering", "biometric", "deepfake", "verdict"]
StepStatus = Literal["running", "complete", "error", "skipped", "pending"]
Verdict = Literal["APPROVED", "REJECT", "MANUAL REVIEW"]


class StepUpdate(TypedDict, total=False):
    """
    Each ``yield`` from ``run_analysis()`` produces one of these.

    Required keys: ``step``, ``status``, ``message``.
    The final ``verdict`` step additionally includes ``verdict``, ``report``,
    and ``results``.
    """
    step: StepId
    status: StepStatus
    message: str
    # Only present on the final "verdict / complete" update:
    verdict: Verdict
    report: str
    results: Dict[str, dict]
