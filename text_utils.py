from __future__ import annotations

import os

import numpy as np
from dotenv import load_dotenv


load_dotenv()

ENABLE_OCR = os.getenv("ENABLE_OCR", "True").lower() == "true"
OCR_LANGUAGE = os.getenv("OCR_LANGUAGE", "en")
EASYOCR_GPU = os.getenv("EASYOCR_GPU", "False").lower() == "true"
READER = None


def get_easyocr_reader():
    global READER

    if READER is None:
        import easyocr

        READER = easyocr.Reader([OCR_LANGUAGE], gpu=EASYOCR_GPU)

    return READER


def extract_text_from_image(image: np.ndarray) -> tuple[str, float]:
    if not ENABLE_OCR:
        return "", 0.0

    try:
        results = get_easyocr_reader().readtext(image, detail=1)
    except RuntimeError as exc:
        raise ValueError("OCR engine failed") from exc

    texts = []
    confidences = []
    for item in results:
        if len(item) >= 3:
            _, text, confidence = item
            text = text.strip()
            if text:
                texts.append(text)
                confidences.append(float(confidence))

    if not texts:
        return "", 0.0

    average_confidence = float(np.mean(confidences)) * 100.0
    return " ".join(texts), average_confidence


def get_content_coverage(text: str, area: int) -> str:
    density = len(text) / (area / 1000.0 + 1)
    if density < 1.8:
        return "POOR"
    if density < 4.5:
        return "GOOD"
    return "EXCELLENT"


def get_clarity_rating(blur: float, contrast: float, skew: float) -> str:
    if blur < 80 or contrast < 25 or skew > 7:
        return "POOR"
    if blur < 150 or contrast < 40 or skew > 4:
        return "GOOD"
    return "EXCELLENT"


def format_confidence(confidence: float) -> str:
    return f"{min(max(confidence, 0.0), 100.0):.1f}%"
