import base64
import io
from typing import Dict, List

from document_quality_schema import SCHEMA_VERSION, get_universal_schema
from image_utils import (
    detect_crop_cutoff,
    estimate_blur,
    estimate_contrast,
    estimate_skew,
    is_blank_page,
    load_images_from_upload,
    measure_resolution,
    to_grayscale,
)
from openai_utils import is_openai_enabled, query_openai
from PIL import Image
from text_utils import extract_text_from_image, format_confidence, get_clarity_rating, get_content_coverage


print("quality_checks: module loaded")


def clamp(value: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
    return max(minimum, min(maximum, value))


def image_to_base64(image_array) -> str:
    image = Image.fromarray(image_array)
    buffered = io.BytesIO()
    image.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode("utf-8")


def evaluate_single_page(image_array, page_number: int, schema: Dict) -> Dict[str, object]:
    gray = to_grayscale(image_array)

    blur = estimate_blur(gray)
    skew = estimate_skew(gray)
    contrast = estimate_contrast(gray)
    resolution = measure_resolution(image_array)
    cutoff = detect_crop_cutoff(gray)
    text, confidence = extract_text_from_image(image_array)
    blank = is_blank_page(gray, text)
    coverage = get_content_coverage(text, resolution)
    clarity = get_clarity_rating(blur, contrast, skew)

    quality_components = [
        clamp(blur / 160.0),
        clamp(contrast / 80.0),
        clamp(confidence / 100.0),
        clamp(resolution / max(schema["min_resolution"], 1_000_000)),
        0.80 if cutoff else 1.0,
        0.30 if blank else 1.0,
    ]

    quality_score = clamp(sum(quality_components) / len(quality_components))
    if skew > schema["max_skew"]:
        quality_score *= 0.88

    is_compliant = quality_score >= schema["min_quality_score"] and not blank
    reasons = []
    if blank:
        reasons.append("Document appears blank or contains insufficient content")
    if blur < 80:
        reasons.append("Page blurriness is too high for reliable OCR")
    if contrast < schema["min_contrast"]:
        reasons.append("Image contrast is too low")
    if resolution < schema["min_resolution"]:
        reasons.append("Document resolution is too low")
    if skew > schema["max_skew"]:
        reasons.append("Page rotation or skew exceeds allowable limits")
    if coverage == "POOR":
        reasons.append("Extracted text coverage is too low")
    if cutoff:
        reasons.append("Document appears to be cropped or margins are cut off")

    flowback_status = "review" if not is_compliant else None

    quality_checks = {
        "Page Blurriness": "YES" if blur < 80 else "NO",
        "Page Rotation": "YES" if skew > schema["max_skew"] else "NO",
        "OCR Confidence Score": format_confidence(confidence),
        "Resolution/DPI Validation": "NO" if resolution < schema["min_resolution"] else "YES",
        "Crop Cutoff / margins": "YES" if cutoff else "NO",
        "Clarity Rating": clarity,
        "Blank page": "YES" if blank else "NO",
        "Content Coverage": coverage,
    }

    return {
        "page_number": page_number,
        "quality_score": quality_score,
        "is_compliant": is_compliant,
        "reasons": reasons,
        "flowback_status": flowback_status,
        "schema_version": SCHEMA_VERSION,
        "quality_checks": quality_checks,
        "analysis_method": "rule_based",
        "page_bytes_base64": image_to_base64(image_array),
    }


def evaluate_document(file_bytes: bytes, filename: str) -> List[Dict[str, object]]:
    print(f"quality_checks: evaluate_document invoked filename={filename}")
    schema = get_universal_schema()
    images = load_images_from_upload(file_bytes, filename)

    if not images:
        raise ValueError("No images were extracted from the uploaded document")

    results = []
    for page_num, image_array in enumerate(images, start=1):
        page_result = evaluate_single_page(image_array, page_num, schema)
        results.append(page_result)
    print(f"quality_checks: completed rule-based evaluation for {len(results)} pages")
    if not is_openai_enabled():
        try:
            print("quality_checks: invoking OpenAI quality review")
            prompt = (
                "You are evaluating document quality based on page metrics. "
                "For each page, summarize whether the page is compliant, list the main issues, "
                "and provide one concise recommendation. Return only the text.\n\n"
                "Page data:\n"
            )
            for page in results:
                prompt += (
                    f"Page {page['page_number']}: score={page['quality_score']}, "
                    f"compliant={page['is_compliant']}, reasons={page['reasons']}\n"
                )

            llm_review = query_openai(prompt, max_tokens=256)
            for page in results:
                page["analysis_method"] = "gpt-4"
                page["llm_quality_review"] = llm_review
        except Exception as exc:
            print(f"quality_checks: OpenAI quality review failed, falling back rule-based: {exc}")

    return results
