"""
backend/utils/card_generator.py — Synthetic Test ID Card Generator for Database Verification.

Generates mathematically valid domestic Indian ID documents (Aadhaar & PAN)
for any citizen registered in the National Identity Database so that verification
pipelines can be instantly tested and demonstrated end-to-end.
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import Optional

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from database import get_citizen_by_id


def generate_citizen_card_image(
    citizen_id: str,
    doc_type: str = "AADHAAR",
) -> bytes:
    """
    Generate an authentic identity card image for a database-registered citizen.

    Args:
        citizen_id: e.g. "CITIZEN-IND-001"
        doc_type: "AADHAAR" or "PAN"

    Returns:
        JPEG bytes of the rendered identity card.
    """
    citizen = get_citizen_by_id(citizen_id)
    if not citizen:
        raise ValueError(f"Citizen with ID '{citizen_id}' not found in database.")

    # Base card dimensions (Standard CR80 aspect ratio ~ 85.6mm x 53.98mm)
    w, h = 900, 560
    card = Image.new("RGB", (w, h), color=(250, 252, 255))
    draw = ImageDraw.Draw(card)

    font_large = ImageFont.load_default()
    font_med = ImageFont.load_default()
    font_small = ImageFont.load_default()

    if doc_type.upper() == "PASSPORT":
        # ── Republic of India Passport Biodata Page Layout ──
        # Top banner with emblem and official passport title
        draw.rectangle([0, 0, w, 80], fill=(15, 30, 60))
        draw.rectangle([0, 80, w, 84], fill=(212, 175, 55))  # Gold foil accent line
        draw.text((30, 18), "REPUBLIC OF INDIA / भारत गणराज्य", fill=(255, 255, 255), font=font_large)
        draw.text((30, 48), "PASSPORT / पासपोर्ट", fill=(212, 175, 55), font=font_med)

        # Top passport metadata strip
        draw.text((400, 20), "Type / प्रकार: P", fill=(200, 220, 245), font=font_small)
        draw.text((540, 20), "Country Code / कोड: IND", fill=(200, 220, 245), font=font_small)
        draw.text((400, 48), f"Passport No.: {citizen.get('passport_number', 'V1234567')}", fill=(255, 255, 255), font=font_large)

        # Photo Box (Left)
        draw.rectangle([45, 110, 235, 350], fill=(230, 238, 248), outline=(100, 120, 160), width=2)
        draw.ellipse([90, 140, 190, 240], fill=(150, 175, 205))
        draw.ellipse([70, 250, 210, 360], fill=(120, 145, 180))
        draw.text((105, 320), "PHOTO", fill=(250, 250, 250), font=font_small)

        # Demographic Fields (Right)
        start_x = 265
        curr_y = 105
        draw.text((start_x, curr_y), "Surname / उपनाम:", fill=(100, 110, 120), font=font_small)
        draw.text((start_x, curr_y + 16), citizen.get("surname", citizen["name"].split()[-1]).upper(), fill=(15, 23, 42), font=font_large)

        curr_y += 44
        draw.text((start_x, curr_y), "Given Name(s) / दिया गया नाम:", fill=(100, 110, 120), font=font_small)
        draw.text((start_x, curr_y + 16), citizen.get("given_name", citizen["name"].split()[0]).upper(), fill=(15, 23, 42), font=font_large)

        curr_y += 44
        draw.text((start_x, curr_y), "Nationality / राष्ट्रीयता:", fill=(100, 110, 120), font=font_small)
        draw.text((start_x + 240, curr_y), "Sex / लिंग:", fill=(100, 110, 120), font=font_small)
        draw.text((start_x, curr_y + 16), "INDIAN", fill=(15, 23, 42), font=font_med)
        draw.text((start_x + 240, curr_y + 16), citizen.get("sex", citizen["gender"][0].upper()), fill=(15, 23, 42), font=font_med)

        curr_y += 44
        draw.text((start_x, curr_y), "Date of Birth / जन्म तिथि:", fill=(100, 110, 120), font=font_small)
        draw.text((start_x + 240, curr_y), "Place of Birth / जन्म स्थान:", fill=(100, 110, 120), font=font_small)
        draw.text((start_x, curr_y + 16), citizen["dob"], fill=(15, 23, 42), font=font_med)
        draw.text((start_x + 240, curr_y + 16), citizen.get("passport_place_of_birth", citizen["city"]).upper(), fill=(15, 23, 42), font=font_med)

        curr_y += 44
        draw.text((start_x, curr_y), "Date of Issue / जारी करने की तिथि:", fill=(100, 110, 120), font=font_small)
        draw.text((start_x + 240, curr_y), "Date of Expiry / समाप्ति की तिथि:", fill=(100, 110, 120), font=font_small)
        draw.text((start_x, curr_y + 16), citizen.get("passport_issue_date", "13/08/2023"), fill=(15, 23, 42), font=font_med)
        draw.text((start_x + 240, curr_y + 16), citizen.get("passport_expiry_date", "12/08/2033"), fill=(15, 23, 42), font=font_med)

        curr_y += 44
        draw.text((start_x, curr_y), "Place of Issue / जारी करने का स्थान:", fill=(100, 110, 120), font=font_small)
        draw.text((start_x, curr_y + 16), citizen.get("passport_place_of_issue", citizen["city"]).upper(), fill=(15, 23, 42), font=font_med)

        # Ghost portrait
        draw.ellipse([760, 120, 860, 240], fill=(240, 245, 255), outline=(200, 215, 235), width=1)
        draw.text((785, 175), "GHOST", fill=(160, 175, 195), font=font_small)

        # ── Machine Readable Zone (MRZ) ──
        # Standard ICAO Doc 9303 (2 lines x 44 chars)
        mrz_box_y = 445
        draw.rectangle([20, mrz_box_y, w - 20, h - 15], fill=(255, 255, 255), outline=(180, 190, 200), width=1)
        mrz_l1 = citizen.get("passport_mrz_l1", "P<INDSIGHANIA<<ARADHANA<<<<<<<<<<<<<<<<<<<<<")
        mrz_l2 = citizen.get("passport_mrz_l2", "V1234567<3IND0308131F3308121<<<<<<<<<<<<<<<2")
        draw.text((35, mrz_box_y + 18), mrz_l1, fill=(10, 10, 10), font=font_large)
        draw.text((35, mrz_box_y + 52), mrz_l2, fill=(10, 10, 10), font=font_large)

    elif doc_type.upper() == "PAN":
        # ── Income Tax Department PAN Card Layout ──
        # Header banner (Blue gradient)
        draw.rectangle([0, 0, w, 75], fill=(20, 60, 110))
        draw.rectangle([0, 75, w, 82], fill=(218, 165, 32))  # Gold accent strip
        draw.text((25, 20), "INCOME TAX DEPARTMENT", fill=(255, 255, 255), font=font_large)
        draw.text((25, 45), "GOVT. OF INDIA / PERMANENT ACCOUNT NUMBER CARD", fill=(200, 225, 255), font=font_small)

        # Portrait Photo Box
        draw.rectangle([45, 120, 225, 340], fill=(220, 230, 242), outline=(100, 120, 150), width=2)
        # Draw face avatar placeholder
        draw.ellipse([85, 150, 185, 250], fill=(160, 180, 205))
        draw.ellipse([65, 260, 205, 360], fill=(130, 150, 180))
        draw.text((95, 315), "PHOTO", fill=(240, 240, 250), font=font_small)

        # Content details
        start_x = 265
        draw.text((start_x, 120), "NAME / Name:", fill=(100, 100, 100), font=font_small)
        draw.text((start_x, 140), citizen["name"].upper(), fill=(15, 23, 42), font=font_large)

        draw.text((start_x, 185), "FATHER'S NAME / Father's Name:", fill=(100, 100, 100), font=font_small)
        draw.text((start_x, 205), f"{citizen['name'].split()[-1].upper()} SENIOR", fill=(15, 23, 42), font=font_large)

        draw.text((start_x, 250), "DATE OF BIRTH / Date of Birth:", fill=(100, 100, 100), font=font_small)
        draw.text((start_x, 270), citizen["dob"], fill=(15, 23, 42), font=font_large)

        # PAN Number Banner
        draw.rectangle([start_x, 330, start_x + 350, 385], fill=(235, 243, 255), outline=(59, 130, 246), width=1)
        draw.text((start_x + 15, 338), "Permanent Account Number:", fill=(70, 90, 120), font=font_small)
        draw.text((start_x + 15, 355), citizen["pan_number"], fill=(10, 37, 84), font=font_large)

        # Hologram / Emblem Simulation
        draw.ellipse([700, 130, 830, 260], fill=(240, 240, 210), outline=(200, 180, 80), width=2)
        draw.text((725, 185), "HOLOGRAM", fill=(150, 130, 30), font=font_small)

        # Signature Area
        draw.rectangle([start_x, 430, start_x + 280, 490], fill=(255, 255, 255), outline=(180, 180, 180), width=1)
        draw.text((start_x + 20, 455), citizen["name"], fill=(30, 40, 100), font=font_med)
        draw.text((start_x + 20, 495), "Signature / हस्ताक्षर", fill=(120, 120, 120), font=font_small)

        # QR pattern placeholder
        draw.rectangle([700, 330, 830, 460], fill=(255, 255, 255), outline=(0, 0, 0), width=2)
        for rx in range(710, 820, 15):
            for ry in range(340, 450, 15):
                if (rx + ry) % 30 == 0:
                    draw.rectangle([rx, ry, rx + 10, ry + 10], fill=(0, 0, 0))

    else:
        # ── UIDAI Aadhaar Card Layout ──
        # Header banner (Tricolour strip + Govt Emblem banner)
        draw.rectangle([0, 0, w, 12], fill=(255, 153, 51))   # Saffron
        draw.rectangle([0, 12, w, 24], fill=(255, 255, 255)) # White
        draw.rectangle([0, 24, w, 36], fill=(19, 136, 8))    # Green

        draw.rectangle([0, 36, w, 95], fill=(240, 244, 250))
        draw.text((30, 45), "Government of India / भारत सरकार", fill=(20, 30, 50), font=font_med)
        draw.text((30, 70), "Unique Identification Authority of India / UIDAI", fill=(70, 80, 100), font=font_small)

        # Portrait Photo Box
        draw.rectangle([45, 130, 235, 370], fill=(225, 235, 245), outline=(180, 195, 210), width=2)
        draw.ellipse([90, 160, 190, 260], fill=(160, 185, 210))
        draw.ellipse([70, 275, 210, 385], fill=(130, 155, 185))
        draw.text((105, 340), "UIDAI", fill=(250, 250, 250), font=font_small)

        # Content details
        start_x = 265
        draw.text((start_x, 135), "To / Name:", fill=(100, 110, 120), font=font_small)
        draw.text((start_x, 155), citizen["name"], fill=(15, 23, 42), font=font_large)

        draw.text((start_x, 195), f"DOB: {citizen['dob']} ({citizen['dob_formatted']})", fill=(30, 41, 59), font=font_med)
        draw.text((start_x, 225), f"Gender: {citizen['gender']}", fill=(30, 41, 59), font=font_med)

        draw.text((start_x, 265), "Address:", fill=(100, 110, 120), font=font_small)
        addr_lines = [
            citizen["street"],
            f"{citizen['city']}, {citizen['state']} - {citizen['pincode']}"
        ]
        curr_y = 285
        for line in addr_lines:
            draw.text((start_x, curr_y), line, fill=(30, 41, 59), font=font_small)
            curr_y += 20

        # QR Code representation (with UIDAI format)
        draw.rectangle([680, 135, 840, 295], fill=(255, 255, 255), outline=(30, 41, 59), width=2)
        # Deterministic pseudo-QR modules
        for qx in range(690, 830, 14):
            for qy in range(145, 285, 14):
                if (qx * 3 + qy * 7) % 23 < 12:
                    draw.rectangle([qx, qy, qx + 10, qy + 10], fill=(0, 0, 0))
        draw.text((705, 305), "UIDAI Secure QR", fill=(100, 116, 139), font=font_small)

        # Aadhaar Number in Large Centered Red/Bold Box
        draw.rectangle([45, 410, w - 45, 490], fill=(254, 242, 242), outline=(239, 68, 68), width=2)
        draw.text((w // 2 - 140, 422), "Your Aadhaar No. / आपका आधार क्रमांक:", fill=(153, 27, 27), font=font_small)
        draw.text((w // 2 - 120, 445), citizen["aadhaar_number"], fill=(185, 28, 28), font=font_large)

        # Footer
        draw.rectangle([0, 520, w, h], fill=(241, 245, 249))
        draw.text((w // 2 - 130, 532), "मेरा आधार, मेरी पहचान (Mera Aadhaar, Meri Pehchan)", fill=(100, 116, 139), font=font_small)

    buf = io.BytesIO()
    card.save(buf, format="JPEG", quality=95)
    return buf.getvalue()
