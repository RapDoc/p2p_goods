import io
import re
from typing import List, Dict, Any

from PIL import Image
import pytesseract
import pdfplumber


# For Windows (Double-check your exact installation folder)
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

def pdf_to_pages_bytes(pdf_bytes: bytes) -> List[bytes]:
    pages = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            pil = page.to_image(resolution=300).original
            buf = io.BytesIO()
            pil.save(buf, format="PNG")
            pages.append(buf.getvalue())
    return pages


def ocr_image_bytes(image_bytes: bytes) -> str:
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    text = pytesseract.image_to_string(img)
    return text


def extract_text_from_file(file_bytes: bytes, filename: str) -> Dict[str, Any]:
    """Return a dict with `pages` (list of page texts) and `tables` (list of table data per page).

    Uses pdfplumber for PDFs and pytesseract for images.
    """
    pages_text: List[str] = []
    tables: List[List[Dict[str, Any]]] = []

    if filename.lower().endswith(".pdf"):
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            for page in pdf.pages:
                # extract text first
                txt = page.extract_text() or ""
                # fallback to image OCR if text is empty
                if not txt.strip():
                    im = page.to_image(resolution=300).original
                    buf = io.BytesIO()
                    im.save(buf, format="PNG")
                    txt = ocr_image_bytes(buf.getvalue())

                pages_text.append(txt)

                # try to extract tables
                page_tables = []
                try:
                    raw_tables = page.extract_tables()
                    for raw in raw_tables:
                        # convert list of rows to list of dicts if header present
                        if raw and len(raw) > 1:
                            header = raw[0]
                            rows = [dict(zip(header, r)) for r in raw[1:]]
                            page_tables.append(rows)
                        else:
                            page_tables.append({"rows": raw})
                except Exception:
                    page_tables = []

                tables.append(page_tables)
    else:
        # assume image
        txt = ocr_image_bytes(file_bytes)
        pages_text.append(txt)
        tables.append([])

    return {"pages": pages_text, "tables": tables}


def find_field_regex(text: str, patterns: List[str]) -> str | None:
    for p in patterns:
        m = re.search(p, text, flags=re.IGNORECASE | re.MULTILINE)
        if m:
            grp = m.groupdict()
            if grp:
                # return first named group value
                return next(iter(grp.values()))
            return m.group(1) if m.groups() else m.group(0)
    return None
