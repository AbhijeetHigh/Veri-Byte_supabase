"""
agent/deepfake_detector.py — Deepfake / AI-Generated Image Detection Engine.

This module detects whether a face or document photo is AI-generated or a real photograph
using the state-of-the-art Hugging Face vision model (prithivMLmods/deepfake-detector-model-v1)
combined with a lightweight, multi-signal ensemble of computer-vision heuristics.

Detection Signals
-----------------
1. **Neural Deepfake Classifier (SigLIP)** (weight 0.60)
   prithivMLmods/deepfake-detector-model-v1 fine-tuned on synthetic & manipulated media
   (SiglipForImageClassification architecture). Provides direct binary classification
   probabilities for "fake" vs "real".

2. **Face Texture Uniformity** (weight 0.15)
   Modern AI generators (StyleGAN, Stable Diffusion) produce images that are
   *uniformly* sharp across every region of the face. Real photos have variable
   sharpness: sharp eyes, softer skin, natural depth-of-field falloff.
   We divide the face crop into a grid and measure CV of local Laplacian
   variance. Low CV = uniform sharpness = AI.

3. **FFT Frequency Smoothness** (weight 0.10)
   AI-generated images are cleaner in high-frequency bands because generative
   models minimise perceptual loss, not reproduce natural sensor noise.

4. **Skin Tone Uniformity in YCbCr** (weight 0.10)
   Real skin has natural chrominance variation (redness, discolouration).
   AI-generated skin is unnaturally uniform in Cb/Cr channels.

5. **Facial Landmark Symmetry** (weight 0.05)
   StyleGAN/GAN faces are near-perfectly symmetric. Real faces are not.

Usage::

    from agent.deepfake_detector import detect_deepfake

    result = detect_deepfake("/path/to/face.jpg")
    print(result["is_ai_generated"], result["confidence"])
"""

from __future__ import annotations

import logging
from typing import Optional

import cv2
import numpy as np
from PIL import Image

import config

logger = logging.getLogger(__name__)

_face_app = None
_classifier = None


def _get_face_app():
    """Return shared cached InsightFace FaceAnalysis instance from face_engine."""
    try:
        from agent.face_engine import get_face_app
        return get_face_app()
    except Exception as exc:
        logger.warning("InsightFace unavailable for deepfake detector: %s", exc)
        return None


def _get_classifier():
    """Return cached Hugging Face image-classification pipeline for deepfake detection."""
    global _classifier
    if not getattr(config, "ENABLE_NEURAL_DEEPFAKE", True):
        logger.info("Neural deepfake detector disabled via ENABLE_NEURAL_DEEPFAKE=false.")
        return None

    if _classifier is None:
        try:
            import torch
            from transformers import pipeline
            device = 0 if torch.cuda.is_available() else -1
            logger.info(
                "Initializing deepfake classification model %s (device=%s)...",
                config.DEEPFAKE_MODEL_NAME,
                device,
            )
            _classifier = pipeline(
                "image-classification",
                model=config.DEEPFAKE_MODEL_NAME,
                device=device,
            )
        except Exception as exc:
            logger.warning(
                "Deepfake neural model %s unavailable: %s",
                config.DEEPFAKE_MODEL_NAME,
                exc,
            )
            _classifier = None
    return _classifier


def _extract_face_crop(img_bgr: np.ndarray) -> np.ndarray:
    """
    Extract face crop from image using InsightFace, or fall back to central crop.
    Adds a 15% margin around the bounding box to capture natural facial context.
    """
    face_app = _get_face_app()
    if face_app is not None:
        try:
            faces = face_app.get(img_bgr)
            if faces:
                x1, y1, x2, y2 = [int(v) for v in faces[0].bbox]
                h, w = img_bgr.shape[:2]
                bw, bh = x2 - x1, y2 - y1
                mx = int(bw * 0.15)
                my = int(bh * 0.15)
                x1, y1 = max(0, x1 - mx), max(0, y1 - my)
                x2, y2 = min(w, x2 + mx), min(h, y2 + my)
                if (x2 - x1) > 20 and (y2 - y1) > 20:
                    return img_bgr[y1:y2, x1:x2]
        except Exception as exc:
            logger.debug("InsightFace crop extraction failed: %s", exc)

    # Fallback: central crop
    h, w = img_bgr.shape[:2]
    my, mx = h // 5, w // 5
    return img_bgr[my:h - my, mx:w - mx]


# -- Public API ---------------------------------------------------------------

