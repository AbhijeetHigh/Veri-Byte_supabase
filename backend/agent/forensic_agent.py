"""
agent/forensic_agent.py — Document Screening Pipeline (Gatekeeper & Format Validated).

Pipeline stages:
1. **Biometric Verification / Gatekeeper** — face match against selfie (if provided).
   Supports both Full Identity Verification (with selfie) and Document-Only Screening.
2. **Deepfake / AI-Generation Detection** — neural SigLIP classifier + CV ensemble.
3. **OCR / MRZ & Format Extraction** — extracts text, parses identity fields,
   and verifies format rules and cryptographic checksums (entity codes for PAN,
   and MRZ check digits for Passports).
4. **Tampering Detection** — Error Level Analysis (ELA) with layout-aware zones + EXIF inspection.
5. **Verdict & Forensic Report** — deterministic decision matrix -> APPROVED / REJECT / MANUAL REVIEW.

``run_analysis()`` is a generator yielding :class:`agent.types.StepUpdate` dicts.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Generator, List, Optional, Tuple

import cv2
import numpy as np
import pytesseract
from PIL import Image, ImageChops

import config
from agent.types import (
    BiometricResult,
    OcrResult,
    StepUpdate,
    TamperResult,
    Verdict,
)

# InsightFace engine
from agent.face_engine import compare_faces

# Deepfake / AI-generation detector
from agent.deepfake_detector import detect_deepfake

# Domestic ID validation algorithms
from utils.verhoeff import validate_aadhaar, validate_pan, validate_vid

# National Identity Database cross-verification
from database import verify_against_database

logger = logging.getLogger(__name__)
pytesseract.pytesseract.tesseract_cmd = config.TESSERACT_CMD

try:
    from passporteye import read_mrz
    HAS_PASSPORTEYE: bool = True
except ImportError:
    HAS_PASSPORTEYE = False
    logger.info("passporteye not installed — MRZ extraction unavailable")


# ── Public API ──────────────────────────────────────────────────

def run_analysis(
    id_path: str,
    selfie_path: Optional[str] = None,
) -> Generator[StepUpdate, None, None]:
    """
    Run the full forensic analysis pipeline on an identity document (+ optional selfie).

    Pipeline order
    --------------
    1. Biometric Gatekeeper  — if selfie provided, compare faces; if score < 50% -> halt.
                               If selfie omitted, run in Document-Only Screening Mode.
    2. Deepfake / AI check   — if confidence >= DEEPFAKE_REJECT_THRESHOLD -> halt.
    3. OCR / MRZ extraction  — parse text, detect ID type, and validate document format.
    4. Tampering detection   — ELA heatmap + EXIF metadata inspection.
    5. Verdict               — deterministic decision matrix -> APPROVED / REJECT / MANUAL REVIEW.

    Args:
        id_path:     Absolute filesystem path to the uploaded identity document image.
        selfie_path: Optional filesystem path to the live selfie image.

    Yields:
        :class:`~agent.types.StepUpdate` dicts, one per stage transition.
    """
    results: dict = {}

    # ── Step 1: Biometric Verification ────────────────────────
    if not selfie_path:
        yield {
            "step": "biometric",
            "status": "complete",
            "message": "Document-Only Screening Mode (Live selfie omitted)",
        }
        results["biometric"] = {
            "match_confidence": 100.0,
            "raw_verified": True,
            "document_only": True,
        }
    else:
        yield {"step": "biometric", "status": "running", "message": "Running Gatekeeper Face Match..."}
        bio_result = _verify_face(id_path, selfie_path)
        results["biometric"] = bio_result

        if bio_result.get("error"):
            yield {"step": "biometric", "status": "error", "message": bio_result["error"]}
            verdict = "REJECT"
            reasons = [f"Gatekeeper failed: {bio_result['error']}"]
            yield {
                "step": "verdict", "status": "complete", "message": "Rejected by Gatekeeper",
                "verdict": verdict, "report": _build_report(results, verdict, reasons), "results": results,
            }
            return

        score = bio_result.get("match_confidence", 0.0)
        if score < config.BIOMETRIC_REJECT_THRESHOLD:
            yield {"step": "biometric", "status": "error", "message": f"Match Failed: {score:.1f}%"}
            verdict = "REJECT"
            reasons = [f"Gatekeeper blocked: Biometric match ({score:.1f}%) is below the {config.BIOMETRIC_REJECT_THRESHOLD}% threshold."]
            yield {
                "step": "verdict", "status": "complete", "message": "Rejected by Gatekeeper",
                "verdict": verdict, "report": _build_report(results, verdict, reasons), "results": results,
            }
            return

        yield {"step": "biometric", "status": "complete", "message": f"Gatekeeper Passed: {score:.1f}%"}


    # ── Step 2: Deepfake / AI-Generated Image Detection ────────────
    yield {"step": "deepfake", "status": "running", "message": f"Analysing document photo with {config.DEEPFAKE_MODEL_NAME}..."}
    deepfake_result = detect_deepfake(id_path)
    results["deepfake"] = deepfake_result

    if deepfake_result.get("error"):
        yield {
            "step": "deepfake", "status": "error",
            "message": f"Detection error (skipped): {deepfake_result['error']}",
        }
    else:
        df_confidence = deepfake_result.get("confidence", 0.0)
        df_is_ai = deepfake_result.get("is_ai_generated", False)

        if df_is_ai or df_confidence > config.DEEPFAKE_REJECT_THRESHOLD:
            yield {
                "step": "deepfake", "status": "error",
                "message": f"AI-Generated Image Detected (AI possibility: {df_confidence:.1f}% > {config.DEEPFAKE_REJECT_THRESHOLD:.0f}%) - REJECTED",
            }
            verdict = "REJECT"
            reasons = [
                f"Flagged AI Generated: AI possibility ({df_confidence:.1f}%) > {config.DEEPFAKE_REJECT_THRESHOLD:.0f}% threshold - rejected."
            ]
            yield {
                "step": "verdict", "status": "complete", "message": "Rejected: Flagged AI Generated",
                "verdict": verdict, "report": _build_report(results, verdict, reasons), "results": results,
            }
            return
        elif df_confidence > config.DEEPFAKE_REVIEW_THRESHOLD:
            yield {
                "step": "deepfake", "status": "error",
                "message": f"Flagged Suspicious: AI possibility ({df_confidence:.1f}% > {config.DEEPFAKE_REVIEW_THRESHOLD:.0f}%) - flagged for manual review",
            }
        else:
            yield {
                "step": "deepfake", "status": "complete",
                "message": f"Real Photo Verified ({config.DEEPFAKE_REVIEW_THRESHOLD:.0f}% threshold)",
            }


    # ── Step 3: OCR / MRZ Extraction & Document Format Validation ─────
    yield {"step": "ocr", "status": "running", "message": "Extracting text & validating document format..."}
    ocr_result = _extract_document_data(id_path)
    results["ocr"] = ocr_result

    if not ocr_result["format_valid"]:
        first_err = (
            ocr_result.get("validation_reasons", ["Format validation failed"])[0]
        )
        yield {
            "step": "ocr", "status": "error",
            "message": f"Detected {ocr_result['id_type']} — INVALID FORMAT: {first_err}",
        }
    elif ocr_result["confidence"] < config.OCR_CONFIDENCE_THRESHOLD:
        yield {
            "step": "ocr", "status": "error",
            "message": f"Low-confidence extraction ({ocr_result['confidence']:.0f}%) — image may be low quality",
        }
    else:
        db_v = ocr_result.get("database_verification", {})
        if db_v.get("status") == "VERIFIED_MATCH":
            cit_name = db_v.get("matched_citizen", {}).get("name", "")
            msg = f"Detected {ocr_result['id_type']} — Format Valid & Database Verified ({cit_name})"
        elif db_v.get("status") == "DEMOGRAPHIC_MISMATCH":
            msg = f"Detected {ocr_result['id_type']} — Database Mismatch: {db_v.get('discrepancies', ['Discrepancy'])[0]}"
        else:
            msg = f"Detected {ocr_result['id_type']} — Format Valid (confidence {ocr_result['confidence']:.0f}%)"

        yield {
            "step": "ocr", "status": "complete",
            "message": msg,
        }


    # ── Step 4: Tampering Detection ───────────────────────────
    yield {"step": "tampering", "status": "running", "message": "Running Error Level Analysis + metadata check..."}
    tamper_result = _detect_tampering(id_path, ocr_result["id_type"])
    results["tampering"] = tamper_result

    tamper_msg = f"Integrity: {tamper_result['integrity_status']}"
    if tamper_result["flagged_zones"]:
        tamper_msg += f" — flagged: {', '.join(tamper_result['flagged_zones'])}"
    yield {
        "step": "tampering",
        "status": "complete" if tamper_result["integrity_status"] == "CLEAN" else "error",
        "message": tamper_msg,
    }


    # ── Step 5: Verdict ───────────────────────────────────────
    yield {"step": "verdict", "status": "running", "message": "Applying forensic decision matrix..."}
    results["database_verification"] = results.get("ocr", {}).get("database_verification", {})
    verdict, reasons = _apply_decision_matrix(results)
    report = _build_report(results, verdict, reasons)
    yield {
        "step": "verdict", "status": "complete", "message": f"Final verdict: {verdict}",
        "verdict": verdict, "report": report, "results": results,
    }


# ── Step Implementations ────────────────────────────────────────

def _verify_face(id_path: str, selfie_path: str) -> BiometricResult:
    """Compare using InsightFace engine with raw image bytes."""
    try:
        with open(id_path, "rb") as f1, open(selfie_path, "rb") as f2:
            ref_bytes = f1.read()
            live_bytes = f2.read()

        result = compare_faces(ref_bytes, live_bytes)
        return {
            "match_confidence": result["similarity_score"],
            "raw_verified": result["similarity_score"] >= config.BIOMETRIC_REJECT_THRESHOLD,
        }
    except Exception as exc:
        logger.error("Face verification failed", exc_info=True)
        return {"error": f"Face verification failed: {exc}", "match_confidence": 0}


def _preprocess_for_ocr(id_path: str) -> Image.Image:
    """Preprocess document image with scaling and contrast normalization for high Tesseract accuracy."""
    try:
        cv_img = cv2.imread(id_path)
        if cv_img is None:
            return Image.open(id_path)
        gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
        h, w = gray.shape
        # Upscale smaller images for sharper text strokes
        if w < 1200 or h < 1200:
            scale = 2.0
            gray = cv2.resize(gray, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_CUBIC)
        # Normalize contrast
        norm = cv2.normalize(gray, None, alpha=0, beta=255, norm_type=cv2.NORM_MINMAX)
        return Image.fromarray(norm)
    except Exception as exc:
        logger.warning("Image preprocessing for OCR encountered an issue: %s", exc)
        return Image.open(id_path)


def _scan_and_validate_qr(id_path: str, expected_id: Optional[str] = None) -> Tuple[str, Optional[str]]:
    """Scan document image for barcodes/QR codes using zxingcpp and OpenCV."""
    try:
        import zxingcpp
        img = Image.open(id_path)
        barcodes = zxingcpp.read_barcodes(img)
        if not barcodes:
            # Try contrast-enhanced upscaled version
            cv_img = cv2.imread(id_path)
            if cv_img is not None:
                gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
                resized = cv2.resize(gray, (0, 0), fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)
                barcodes = zxingcpp.read_barcodes(resized)

        if barcodes:
            b = barcodes[0]
            txt = b.text or ""
            if "<PrintLetterBarcodeData" in txt or "uid=" in txt or "uidai" in txt.lower():
                return "Official UIDAI Secure QR Code detected", txt
            elif txt.startswith("http://") or txt.startswith("https://"):
                if "uidai.gov.in" in txt:
                    return "Official UIDAI Web URL in QR Code", txt
                return f"Suspicious Non-Government URL in QR code: {txt[:40]}...", txt
            return f"Decoded Barcode/QR ({len(txt)} chars)", txt
        return "No decodable QR code found (or damaged / compressed)", None
    except Exception as exc:
        return f"QR code scanning skipped: {exc}", None


def _extract_document_data(id_path: str) -> OcrResult:
    """
    Extract document text via Tesseract OCR, identify document type,
    parse identity fields, and execute format and checksum validations:
    - Format validation for Indian Aadhaar numbers and Virtual IDs (VID).
    - Entity classification code checks for PAN cards.
    - MRZ check-digit verification for Passports.
    """
    pil_img = _preprocess_for_ocr(id_path)

    raw_text: str = pytesseract.image_to_string(pil_img, config=config.TESSERACT_CONFIG)
    data = pytesseract.image_to_data(
        pil_img, config=config.TESSERACT_CONFIG, output_type=pytesseract.Output.DICT,
    )
    confidences = [int(c) for c in data["conf"] if str(c) not in ("-1", "")]
    ocr_confidence: float = sum(confidences) / len(confidences) if confidences else 0.0

    # If confidence is low, attempt fallback to raw image
    if ocr_confidence < 30.0:
        try:
            raw_img = Image.open(id_path)
            raw_text2 = pytesseract.image_to_string(raw_img, config=config.TESSERACT_CONFIG)
            if len(raw_text2) > len(raw_text):
                raw_text = raw_text2
        except Exception:
            pass

    # 1. Check MRZ for Passports
    if HAS_PASSPORTEYE:
        try:
            mrz = read_mrz(str(id_path))
            if mrz is not None:
                mrz_data = mrz.to_dict()
                checksum_valid = bool(mrz_data.get("valid_score", 0) >= 80)
                reasons = (
                    ["Passport MRZ check-digits valid"]
                    if checksum_valid
                    else ["Passport MRZ checksum failed validation (tampered or counterfeit)"]
                )
                pass_res = {
                    "id_type": "Passport",
                    "confidence": ocr_confidence,
                    "raw_text": raw_text.strip(),
                    "fields": {
                        "name": f"{mrz_data.get('surname', '')} {mrz_data.get('names', '')}".strip(),
                        "passport_number": mrz_data.get("number", ""),
                        "nationality": mrz_data.get("nationality", ""),
                        "date_of_birth": mrz_data.get("date_of_birth", ""),
                        "date_of_expiry": mrz_data.get("expiration_date", ""),
                        "gender": mrz_data.get("sex", ""),
                        "checksum_status": "PASSED" if checksum_valid else "FAILED",
                    },
                    "format_valid": checksum_valid,
                    "validation_reasons": reasons,
                }
                pass_res["database_verification"] = verify_against_database(pass_res)
                return pass_res
        except Exception:
            logger.debug("MRZ extraction failed — falling back to domestic ID rules", exc_info=True)

    detected_type: Optional[str] = None
    matched_value: Optional[str] = None
    validation_reasons: List[str] = []
    format_valid: bool = True
    fields: dict = {}

    # Aadhaar document indicators
    aadhaar_keywords = ["aadhaar", "आधार", "unique identification", "enrolment no", "uidai", "mera aadhaar", "मेरी पहचान"]
    is_aadhaar_text = any(kw in raw_text.lower() for kw in aadhaar_keywords)
    aadhaar_matches = re.findall(r"\b([2-9]\d{3}\s?\d{4}\s?\d{4})(?!\s?\d)\b", raw_text)
    aadhaar_match = aadhaar_matches[0] if aadhaar_matches else None
    if not aadhaar_match:
        fallback_m = re.search(r"\b([2-9]\d{3}\s?\d{4}\s?\d{4})\b", raw_text)
        if fallback_m:
            aadhaar_match = fallback_m.group(1)
            aadhaar_matches = [aadhaar_match]

    # PAN document indicators
    pan_keywords = ["income tax", "permanent account number", "govt. of india", "father's name"]
    is_pan_text = any(kw in raw_text.lower() for kw in pan_keywords)
    pan_match = re.search(r"\b([A-Z]{5}[0-9]{4}[A-Z])\b", raw_text)

    # Voter ID indicators
    voter_keywords = ["election commission", "elector photo", "identity card", "epic"]
    is_voter_text = any(kw in raw_text.lower() for kw in voter_keywords)
    voter_match = re.search(r"\b([A-Z]{3}[0-9]{7})\b", raw_text)

    if aadhaar_matches or is_aadhaar_text:
        detected_type = "AADHAAR"
        if aadhaar_matches:
            # Check all candidate occurrences (e.g. letter and wallet card) to find the valid one
            chosen_adh = None
            chosen_msg = ""
            for cand in aadhaar_matches:
                cleaned_cand = cand.replace(" ", "").strip()
                cand_val, cand_msg = validate_aadhaar(cleaned_cand)
                if cand_val:
                    chosen_adh = cleaned_cand
                    chosen_msg = cand_msg
                    break

            if chosen_adh:
                matched_value = chosen_adh
                fields["id_number"] = f"{chosen_adh[:4]} {chosen_adh[4:8]} {chosen_adh[8:]}"
                validation_reasons.append(chosen_msg)
            else:
                raw_adh = aadhaar_matches[0].replace(" ", "").strip()
                matched_value = raw_adh
                fields["id_number"] = f"{raw_adh[:4]} {raw_adh[4:8]} {raw_adh[8:]}"
                _, err_msg = validate_aadhaar(raw_adh)
                format_valid = False
                validation_reasons.append(err_msg)
        else:
            format_valid = False
            validation_reasons.append("Document indicates Aadhaar but 12-digit UIDAI number could not be recognized")

        # Check Virtual ID (VID)
        vid_match = re.search(r"VID\s*[:\s]\s*([0-9\s]{16,23})", raw_text)
        if vid_match:
            vid_clean = vid_match.group(1).replace(" ", "").strip()
            if len(vid_clean) == 16:
                fields["vid"] = f"{vid_clean[:4]} {vid_clean[4:8]} {vid_clean[8:12]} {vid_clean[12:]}"
                is_vid_val, vid_msg = validate_vid(vid_clean)
                if not is_vid_val:
                    format_valid = False
                    validation_reasons.append(vid_msg)
                else:
                    validation_reasons.append("Virtual ID (VID) format verified")

        # Check Enrolment Number
        enrol_match = re.search(r"Enrolment\s*No\.?[\s:]*([0-9/\s]{14,22})", raw_text, re.IGNORECASE)
        if enrol_match:
            fields["enrolment_no"] = enrol_match.group(1).strip()

        # Check Name
        name_match = re.search(r"(?:To\s*\n\s*|Name[:\s]*)([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)", raw_text)
        if name_match:
            fields["name"] = name_match.group(1).strip()

        # Check Gender
        gender_match = re.search(r"\b(Male|Female|Transgender)\b", raw_text, re.IGNORECASE)
        if gender_match:
            fields["gender"] = gender_match.group(1).capitalize()

        # Scan QR Code
        qr_status, qr_text = _scan_and_validate_qr(id_path, matched_value)
        fields["qr_code_status"] = qr_status
        if "Suspicious" in qr_status:
            format_valid = False
            validation_reasons.append(qr_status)

    elif pan_match or is_pan_text:
        detected_type = "PAN"
        if pan_match:
            matched_value = pan_match.group(1).upper().strip()
            fields["id_number"] = matched_value
            is_valid, msg = validate_pan(matched_value)
            if not is_valid:
                format_valid = False
                validation_reasons.append(msg)
            else:
                validation_reasons.append(msg)
        else:
            format_valid = False
            validation_reasons.append("Document indicates PAN card but valid 10-character PAN was not found")

    elif voter_match or is_voter_text:
        detected_type = "VOTER_ID"
        if voter_match:
            matched_value = voter_match.group(1).upper().strip()
            fields["id_number"] = matched_value
            validation_reasons.append("Voter ID EPIC pattern valid")
        else:
            format_valid = False
            validation_reasons.append("Document indicates Voter ID but EPIC number could not be found")

    else:
        for doc_type, spec in config.REGEX_PATTERNS.items():
            match = re.search(spec["pattern"], raw_text)
            if match:
                detected_type = doc_type
                matched_value = spec["clean"](match.group())
                fields["id_number"] = matched_value
                break

        if not detected_type:
            detected_type = "National ID (unrecognized format)"
            format_valid = False
            validation_reasons.append("No recognized government identity format detected")

    # Extract DOB
    dob_match = re.search(r"(?:DOB|Date of Birth|Birth)[\s:/]+(\d{2}[/\-\.]\d{2}[/\-\.]\d{4})", raw_text, re.IGNORECASE)
    if dob_match:
        fields["date_of_birth"] = dob_match.group(1)
    else:
        for pattern in config.DOB_PATTERNS:
            m = re.search(pattern, raw_text)
            if m:
                fields["date_of_birth"] = m.group()
                break

    fields["checksum_status"] = "PASSED" if format_valid else "FAILED"

    ocr_res = {
        "id_type": detected_type,
        "confidence": ocr_confidence,
        "raw_text": raw_text.strip(),
        "fields": fields,
        "format_valid": format_valid,
        "validation_reasons": validation_reasons,
    }
    ocr_res["database_verification"] = verify_against_database(ocr_res)
    return ocr_res


def _detect_tampering(id_path: str, id_type: str) -> TamperResult:
    """Run Error Level Analysis (ELA) using adaptive document layout zones."""
    original = Image.open(id_path).convert("RGB")
    w_orig, h_orig = original.size
    is_portrait = h_orig > (w_orig * 1.2)

    if id_type == "Passport":
        zones = config.PASSPORT_ZONES
        critical = config.CRITICAL_FIELDS_PASSPORT
    elif id_type == "AADHAAR" and is_portrait:
        zones = getattr(config, "AADHAAR_LETTER_ZONES", config.ID_DOCUMENT_ZONES)
        critical = getattr(config, "CRITICAL_FIELDS_AADHAAR_LETTER", config.CRITICAL_FIELDS_ID)
    else:
        zones = config.ID_DOCUMENT_ZONES
        critical = config.CRITICAL_FIELDS_ID

    ela_path = str(config.TEMP_DIR / f"ela_{Path(id_path).stem}.jpg")
    original.save(ela_path, "JPEG", quality=config.ELA_QUALITY)
    resaved = Image.open(ela_path)
    diff = ImageChops.difference(original, resaved)

    diff_np = np.array(diff).astype(int)
    ela_visual = Image.fromarray(
        np.clip(diff_np * config.ELA_SCALE_FACTOR, 0, 255).astype("uint8"),
    )
    ela_visual.save(ela_path)

    gray_diff = np.array(diff.convert("L"))
    h, w = gray_diff.shape

    flagged_zones: List[str] = []
    for zone_name, (y0, y1, x0, x1) in zones.items():
        region = gray_diff[int(y0 * h) : int(y1 * h), int(x0 * w) : int(x1 * w)]
        if region.size and np.sum(region > config.ELA_SENSITIVITY) > config.ELA_MIN_REGION_AREA:
            flagged_zones.append(zone_name)

    suspicious_software: Optional[str] = None
    try:
        exif = original.getexif()
        software_tag = exif.get(305)
        if software_tag:
            for sw in config.SUSPICIOUS_SOFTWARE:
                if sw in str(software_tag).lower():
                    suspicious_software = software_tag
                    break
    except Exception:
        logger.debug("Failed to read EXIF data", exc_info=True)

    critical_flagged = [z for z in flagged_zones if z in critical]

    if suspicious_software or critical_flagged:
        integrity_status = "TAMPERED"
    elif flagged_zones:
        integrity_status = "SUSPICIOUS"
    else:
        integrity_status = "CLEAN"

    return {
        "integrity_status": integrity_status,
        "flagged_zones": flagged_zones,
        "critical_flagged": critical_flagged,
        "suspicious_software": suspicious_software,
        "ela_image_path": ela_path,
    }


def _apply_decision_matrix(results: dict) -> Tuple[Verdict, List[str]]:
    """Deterministic forensic decision matrix."""
    reasons: List[str] = []
    ocr: dict = results.get("ocr", {})
    tamper: dict = results.get("tampering", {})
    bio: dict = results.get("biometric", {})
    deepfake: dict = results.get("deepfake", {})

    # 1. Deepfake check (reject if >80%, review if >66%)
    df_confidence: float = deepfake.get("confidence", 0.0)
    review_df = False

    if df_confidence > config.DEEPFAKE_REJECT_THRESHOLD:
        reasons.append(f"AI possibility ({df_confidence:.1f}%) > {config.DEEPFAKE_REJECT_THRESHOLD:.0f}% - flagged AI Generated and rejected")
        return "REJECT", reasons
    elif df_confidence > config.DEEPFAKE_REVIEW_THRESHOLD:
        reasons.append(f"Flagged Suspicious: AI possibility ({df_confidence:.1f}%) > {config.DEEPFAKE_REVIEW_THRESHOLD:.0f}% - requires manual review")
        review_df = True

    # 2. Checksum / Format validation
    format_invalid = not ocr.get("format_valid", True)
    if format_invalid:
        val_reasons = ocr.get("validation_reasons") or ["Document failed cryptographic / checksum verification"]
        for vr in val_reasons:
            if vr not in reasons:
                reasons.append(vr)

    # 3. Tampering
    critical_tamper = bool(tamper.get("critical_flagged"))
    if critical_tamper:
        reasons.append(f"Tampering detected in critical field(s): {', '.join(tamper['critical_flagged'])}")
    if tamper.get("suspicious_software"):
        reasons.append(f"Image metadata shows editing software: {tamper['suspicious_software']}")
        critical_tamper = True

    # Fast-fail REJECT on invalid checksum or critical tampering
    if format_invalid or critical_tamper:
        return "REJECT", reasons

    # 4. Review thresholds
    low_ocr_conf = ocr.get("confidence", 0) < config.OCR_CONFIDENCE_THRESHOLD
    is_doc_only = bio.get("document_only", False)
    bio_score: float = bio.get("match_confidence", 0.0)
    review_bio = (not is_doc_only) and (config.BIOMETRIC_REJECT_THRESHOLD <= bio_score < config.BIOMETRIC_REVIEW_THRESHOLD)

    # 5. Database Cross-Verification check
    db_ver = ocr.get("database_verification", {})
    review_db = False
    if db_ver.get("status") == "DEMOGRAPHIC_MISMATCH":
        for disc in db_ver.get("discrepancies", []):
            reasons.append(f"Database discrepancy: {disc}")
        review_db = True
    elif db_ver.get("status") == "VERIFIED_MATCH":
        cit = db_ver.get("matched_citizen", {})
        reasons.append(f"National Identity Database verified: Confirmed authentic record for {cit.get('name')} ({cit.get('id')})")

    if low_ocr_conf:
        reasons.append("OCR confidence too low for guaranteed certainty")
    if review_bio:
        reasons.append(f"Biometric match in review range: {bio_score:.1f}%")

    if low_ocr_conf or review_bio or review_df or review_db:
        return "MANUAL REVIEW", reasons

    reasons.append("All forensic and cryptographic integrity checks passed successfully")
    return "APPROVED", reasons


def _build_report(results: dict, verdict: Verdict, reasons: List[str]) -> str:
    """Build structured Markdown forensic screening report."""
    ocr: dict = results.get("ocr", {})
    tamper: dict = results.get("tampering", {})
    bio: dict = results.get("biometric", {})
    deepfake: dict = results.get("deepfake", {})

    lines: List[str] = [
        "# Forensic Document Screening Report",
        f"**Verdict:** {verdict}",
        "",
        "## Document Analysis",
        f"- Type: {ocr.get('id_type', 'Unknown')}",
        f"- Extraction confidence: {ocr.get('confidence', 0):.0f}%",
        f"- Cryptographic Checksum Status: **{'VALID' if ocr.get('format_valid', False) else 'INVALID / COUNTERFEIT'}**",
    ]

    val_reasons = ocr.get("validation_reasons", [])
    if val_reasons:
        lines.append("- Validation Details:")
        for vr in val_reasons:
            lines.append(f"  - {vr}")

    fields = ocr.get("fields", {})
    if fields:
        lines.append("- Extracted Identity Fields:")
        for k, v in fields.items():
            if v:
                label = k.replace("_", " ").title()
                lines.append(f"  - {label}: `{v}`")

    lines += [
        "",
        "## Deepfake / AI-Generation Check",
    ]

    if deepfake and "confidence" in deepfake:
        df_conf = deepfake["confidence"]
        if df_conf > config.DEEPFAKE_REJECT_THRESHOLD:
            verdict_label = "AI-GENERATED (REJECTED)"
        elif df_conf > config.DEEPFAKE_REVIEW_THRESHOLD:
            verdict_label = "SUSPICIOUS (MANUAL REVIEW)"
        else:
            verdict_label = "REAL"
        lines.append(f"- Result: **{verdict_label}**")
        lines.append(f"- AI possibility: {df_conf:.1f}%")
        if deepfake.get("model_name"):
            lines.append(f"- Primary model: `{deepfake['model_name']}`")
        if deepfake.get("signals"):
            lines.append("- Signal breakdown:")
            signal_labels = {
                "neural_detector":    f"Neural Model ({config.DEEPFAKE_MODEL_NAME})",
                "texture_uniformity": "Face Texture Uniformity",
                "fft_score":          "FFT Frequency Smoothness",
                "skin_uniformity":    "YCbCr Skin Tone Uniformity",
                "symmetry_score":     "Facial Landmark Symmetry",
            }
            for sig_key, sig_val in deepfake["signals"].items():
                label = signal_labels.get(sig_key, sig_key)
                lines.append(f"  - {label}: {sig_val:.1f}/100")
    elif deepfake.get("error"):
        lines.append(f"- Detection skipped: {deepfake['error']}")
    else:
        lines.append("- Not performed")

    lines += [
        "",
        "## Tampering & Integrity Check",
        f"- Integrity: {tamper.get('integrity_status', 'Unknown')}",
        f"- Flagged zones: {', '.join(tamper.get('flagged_zones', [])) or 'None'}",
    ]
    if tamper.get("suspicious_software"):
        lines.append(f"- Metadata warning: Editing software detected (`{tamper['suspicious_software']}`)")

    lines += [
        "",
        "## Biometric Verification",
    ]

    if bio.get("document_only"):
        lines.append("- Mode: **Document-Only Screening** (Live selfie omitted)")
    elif bio and "match_confidence" in bio:
        lines.append(f"- Match confidence: {bio['match_confidence']:.1f}%")
    else:
        lines.append("- Skipped or Blocked")

    # National Identity Database Registry Cross-Verification
    db_ver = ocr.get("database_verification", {})
    if db_ver and db_ver.get("record_found"):
        cit = db_ver.get("matched_citizen", {})
        lines += [
            "",
            "## National Identity Database Verification",
            f"- Registry Status: **{db_ver.get('status')}**",
            f"- Matched Citizen: **{cit.get('name')}** (ID: `{cit.get('id')}`)",
            f"- Registered Birth Date: {cit.get('dob_formatted')} (`{cit.get('dob')}`)",
            f"- Registered Address: {cit.get('address')}",
            f"- Official Aadhaar UIDAI: `{cit.get('aadhaar_number')}`",
            f"- Official PAN (Income Tax): `{cit.get('pan_number')}`",
            f"- Issuing Authority: {cit.get('issuing_authority')}",
        ]
        if db_ver.get("discrepancies"):
            lines.append("- Discrepancy Warnings:")
            for disc in db_ver["discrepancies"]:
                lines.append(f"  - ⚠️ {disc}")
    elif db_ver:
        lines += [
            "",
            "## National Identity Database Verification",
            "- Registry Status: **UNREGISTERED**",
            "- Note: Identity document was not matched against the 5-person National Identity Database.",
        ]

    lines += ["", "## Forensic Findings & Reasoning", *[f"- {r}" for r in reasons]]
    return "\n".join(lines)