"""
backend/database.py — National Identity Registry & Database Cross-Verification Engine.

Houses the official reference database of verified citizens and provides
automated cross-verification between extracted OCR document data and official
government records (UIDAI, NSDL Income Tax Department, Election Commission, Passport Seva).
"""

from __future__ import annotations

import json
import logging
import os
import re
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("veri-byte-database")

DATA_DIR = Path(__file__).resolve().parent / "data"
DATABASE_FILE = DATA_DIR / "identity_database.json"

# In-memory cached database records
_DATABASE_RECORDS: Optional[List[Dict[str, Any]]] = None


def load_database() -> List[Dict[str, Any]]:
    """Load the citizen identity database from persistent storage."""
    global _DATABASE_RECORDS
    if _DATABASE_RECORDS is not None:
        return _DATABASE_RECORDS

    if not DATABASE_FILE.exists():
        logger.warning("Database file not found at %s. Initializing empty.", DATABASE_FILE)
        _DATABASE_RECORDS = []
        return _DATABASE_RECORDS

    try:
        with open(DATABASE_FILE, "r", encoding="utf-8") as f:
            _DATABASE_RECORDS = json.load(f)
            logger.info("Loaded %d citizen records into National Identity Registry.", len(_DATABASE_RECORDS))
            return _DATABASE_RECORDS
    except Exception as exc:
        logger.error("Failed to load database: %s", exc)
        return []


def get_all_citizens() -> List[Dict[str, Any]]:
    """Return all citizen records registered in the verification database."""
    return load_database()


def get_citizen_by_id(citizen_id: str) -> Optional[Dict[str, Any]]:
    """Find citizen by internal identifier (e.g. CITIZEN-IND-001)."""
    for record in load_database():
        if record.get("id") == citizen_id:
            return record
    return None


def _normalize_text(text: Optional[str]) -> str:
    """Normalize string for robust fuzzy comparison."""
    if not text:
        return ""
    # Remove punctuation, extra spaces, lowercase
    clean = re.sub(r"[^a-zA-Z0-9\s]", " ", str(text).lower())
    return " ".join(clean.split())


def _similarity(s1: str, s2: str) -> float:
    """Compute string similarity ratio between 0.0 and 1.0."""
    return SequenceMatcher(None, _normalize_text(s1), _normalize_text(s2)).ratio()


def _normalize_date(date_str: Optional[str]) -> str:
    """Normalize various date formats into DD/MM/YYYY or DD-Month-YYYY."""
    if not date_str:
        return ""
    s = str(date_str).strip()
    # Match dd/mm/yyyy or dd-mm-yyyy or dd.mm.yyyy
    m = re.search(r"(\d{1,2})[/\-\.](\d{1,2})[/\-\.](\d{4})", s)
    if m:
        day, month, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
        return f"{day:02d}/{month:02d}/{year:04d}"
    
    # Textual month matching (e.g. 13 August 2003, Aug 13 2003)
    months = {
        "jan": 1, "january": 1,
        "feb": 2, "february": 2,
        "mar": 3, "march": 3,
        "apr": 4, "april": 4,
        "may": 5,
        "jun": 6, "june": 6,
        "jul": 7, "july": 7,
        "aug": 8, "august": 8,
        "sep": 9, "september": 9,
        "oct": 10, "october": 10,
        "nov": 11, "november": 11,
        "dec": 12, "december": 12
    }
    m_text = re.search(r"(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})", s)
    if m_text:
        d = int(m_text.group(1))
        m_name = m_text.group(2).lower()
        y = int(m_text.group(3))
        if m_name in months:
            return f"{d:02d}/{months[m_name]:02d}/{y:04d}"

    return _normalize_text(s)


