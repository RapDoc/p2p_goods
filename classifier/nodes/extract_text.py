import os

from dotenv import load_dotenv
from pypdf import PdfReader

from .ocr_utils import easyocr_page_text

print("classifier.nodes.extract_text: module loaded")


load_dotenv()


ENABLE_OCR = os.getenv("ENABLE_OCR", "True").lower() == "true"
OCR_MIN_TEXT_LENGTH = int(os.getenv("OCR_MIN_TEXT_LENGTH", "30"))


def extract_text_using_pypdf(input_file_path: str):
    """
    Extracts text page-wise using pypdf.
    Works for normal text-based PDF pages.
    """

    reader = PdfReader(input_file_path)
    extracted_pages = []

    for index, page in enumerate(reader.pages):
        text = page.extract_text() or ""

        extracted_pages.append({
            "page_number": index + 1,
            "text": text.strip(),
            "text_extraction_method": "pypdf",
            "ocr_used": False,
            "ocr_error": None
        })

    return extracted_pages


def apply_easyocr_fallback(input_file_path: str, extracted_pages):
    """
    Runs EasyOCR only on pages where pypdf text is blank or too short.
    This helps classify image-only Delivery Challan pages.
    """

    updated_pages = []

    for page_info in extracted_pages:
        page_number = page_info["page_number"]
        existing_text = page_info.get("text", "")

        if len(existing_text.strip()) >= OCR_MIN_TEXT_LENGTH:
            updated_pages.append(page_info)
            continue

        if not ENABLE_OCR:
            updated_pages.append(page_info)
            continue

        try:
            ocr_text = easyocr_page_text(
                input_file_path=input_file_path,
                page_index=page_number - 1
            )

            if len(ocr_text.strip()) > len(existing_text.strip()):
                updated_pages.append({
                    **page_info,
                    "text": ocr_text,
                    "text_extraction_method": "easyocr",
                    "ocr_used": True,
                    "ocr_error": None
                })
            else:
                updated_pages.append({
                    **page_info,
                    "ocr_used": False,
                    "ocr_error": None
                })

        except Exception as e:
            updated_pages.append({
                **page_info,
                "ocr_used": False,
                "ocr_error": str(e)
            })

    return updated_pages


def extract_text_node(state):
    """
    LangGraph node:
    Extracts page-wise text from input PDF.
    Uses pypdf first, then EasyOCR fallback for image-only pages.
    """

    print("classifier.nodes.extract_text: extract_text_node invoked")

    try:
        input_file_path = state["input_file_path"]

        reader = PdfReader(input_file_path)
        total_pages = len(reader.pages)

        extracted_pages = extract_text_using_pypdf(input_file_path)

        extracted_pages = apply_easyocr_fallback(
            input_file_path=input_file_path,
            extracted_pages=extracted_pages
        )

        return {
            **state,
            "total_pages": total_pages,
            "extracted_pages": extracted_pages,
            "status": "text_extracted",
            "message": "Text extracted using pypdf with EasyOCR fallback."
        }

    except Exception as e:
        return {
            **state,
            "status": "error",
            "error": str(e),
            "message": "Text extraction failed."
        }