def detect_deepfake(image_path: str) -> dict:
    """
    Analyse an image and return a deepfake/AI-generation verdict.

    Combines neural model (prithivMLmods/deepfake-detector-model-v1) and
    CV heuristics.

    Returns dict with keys:
        is_ai_generated: bool
        confidence: float (0-100)
        model_name: Optional[str]
        signals: dict per-signal (0-100, higher = more AI-like)
        error: Optional[str]
    """
    try:
        img_bgr = cv2.imread(str(image_path))
        if img_bgr is None:
            raise ValueError(f"Could not read image at {image_path!r}")

        signals: dict = {}

        # Extract face crop once
        face_crop = _extract_face_crop(img_bgr)

        # Primary Signal: Neural Deepfake Model (prithivMLmods/deepfake-detector-model-v1)
        neural_score = _score_neural_detector(face_crop)
        if neural_score is not None:
            signals["neural_detector"] = neural_score

        # Signal 2: Face Texture Uniformity
        tex_score = _score_texture_uniformity(img_bgr, face_crop=face_crop)
        if tex_score is not None:
            signals["texture_uniformity"] = tex_score

        # Signal 3: FFT High-Frequency Smoothness
        signals["fft_score"] = _score_fft_smoothness(img_bgr)

        # Signal 4: YCbCr Skin Tone Uniformity
        skin_score = _score_skin_uniformity(img_bgr)
        if skin_score is not None:
            signals["skin_uniformity"] = skin_score

        # Signal 5: Facial Landmark Symmetry
        sym_score = _score_face_symmetry(img_bgr)
        if sym_score is not None:
            signals["symmetry_score"] = sym_score

        confidence = _compute_ensemble_confidence(signals)

        return {
            "is_ai_generated": bool(confidence > config.DEEPFAKE_REJECT_THRESHOLD),
            "is_suspicious": bool(confidence > config.DEEPFAKE_REVIEW_THRESHOLD),
            "confidence": float(round(confidence, 2)),
            "model_name": config.DEEPFAKE_MODEL_NAME if "neural_detector" in signals else None,
            "signals": {k: float(round(v, 2)) for k, v in signals.items()},
        }

    except Exception as exc:
        logger.error("Deepfake detection failed", exc_info=True)
        return {
            "is_ai_generated": False,
            "is_suspicious": False,
            "confidence": 0.0,
            "signals": {},
            "error": f"Detection error: {exc}",
        }


# -- Signal Implementations ---------------------------------------------------

def _score_neural_detector(face_crop: np.ndarray) -> Optional[float]:
    """
    Run SigLIP classifier (prithivMLmods/deepfake-detector-model-v1) on the face crop.

    Returns: 0-100 (higher = more AI-like / fake), or None if inference fails.
    """
    classifier = _get_classifier()
    if classifier is None:
        return None

    try:
        crop_rgb = cv2.cvtColor(face_crop, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(crop_rgb)

        predictions = classifier(pil_img)
        # Predictions format: [{'label': 'Fake', 'score': 0.88}, {'label': 'Real', 'score': 0.12}]
        fake_score = None
        real_score = None
        for item in predictions:
            label = str(item.get("label", "")).strip().lower()
            score = float(item.get("score", 0.0))
            if "fake" in label or label == "0" or label == "label_0":
                fake_score = score
            elif "real" in label or label == "1" or label == "label_1":
                real_score = score

        if fake_score is not None:
            ai_prob = fake_score
        elif real_score is not None:
            ai_prob = 1.0 - real_score
        else:
            ai_prob = float(predictions[0].get("score", 0.0))

        return round(ai_prob * 100.0, 2)
    except Exception as exc:
        logger.warning("Neural deepfake inference error: %s", exc)
        return None


def _score_texture_uniformity(
    img_bgr: np.ndarray,
    face_crop: Optional[np.ndarray] = None,
) -> Optional[float]:
    """
    Score based on how UNIFORMLY sharp the face crop is across sub-regions.
    """
    if face_crop is None:
        face_crop = _extract_face_crop(img_bgr)


    gray = cv2.cvtColor(face_crop, cv2.COLOR_BGR2GRAY)  # keep uint8 for Laplacian compat
    fh, fw = gray.shape

    rows, cols = 5, 5
    cell_h, cell_w = fh // rows, fw // cols

    if cell_h < 4 or cell_w < 4:
        return None

    local_vars = []
    for r in range(rows):
        for c in range(cols):
            cell = gray[r * cell_h:(r + 1) * cell_h, c * cell_w:(c + 1) * cell_w]
            lap_var = float(cv2.Laplacian(cell, cv2.CV_64F).var())
            local_vars.append(lap_var + 1e-6)

    arr = np.array(local_vars)
    cv_score = arr.std() / arr.mean()

    # Real photos: CV of local sharpness ~ 0.6-1.8 (high variation)
    # AI images:   CV ~ 0.10-0.50 (uniformly sharp, no natural depth-of-field)
    # Map: CV=0.10 -> 100 (AI), CV=0.70+ -> 0 (real)
    ai_score = max(0.0, min(100.0, (0.70 - cv_score) / (0.70 - 0.10) * 100.0))
    return round(ai_score, 2)


def _score_fft_smoothness(img_bgr: np.ndarray) -> float:
    """
    Measure high-frequency energy deficit via 2-D FFT.

    AI generators minimise perceptual loss -> clean, noiseless images -> less
    energy in high-frequency bins relative to real camera images.

    Returns: 0-100 (higher = more AI-like).
    """
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY).astype(np.float32)
    fft = np.fft.fft2(gray)
    fft_shifted = np.fft.fftshift(fft)
    magnitude = np.abs(fft_shifted)

    h, w = magnitude.shape
    cy, cx = h // 2, w // 2
    Y, X = np.ogrid[:h, :w]
    dist = np.sqrt((X - cx) ** 2 + (Y - cy) ** 2)

    total_energy = magnitude.sum() + 1e-9
    hf_mask = dist > min(h, w) * 0.30
    hf_ratio = magnitude[hf_mask].sum() / total_energy

    # Real DSLR/phone photos: hf_ratio ~ 0.55-0.78 (natural sensor noise)
    # AI images (SD, MJ, StyleGAN): hf_ratio ~ 0.30-0.55
    # Map: 0.30 -> 100 (AI), 0.65+ -> 0 (real)
    ai_score = max(0.0, min(100.0, (0.65 - hf_ratio) / (0.65 - 0.30) * 100.0))
    return round(ai_score, 2)


