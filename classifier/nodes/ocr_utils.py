import os

from dotenv import load_dotenv
import fitz
import easyocr
import numpy as np

from PIL import Image


load_dotenv()

print("classifier.nodes.ocr_utils: module loaded")

ENABLE_OCR = os.getenv("ENABLE_OCR", "True").lower() == "true"
OCR_LANGUAGE = os.getenv("OCR_LANGUAGE", "en")
OCR_DPI = int(os.getenv("OCR_DPI", "300"))
EASYOCR_GPU = os.getenv("EASYOCR_GPU", "False").lower() == "true"


_easyocr_reader = None


def get_easyocr_reader():
    """
    Creates EasyOCR reader only once.
    This avoids loading the OCR model repeatedly for every page.
    """

    global _easyocr_reader

    if _easyocr_reader is None:
        _easyocr_reader = easyocr.Reader(
            [OCR_LANGUAGE],
            gpu=EASYOCR_GPU
        )

    return _easyocr_reader


def convert_pdf_page_to_image(input_file_path: str, page_index: int) -> np.ndarray:
    """
    Converts a PDF page to an image array for EasyOCR.
    page_index is zero-based.
    """

    pdf_document = fitz.open(input_file_path)

    try:
        page = pdf_document.load_page(page_index)

        zoom = OCR_DPI / 72
        matrix = fitz.Matrix(zoom, zoom)

        pixmap = page.get_pixmap(matrix=matrix, alpha=False)

        image = Image.frombytes(
            "RGB",
            [pixmap.width, pixmap.height],
            pixmap.samples
        )

        return np.array(image)

    finally:
        pdf_document.close()


def easyocr_page_text(input_file_path: str, page_index: int) -> str:
    """
    Runs EasyOCR on one PDF page and returns extracted text.
    """

    print(f"classifier.nodes.ocr_utils: easyocr_page_text invoked page_index={page_index}")

    if not ENABLE_OCR:
        return ""

    image_array = convert_pdf_page_to_image(
        input_file_path=input_file_path,
        page_index=page_index
    )

    reader = get_easyocr_reader()

    results = reader.readtext(
        image_array,
        detail=0,
        paragraph=True
    )

    return "\n".join(results).strip()