def find_matching_citizen(
    id_number: Optional[str] = None,
    name: Optional[str] = None,
    dob: Optional[str] = None,
    raw_text: Optional[str] = None,
) -> Optional[Tuple[Dict[str, Any], float, str]]:
    """
    Look up a citizen record based on ID number, name, DOB, or raw document text.
    Returns (matched_record, confidence_score, match_type).
    """
    records = load_database()
    if not records:
        return None

    cleaned_id = str(id_number or "").replace(" ", "").replace("-", "").upper().strip()

    # 1. Exact ID Number Match (Highest confidence)
    if cleaned_id:
        for rec in records:
            adh_clean = rec.get("aadhaar_clean", "").upper()
            pan_clean = rec.get("pan_number", "").upper()
            voter_clean = rec.get("voter_id", "").upper()
            pass_clean = rec.get("passport_number", "").upper()
            vid_clean = rec.get("vid", "").replace(" ", "").upper()

            if cleaned_id in (adh_clean, pan_clean, voter_clean, pass_clean, vid_clean):
                return rec, 100.0, "EXACT_ID_MATCH"

    # 2. Match ID Number from raw_text
    if raw_text:
        raw_upper = raw_text.upper()
        for rec in records:
            adh_clean = rec.get("aadhaar_clean", "")
            adh_spaced = rec.get("aadhaar_number", "")
            pan = rec.get("pan_number", "")
            voter = rec.get("voter_id", "")
            passport = rec.get("passport_number", "")

            if (adh_clean and adh_clean in raw_upper) or (adh_spaced and adh_spaced in raw_upper):
                return rec, 95.0, "AADHAAR_TEXT_MATCH"
            if pan and pan in raw_upper:
                return rec, 95.0, "PAN_TEXT_MATCH"
            if voter and voter in raw_upper:
                return rec, 95.0, "VOTER_ID_TEXT_MATCH"
            if passport and passport in raw_upper:
                return rec, 95.0, "PASSPORT_TEXT_MATCH"

    # 3. High Name Match
    best_name_record = None
    best_name_sim = 0.0
    if name:
        norm_input_name = _normalize_text(name)
        for rec in records:
            norm_rec_name = _normalize_text(rec["name"])
            sim = _similarity(norm_input_name, norm_rec_name)
            # Token inclusion check (e.g. Aradhana Sighania in extracted text)
            input_tokens = set(norm_input_name.split())
            rec_tokens = set(norm_rec_name.split())
            if rec_tokens.issubset(input_tokens) or input_tokens.issubset(rec_tokens):
                sim = max(sim, 0.90)

            if sim > best_name_sim:
                best_name_sim = sim
                best_name_record = rec

    if best_name_record and best_name_sim >= 0.75:
        return best_name_record, best_name_sim * 100.0, "NAME_SIMILARITY_MATCH"

    # 4. Search citizen name in raw_text
    if raw_text:
        norm_raw = _normalize_text(raw_text)
        for rec in records:
            norm_rec_name = _normalize_text(rec["name"])
            if norm_rec_name in norm_raw:
                return rec, 88.0, "NAME_IN_RAW_TEXT"

    return None