def _score_skin_uniformity(img_bgr: np.ndarray) -> Optional[float]:
    """
    Measure chrominance uniformity in skin regions using YCbCr.

    Real skin has natural chrominance variation (redness in cheeks/nose,
    discolouration, lighting gradients). AI skin is unnaturally uniform in
    the Cb/Cr channels.

    Returns: 0-100 (higher = more AI-like), or None if no skin pixels found.
    """
    ycbcr = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2YCrCb)
    cr = ycbcr[:, :, 1].astype(np.float32)
    cb = ycbcr[:, :, 2].astype(np.float32)

    skin_mask = (
        (cr >= 133) & (cr <= 173) &
        (cb >= 77)  & (cb <= 127)
    )

    if skin_mask.sum() < 500:
        return None

    cb_std = float(cb[skin_mask].std())
    cr_std = float(cr[skin_mask].std())
    avg_chroma_std = (cb_std + cr_std) / 2.0

    # Real faces: avg_chroma_std ~ 5.0-12.0 (natural chrominance variation)
    # AI faces:   avg_chroma_std ~ 1.5-4.5  (unnaturally uniform)
    # Map: std=1.5 -> 100 (AI), std=7.0+ -> 0 (real)
    ai_score = max(0.0, min(100.0, (7.0 - avg_chroma_std) / (7.0 - 1.5) * 100.0))
    return round(ai_score, 2)


def _score_face_symmetry(img_bgr: np.ndarray) -> Optional[float]:
    """
    Measure horizontal symmetry from InsightFace 5-point landmarks.

    StyleGAN faces are near-perfectly symmetric; real faces are naturally
    asymmetric. Landmark order: 0=left eye, 1=right eye, 2=nose, 3=left mouth,
    4=right mouth.

    Returns: 0-100 (higher = more AI-like), or None if no landmarks found.
    """
    face_app = _get_face_app()
    if face_app is None:
        return None

    try:
        faces = face_app.get(img_bgr)
    except Exception:
        return None

    if not faces or not hasattr(faces[0], "kps") or faces[0].kps is None:
        return None

    kps = faces[0].kps
    if kps.shape[0] < 5:
        return None

    nose_x = kps[2, 0]
    pairs = [
        (abs(kps[0, 0] - nose_x), abs(kps[1, 0] - nose_x)),
        (abs(kps[3, 0] - nose_x), abs(kps[4, 0] - nose_x)),
    ]

    ratios = []
    for left_d, right_d in pairs:
        total = left_d + right_d
        if total > 0:
            ratios.append(abs(left_d - right_d) / total)

    if not ratios:
        return None

    mean_asymmetry = sum(ratios) / len(ratios)

    # Real faces:  mean_asymmetry ~ 0.08-0.25
    # AI faces:    mean_asymmetry ~ 0.00-0.06
    # Map: 0 asym -> 100 (AI), 0.12+ asym -> 0 (real)
    ai_score = max(0.0, min(100.0, (0.12 - mean_asymmetry) / 0.12 * 100.0))
    return round(ai_score, 2)


# -- Ensemble Combiner --------------------------------------------------------

def _compute_ensemble_confidence(signals: dict) -> float:
    """
    Weighted average of available signals, re-normalised for absent signals.
    """
    weights = config.DEEPFAKE_SIGNAL_WEIGHTS

    total_weight = 0.0
    weighted_sum = 0.0

    for signal_name, weight in weights.items():
        if signal_name in signals:
            weighted_sum += signals[signal_name] * weight
            total_weight += weight

    if total_weight == 0:
        return 0.0

    return round(weighted_sum / total_weight, 2)
