"""
agent/face_engine.py — InsightFace Biometric Verification Engine.

Provides high-accuracy face embedding extraction and cosine similarity matching
using the InsightFace library (buffalo_l model pack).
"""

from __future__ import annotations

import logging
import os
from typing import Optional

import cv2
import numpy as np
from insightface.app import FaceAnalysis

logger = logging.getLogger(__name__)

# Lazy-loaded singleton so server boots in <1 second and stays well under memory limits
_FACE_APP: Optional[FaceAnalysis] = None


def get_face_app() -> FaceAnalysis:
    """Return cached FaceAnalysis instance, loading models on demand with memory-conscious settings."""
    global _FACE_APP
    if _FACE_APP is None:
        det_size = int(os.environ.get("INSIGHTFACE_DET_SIZE", "320"))
        logger.info("Initializing InsightFace (allowed_modules=['detection', 'recognition'], det_size=%s)...", det_size)
        app = FaceAnalysis(
            name="buffalo_l",
            allowed_modules=["detection", "recognition"],
            providers=["CPUExecutionProvider"],
        )
        app.prepare(ctx_id=0, det_size=(det_size, det_size))
        _FACE_APP = app
    return _FACE_APP


def _bytes_to_cv2(image_bytes: bytes) -> np.ndarray:
    """Convert raw image bytes into an OpenCV BGR numpy array."""
    np_arr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Failed to decode image bytes. Ensure the file is a valid image.")
    return img


def compare_faces(reference_bytes: bytes, live_bytes: bytes) -> dict:
    """
    Compare a reference image (ID card) to a live image (selfie) using InsightFace.

    Args:
        reference_bytes: Raw binary content of the ID reference image.
        live_bytes: Raw binary content of the live capture selfie.

    Returns:
        A dictionary containing the similarity score (0–100) and match status.
    """
    face_app = get_face_app()

    # 1. Decode bytes to OpenCV format
    ref_img = _bytes_to_cv2(reference_bytes)
    live_img = _bytes_to_cv2(live_bytes)

    # 2. Extract faces and embeddings
    ref_faces = face_app.get(ref_img)
    live_faces = face_app.get(live_img)

    if not ref_faces:
        raise ValueError("No face detected in the reference identity document.")
    if not live_faces:
        raise ValueError("No face detected in the live camera capture.")

    # Select the primary (largest) face from each image
    ref_face = max(ref_faces, key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]))
    live_face = max(live_faces, key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]))

    ref_emb = ref_face.embedding
    live_emb = live_face.embedding

    # 3. Calculate Cosine Similarity
    dot_product = np.dot(ref_emb, live_emb)
    norm_ref = np.linalg.norm(ref_emb)
    norm_live = np.linalg.norm(live_emb)

    if norm_ref == 0 or norm_live == 0:
        similarity_score = 0.0
    else:
        cosine_sim = dot_product / (norm_ref * norm_live)
        # InsightFace cosine similarity typically ranges from -1 to 1. 
        # Map it to a 0–100 percentage scale (clamped between 0 and 100).
        similarity_score = float(np.clip(cosine_sim * 100.0, 0.0, 100.0))

    return {
        "similarity_score": round(similarity_score, 2),
        "matched": similarity_score >= 90.0,
    }