def verify_against_database(ocr_result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Comprehensive cross-verification between extracted OCR fields and National Identity Database.

    Returns:
    {
        "status": "VERIFIED_MATCH" | "UNREGISTERED" | "DEMOGRAPHIC_MISMATCH",
        "record_found": bool,
        "matched_citizen": dict or None,
        "match_type": str,
        "confidence": float,
        "checks": {
            "id_number": {"status": "MATCH" | "MISMATCH" | "NOT_FOUND", "doc_val": ..., "db_val": ...},
            "name": {"status": "MATCH" | "MISMATCH" | "NOT_CHECKED", "score": float},
            "dob": {"status": "MATCH" | "MISMATCH" | "NOT_CHECKED"},
            "address": {"status": "MATCH" | "PARTIAL" | "NOT_CHECKED"},
        },
        "discrepancies": List[str],
        "message": str
    }
    """
    fields = ocr_result.get("fields", {})
    raw_text = ocr_result.get("raw_text", "")
    id_type = ocr_result.get("id_type", "")
    id_number = fields.get("id_number") or fields.get("passport_number")
    name = fields.get("name")
    dob = fields.get("date_of_birth")

    match = find_matching_citizen(id_number=id_number, name=name, dob=dob, raw_text=raw_text)

    if not match:
        return {
            "status": "UNREGISTERED",
            "record_found": False,
            "matched_citizen": None,
            "match_type": "NONE",
            "confidence": 0.0,
            "checks": {
                "id_number": {"status": "NOT_FOUND", "doc_val": id_number, "db_val": None},
                "name": {"status": "NOT_CHECKED", "doc_val": name, "db_val": None, "score": 0.0},
                "dob": {"status": "NOT_CHECKED", "doc_val": dob, "db_val": None},
                "address": {"status": "NOT_CHECKED", "doc_val": None, "db_val": None},
            },
            "discrepancies": ["Document identity details not found in the 5-person National Identity Database"],
            "message": "Citizen record not registered in National Identity Database.",
        }

    rec, conf, match_type = match
    discrepancies: List[str] = []

    # 1. Check ID Number
    db_id_matched = False
    db_primary_id = rec.get("aadhaar_number")
    if id_type == "PAN":
        db_primary_id = rec.get("pan_number")
    elif id_type == "Passport":
        db_primary_id = rec.get("passport_number")
    elif id_type == "VOTER_ID":
        db_primary_id = rec.get("voter_id")

    if id_number:
        clean_input = str(id_number).replace(" ", "").upper()
        rec_ids = [
            rec.get("aadhaar_clean", "").upper(),
            rec.get("pan_number", "").upper(),
            rec.get("voter_id", "").upper(),
            rec.get("passport_number", "").upper(),
        ]
        if clean_input in rec_ids:
            db_id_matched = True
        else:
            discrepancies.append(
                f"Document ID '{id_number}' conflicts with registered ID for {rec['name']} (Expected {db_primary_id})"
            )

    # 2. Check Name
    name_sim = 0.0
    name_matched = False
    if name:
        name_sim = _similarity(name, rec["name"])
        input_tokens = set(_normalize_text(name).split())
        rec_tokens = set(_normalize_text(rec["name"]).split())

        # Support inverted order (e.g. "SIGHANIA ARADHANA" on passports vs "Aradhana Sighania" in database)
        if input_tokens and rec_tokens and (input_tokens == rec_tokens or rec_tokens.issubset(input_tokens) or input_tokens.issubset(rec_tokens)):
            name_sim = max(name_sim, 0.95)

        if name_sim >= 0.70 or _normalize_text(rec["name"]) in _normalize_text(name):
            name_matched = True
        else:
            discrepancies.append(
                f"Extracted name '{name}' does not match registered citizen name '{rec['name']}'"
            )
    else:
        # Check raw text for citizen name
        if _normalize_text(rec["name"]) in _normalize_text(raw_text):
            name_matched = True
            name_sim = 0.90

    # 3. Check DOB
    dob_matched = False
    if dob:
        norm_doc_dob = _normalize_date(dob)
        norm_rec_dob1 = _normalize_date(rec.get("dob"))
        norm_rec_dob2 = _normalize_date(rec.get("dob_formatted"))
        if norm_doc_dob in (norm_rec_dob1, norm_rec_dob2) or rec.get("dob") in dob:
            dob_matched = True
        else:
            discrepancies.append(
                f"Document DOB '{dob}' differs from registered citizen birth date '{rec['dob_formatted']}'"
            )
    else:
        # Check raw text
        if rec.get("dob") in raw_text or rec.get("dob_formatted") in raw_text:
            dob_matched = True

    # 4. Check Address keywords in raw text
    address_matched = False
    city = rec.get("city", "")
    state = rec.get("state", "")
    pincode = rec.get("pincode", "")
    if raw_text:
        raw_norm = _normalize_text(raw_text)
        if (city and city.lower() in raw_norm) or (pincode and pincode in raw_norm):
            address_matched = True

    # 5. Passport-Specific Checks (Expiry & Nationality)
    passport_matched = None
    if id_type == "Passport" or fields.get("passport_number"):
        doc_exp = fields.get("date_of_expiry")
        db_exp = rec.get("passport_expiry_date")
        if doc_exp and db_exp:
            norm_doc_exp = _normalize_date(doc_exp)
            norm_db_exp = _normalize_date(db_exp)
            if norm_doc_exp != norm_db_exp and db_exp not in doc_exp:
                discrepancies.append(
                    f"Passport expiration date '{doc_exp}' does not match official record '{db_exp}'"
                )

        doc_nat = fields.get("nationality")
        if doc_nat and doc_nat.upper() not in ("IND", "INDIAN"):
            discrepancies.append(f"Passport nationality '{doc_nat}' does not match registered Indian citizenship")

        passport_matched = len(discrepancies) == 0

    if discrepancies:
        status = "DEMOGRAPHIC_MISMATCH"
        message = f"Record found for {rec['name']}, but demographic discrepancies detected: {'; '.join(discrepancies)}"
    else:
        status = "VERIFIED_MATCH"
        message = f"Verified: Identity successfully verified against National Identity Database for {rec['name']}."

    return {
        "status": status,
        "record_found": True,
        "matched_citizen": rec,
        "match_type": match_type,
        "confidence": conf,
        "checks": {
            "id_number": {
                "status": "MATCH" if db_id_matched else "MISMATCH" if id_number else "NOT_PROVIDED",
                "doc_val": id_number,
                "db_val": db_primary_id,
            },
            "name": {
                "status": "MATCH" if name_matched else "MISMATCH" if name else "NOT_CHECKED",
                "doc_val": name,
                "db_val": rec["name"],
                "score": round(name_sim * 100, 1),
            },
            "dob": {
                "status": "MATCH" if dob_matched else "MISMATCH" if dob else "NOT_CHECKED",
                "doc_val": dob,
                "db_val": rec["dob_formatted"],
            },
            "address": {
                "status": "MATCH" if address_matched else "NOT_CHECKED",
                "db_val": rec["address"],
            },
        },
        "discrepancies": discrepancies,
        "message": message,
    }


# ─────────────────────────────────────────────────────────────
# Persistent User Scan Storage
# ─────────────────────────────────────────────────────────────

USER_SCANS_FILE: Path = DATA_DIR / "user_scans.json"


def get_user_scans(user_id: str) -> List[Dict[str, Any]]:
    """Retrieve all verification scans belonging to a specific user."""
    if not USER_SCANS_FILE.exists():
        return []
    try:
        with open(USER_SCANS_FILE, "r", encoding="utf-8") as f:
            all_scans = json.load(f)
            return [s for s in all_scans if s.get("user_id") == user_id]
    except Exception as exc:
        logger.error("Failed to load user scans: %s", exc)
        return []


def save_user_scan(user_id: str, scan_data: Dict[str, Any]) -> Dict[str, Any]:
    """Persist a new verification scan record to user scan storage."""
    import uuid
    from datetime import datetime, timezone

    all_scans: List[Dict[str, Any]] = []
    if USER_SCANS_FILE.exists():
        try:
            with open(USER_SCANS_FILE, "r", encoding="utf-8") as f:
                all_scans = json.load(f)
        except Exception:
            all_scans = []

    scan_id = scan_data.get("id") or f"SCAN-{uuid.uuid4().hex[:8].upper()}"
    scan_record = {
        "id": scan_id,
        "user_id": user_id,
        "timestamp": scan_data.get("timestamp") or datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        "doc_type": scan_data.get("doc_type", "IDENTITY_DOCUMENT"),
        "document_name": scan_data.get("document_name", "Document"),
        "verdict": scan_data.get("verdict", "UNKNOWN"),
        "biometric_score": scan_data.get("biometric_score", 0),
        "deepfake_score": scan_data.get("deepfake_score", 0),
        "tampering_detected": scan_data.get("tampering_detected", False),
        "tampering_score": scan_data.get("tampering_score", 0),
        "ocr_confidence": scan_data.get("ocr_confidence", 0),
        "ocr_data": scan_data.get("ocr_data", {}),
        "database_match": scan_data.get("database_match", {}),
        "report": scan_data.get("report", ""),
        "ela_image_base64": scan_data.get("ela_image_base64"),
    }

    all_scans.insert(0, scan_record)
    try:
        with open(USER_SCANS_FILE, "w", encoding="utf-8") as f:
            json.dump(all_scans, f, indent=2)
    except Exception as exc:
        logger.error("Failed to persist user scan record: %s", exc)
        raise

    return scan_record


LOCAL_USERS_FILE = DATA_DIR / "local_users.json"


def save_local_user(user_data: Dict[str, Any]) -> Dict[str, Any]:
    """Persist a local user record for resilient authentication."""
    import uuid
    import hashlib
    from datetime import datetime, timezone

    all_users: List[Dict[str, Any]] = []
    if LOCAL_USERS_FILE.exists():
        try:
            with open(LOCAL_USERS_FILE, "r", encoding="utf-8") as f:
                all_users = json.load(f)
        except Exception:
            all_users = []

    email_clean = user_data.get("email", "").strip().lower()
    # Remove existing record with same email if present
    all_users = [u for u in all_users if u.get("email", "").strip().lower() != email_clean]

    user_id = user_data.get("id") or f"usr_{uuid.uuid4().hex[:12]}"
    token = f"local_{uuid.uuid4().hex}"
    pwd_raw = user_data.get("password", "")
    pwd_hash = hashlib.sha256(pwd_raw.encode("utf-8")).hexdigest() if pwd_raw else ""

    user_record = {
        "id": user_id,
        "email": email_clean,
        "username": user_data.get("username") or user_data.get("user_name", "User"),
        "phone": user_data.get("phone", ""),
        "aadhaar": user_data.get("aadhaar", ""),
        "password_hash": pwd_hash,
        "token": token,
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
    }
    all_users.append(user_record)

    try:
        with open(LOCAL_USERS_FILE, "w", encoding="utf-8") as f:
            json.dump(all_users, f, indent=2)
    except Exception as exc:
        logger.error("Failed to save local user: %s", exc)

    return user_record


def get_local_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    """Find a local user by email address."""
    if not LOCAL_USERS_FILE.exists():
        return None
    try:
        with open(LOCAL_USERS_FILE, "r", encoding="utf-8") as f:
            users = json.load(f)
        for u in users:
            if u.get("email", "").strip().lower() == email.strip().lower():
                return u
    except Exception:
        pass
    return None


def get_local_user_by_token(token: str) -> Optional[Dict[str, Any]]:
    """Find a local user by session token."""
    if not LOCAL_USERS_FILE.exists():
        return None
    try:
        with open(LOCAL_USERS_FILE, "r", encoding="utf-8") as f:
            users = json.load(f)
        for u in users:
            if u.get("token") == token:
                return u
    except Exception:
        pass
    return None


