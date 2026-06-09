import os
import re
from typing import Any, Dict, List, Optional, TypedDict

from dotenv import load_dotenv
from pypdf import PdfReader, PdfWriter

from openai_utils import is_azure_openai_enabled, query_openai


load_dotenv()

ENABLE_OCR = os.getenv("ENABLE_OCR", "True").lower() == "true"
OCR_LANGUAGE = os.getenv("OCR_LANGUAGE", "en")
OCR_DPI = int(os.getenv("OCR_DPI", "300"))
OCR_MIN_TEXT_LENGTH = int(os.getenv("OCR_MIN_TEXT_LENGTH", "30"))
EASYOCR_GPU = os.getenv("EASYOCR_GPU", "False").lower() == "true"
OPENAI_FALLBACK_THRESHOLD = float(os.getenv("OPENAI_FALLBACK_THRESHOLD", "0.5"))

_easyocr_reader = None


class DocumentAgentState(TypedDict):
    input_file_path: str
    input_file_name: str
    output_folder: str
    total_pages: int
    extracted_pages: List[Dict[str, Any]]
    classified_pages: List[Dict[str, Any]]
    grouped_documents: List[Dict[str, Any]]
    extracted_documents: List[Dict[str, Any]]
    extracted_data: List[Dict[str, Any]]
    status: str
    message: str
    error: Optional[str]
    response: Optional[Dict[str, Any]]


def validate_input_node(state):
    input_file_path = state.get("input_file_path")

    if not input_file_path:
        return {
            **state,
            "status": "error",
            "error": "Input file path is missing.",
            "message": "Validation failed.",
        }

    if not os.path.exists(input_file_path):
        return {
            **state,
            "status": "error",
            "error": "Input file does not exist.",
            "message": "Validation failed.",
        }

    if not input_file_path.lower().endswith(".pdf"):
        return {
            **state,
            "status": "error",
            "error": "Only PDF files are supported.",
            "message": "Validation failed.",
        }

    return {
        **state,
        "status": "validated",
        "message": "Input file validated successfully.",
    }


def get_easyocr_reader():
    global _easyocr_reader

    if _easyocr_reader is None:
        import easyocr

        _easyocr_reader = easyocr.Reader([OCR_LANGUAGE], gpu=EASYOCR_GPU)

    return _easyocr_reader


def convert_pdf_page_to_image(input_file_path: str, page_index: int):
    import fitz
    import numpy as np
    from PIL import Image

    pdf_document = fitz.open(input_file_path)

    try:
        page = pdf_document.load_page(page_index)
        zoom = OCR_DPI / 72
        matrix = fitz.Matrix(zoom, zoom)
        pixmap = page.get_pixmap(matrix=matrix, alpha=False)

        image = Image.frombytes(
            "RGB",
            [pixmap.width, pixmap.height],
            pixmap.samples,
        )

        return np.array(image)
    finally:
        pdf_document.close()


def easyocr_page_text(input_file_path: str, page_index: int) -> str:
    if not ENABLE_OCR:
        return ""

    image_array = convert_pdf_page_to_image(
        input_file_path=input_file_path,
        page_index=page_index,
    )
    reader = get_easyocr_reader()
    results = reader.readtext(image_array, detail=0, paragraph=True)

    return "\n".join(results).strip()


def extract_text_using_pypdf(input_file_path: str):
    reader = PdfReader(input_file_path)
    extracted_pages = []

    for index, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        extracted_pages.append(
            {
                "page_number": index + 1,
                "text": text.strip(),
                "text_extraction_method": "pypdf",
                "ocr_used": False,
                "ocr_error": None,
            }
        )

    return extracted_pages


def apply_easyocr_fallback(input_file_path: str, extracted_pages):
    updated_pages = []

    for page_info in extracted_pages:
        page_number = page_info["page_number"]
        existing_text = page_info.get("text", "")

        if len(existing_text.strip()) >= OCR_MIN_TEXT_LENGTH or not ENABLE_OCR:
            updated_pages.append(page_info)
            continue

        try:
            ocr_text = easyocr_page_text(
                input_file_path=input_file_path,
                page_index=page_number - 1,
            )

            if len(ocr_text.strip()) > len(existing_text.strip()):
                updated_pages.append(
                    {
                        **page_info,
                        "text": ocr_text,
                        "text_extraction_method": "easyocr",
                        "ocr_used": True,
                        "ocr_error": None,
                    }
                )
            else:
                updated_pages.append(
                    {
                        **page_info,
                        "ocr_used": False,
                        "ocr_error": None,
                    }
                )
        except Exception as exc:
            updated_pages.append(
                {
                    **page_info,
                    "ocr_used": False,
                    "ocr_error": str(exc),
                }
            )

    return updated_pages


def extract_text_node(state):
    try:
        input_file_path = state["input_file_path"]
        reader = PdfReader(input_file_path)
        extracted_pages = extract_text_using_pypdf(input_file_path)
        extracted_pages = apply_easyocr_fallback(
            input_file_path=input_file_path,
            extracted_pages=extracted_pages,
        )

        return {
            **state,
            "total_pages": len(reader.pages),
            "extracted_pages": extracted_pages,
            "status": "text_extracted",
            "message": "Text extracted using pypdf with optional EasyOCR fallback.",
        }
    except Exception as exc:
        return {
            **state,
            "status": "error",
            "error": str(exc),
            "message": "Text extraction failed.",
        }


def _parse_openai_classification(response_text: str) -> str:
    response_text = response_text.lower()
    if "delivery challan" in response_text:
        return "delivery_challan"
    if "purchase order" in response_text or "po" in response_text:
        return "purchase_order"
    if "invoice" in response_text:
        return "tax_invoice"
    if "e way bill" in response_text or "e-way bill" in response_text:
        return "e_way_bill"
    return "Unknown"


def classify_document_page(text: str, is_image_based: bool = False):
    text_lower = (text or "").lower()

    keyword_sets = {
        "purchase_order": [
            "purchase order",
            "po number",
            "po no",
            "purchase order no",
            "po date",
            "buyer",
            "supplier",
            "vendor",
            "payment terms",
            "po originator",
            "ordered",
        ],
        "delivery_challan": [
            "delivery challan",
            "challan",
            "challan no",
            "dc no",
            "dc number",
            "delivery note",
            "delivery note no",
            "delivered",
            "consignee",
            "consignor",
            "goods received",
            "received by",
            "vehicle no",
            "lr no",
            "ship to",
            "delivery address",
        ],
        "tax_invoice": [
            "invoice",
            "tax invoice",
            "gst invoice",
            "invoice no",
            "bill to",
            "billed to",
            "irn",
            "ack no",
            "ack date",
            "taxable value",
            "cgst",
            "sgst",
            "igst",
            "amount payable",
            "total amount",
            "grand total",
        ],
        "e_way_bill": [
            "e way bill",
            "e-way bill",
            "way bill",
            "gstin of supplier",
        ],
    }

    scores = {
        document_type: sum(1 for keyword in keywords if keyword in text_lower)
        for document_type, keywords in keyword_sets.items()
    }

    phrase_boosts = {
        "purchase_order": ["purchase order"],
        "delivery_challan": ["delivery challan"],
        "tax_invoice": ["tax invoice", "invoice no"],
        "e_way_bill": ["e way bill", "e-way bill"],
    }

    for document_type, phrases in phrase_boosts.items():
        if any(phrase in text_lower for phrase in phrases):
            scores[document_type] += 8

    best_type = max(scores, key=scores.get)
    best_score = scores[best_type]

    if best_score == 0:
        result = {
            "document_type": "Unknown",
            "confidence": 0.0,
            "reason": "No matching keywords found.",
            "classification_method": "rule_based",
        }
        confidence = 0.0
    else:
        confidence = min(best_score / 10, 1.0)
        result = {
            "document_type": best_type,
            "confidence": round(confidence, 2),
            "reason": (
                "Scores: "
                f"PO={scores['purchase_order']}, "
                f"Delivery Challan={scores['delivery_challan']}, "
                f"Invoice={scores['tax_invoice']}, "
                f"E-Way Bill={scores['e_way_bill']}."
            ),
            "classification_method": "rule_based",
        }

    should_use_openai = (
        best_score > 0
        and confidence < OPENAI_FALLBACK_THRESHOLD
        and is_azure_openai_enabled()
    )

    if should_use_openai:
        try:
            source = "image-based" if is_image_based else "digital"
            prompt = (
                "Classify the page text as one of: PO, Delivery Challan, "
                "Invoice, E-Way Bill, or Unknown. Provide only the document "
                f"type in a single word or phrase.\n\nSource: {source}\n\n"
                f"Page text:\n{text}\n"
            )
            llm_response = query_openai(prompt, max_tokens=64)
            llm_type = _parse_openai_classification(llm_response)

            if llm_type != "Unknown":
                result["document_type"] = llm_type
                result["confidence"] = 1.0
                result["reason"] = (
                    "OpenAI classification used because rule-based confidence "
                    f"was {confidence:.2f}."
                )
                result["classification_method"] = "openai"
        except Exception as exc:
            result["openai_error"] = str(exc)

    return result


def classify_pages_node(state):
    try:
        classified_pages = []

        for page in state.get("extracted_pages", []):
            result = classify_document_page(
                page.get("text", ""),
                is_image_based=page.get("ocr_used", False),
            )
            classified_pages.append(
                {
                    "page_number": page.get("page_number"),
                    "document_type": result.get("document_type"),
                    "confidence": result.get("confidence"),
                    "reason": result.get("reason"),
                    "classification_method": result.get(
                        "classification_method",
                        "rule_based",
                    ),
                    "text_extraction_method": page.get("text_extraction_method"),
                    "ocr_used": page.get("ocr_used", False),
                    "ocr_error": page.get("ocr_error"),
                    "openai_error": result.get("openai_error"),
                }
            )

        return {
            **state,
            "classified_pages": classified_pages,
            "status": "classified",
            "message": "Pages classified successfully.",
        }
    except Exception as exc:
        return {
            **state,
            "status": "error",
            "error": str(exc),
            "message": "Page classification failed.",
        }


def group_pages_node(state):
    try:
        classified_pages = state["classified_pages"]

        if not classified_pages:
            return {
                **state,
                "grouped_documents": [],
                "status": "grouped",
                "message": "No classified pages found.",
            }

        grouped_documents = []
        current_type = classified_pages[0]["document_type"]
        current_pages = [classified_pages[0]["page_number"]]

        for page in classified_pages[1:]:
            page_type = page["document_type"]
            page_number = page["page_number"]

            if page_type == current_type:
                current_pages.append(page_number)
                continue

            grouped_documents.append(
                {
                    "document_type": current_type,
                    "start_page": current_pages[0],
                    "end_page": current_pages[-1],
                    "pages": current_pages,
                }
            )
            current_type = page_type
            current_pages = [page_number]

        grouped_documents.append(
            {
                "document_type": current_type,
                "start_page": current_pages[0],
                "end_page": current_pages[-1],
                "pages": current_pages,
            }
        )

        return {
            **state,
            "grouped_documents": grouped_documents,
            "status": "grouped",
            "message": "Pages grouped by document type successfully.",
        }
    except Exception as exc:
        return {
            **state,
            "status": "error",
            "error": str(exc),
            "message": "Page grouping failed.",
        }


def get_file_prefix(document_type):
    mapping = {
        "purchase_order": "PO",
        "delivery_challan": "Delivery_Challan",
        "tax_invoice": "Invoice",
        "e_way_bill": "E_Way_Bill",
    }

    return mapping.get(document_type, "Unknown")


def split_documents_node(state):
    try:
        input_file_path = state["input_file_path"]
        output_folder = state["output_folder"]
        os.makedirs(output_folder, exist_ok=True)

        reader = PdfReader(input_file_path)
        extracted_documents = []
        counters = {
            "purchase_order": 1,
            "delivery_challan": 1,
            "tax_invoice": 1,
            "e_way_bill": 1,
        }

        for group in state["grouped_documents"]:
            document_type = group["document_type"]

            if document_type == "Unknown":
                continue

            writer = PdfWriter()
            for page_number in group["pages"]:
                writer.add_page(reader.pages[page_number - 1])

            counter = counters.get(document_type, 1)
            prefix = get_file_prefix(document_type)
            document_name = f"{prefix}_{counter:03d}.pdf"
            document_path = os.path.join(output_folder, document_name)

            with open(document_path, "wb") as output_file:
                writer.write(output_file)

            counters[document_type] = counter + 1
            extracted_documents.append(
                {
                    "document_type": document_type,
                    "document_name": document_name,
                    "document_path": document_path,
                    "start_page": group["start_page"],
                    "end_page": group["end_page"],
                }
            )

        return {
            **state,
            "extracted_documents": extracted_documents,
            "status": "documents_split",
            "message": "Documents split and saved successfully.",
        }
    except Exception as exc:
        return {
            **state,
            "status": "error",
            "error": str(exc),
            "message": "Document splitting failed.",
        }


def clean_amount(value: str) -> str:
    if not value:
        return ""
    return value.replace(",", "").strip()


def normalize_text(text: str) -> str:
    text = text.replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{2,}", "\n", text)
    return text.strip()


def find_first(patterns: List[str], text: str, default: str = "") -> str:
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL)
        if match:
            return re.sub(r"\s+", " ", match.group(1)).strip()
    return default


def extract_all_gst_numbers(text: str) -> List[str]:
    gst_pattern = r"\b[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][0-9A-Z]Z[0-9A-Z]\b"
    return list(dict.fromkeys(re.findall(gst_pattern, text)))


def extract_text_from_pdf(pdf_path: str) -> str:
    reader = PdfReader(pdf_path)
    text_parts = []

    for index, page in enumerate(reader.pages):
        text = page.extract_text() or ""

        if ENABLE_OCR and len(text.strip()) < OCR_MIN_TEXT_LENGTH:
            try:
                ocr_text = easyocr_page_text(input_file_path=pdf_path, page_index=index)
                if len(ocr_text.strip()) > len(text.strip()):
                    text = ocr_text
            except Exception:
                pass

        text_parts.append(text)

    return normalize_text("\n".join(text_parts))


def extract_invoice_header_fields(text: str) -> Dict[str, Any]:
    invoice_number = find_first(
        [
            r"Invoice No\.?\s*Dated\s*([A-Z0-9\-\/]+)\s+[0-9]{1,2}[\/\-][0-9]{1,2}[\/\-][0-9]{2,4}",
            r"Invoice No\.?\s*[:\-]?\s*([A-Z0-9\-\/]+)",
            r"Tax Invoice No\.?\s*[:\-]?\s*([A-Z0-9\-\/]+)",
        ],
        text,
    )
    invoice_date = find_first(
        [
            r"Invoice No\.?\s*Dated\s*[A-Z0-9\-\/]+\s+([0-9]{1,2}[\/\-][0-9]{1,2}[\/\-][0-9]{2,4})",
            r"Invoice Date\s*[:\-]?\s*([0-9]{1,2}[\/\-][0-9]{1,2}[\/\-][0-9]{2,4})",
            r"Dated\s*[:\-]?\s*([0-9]{1,2}[\/\-][0-9]{1,2}[\/\-][0-9]{2,4})",
        ],
        text,
    )
    customer_order_number = find_first(
        [
            r"Customer Order No\s*Customer Order Date\s*([A-Z0-9\s\-\/]+?)\s+[0-9]{1,2}[\/\-][0-9]{1,2}[\/\-][0-9]{2,4}",
            r"Customer Order No\.?\s*[:\-]?\s*([A-Z0-9\s\-\/]+)",
        ],
        text,
    )
    customer_order_date = find_first(
        [
            r"Customer Order No\s*Customer Order Date\s*[A-Z0-9\s\-\/]+?\s+([0-9]{1,2}[\/\-][0-9]{1,2}[\/\-][0-9]{2,4})",
            r"Customer Order Date\s*[:\-]?\s*([0-9]{1,2}[\/\-][0-9]{1,2}[\/\-][0-9]{2,4})",
        ],
        text,
    )
    supplier_name = find_first(
        [
            r"^(Benir E Store Solutions Pvt Ltd)",
            r"Supplier Name\s*[:\-]?\s*([A-Za-z0-9 &.,()\-]+)",
            r"Seller\s*[:\-]?\s*([A-Za-z0-9 &.,()\-]+)",
        ],
        text,
    )
    buyer_name = find_first(
        [
            r"Bill TO ADDRESS:\s*(.*?)\s*Level",
            r"Bill To\s*[:\-]?\s*(.*?)\s*(?:Ship To|SHIP TO|GST)",
            r"Buyer Name\s*[:\-]?\s*([A-Za-z0-9 &.,()\-]+)",
        ],
        text,
    )
    ship_to_name = find_first(
        [
            r"SHIP TO ADDRESS\s*:\s*(.*?)\s*Torrey Pines",
            r"Ship To\s*[:\-]?\s*(.*?)\s*(?:Invoice No|GST|Place of supply)",
        ],
        text,
    )
    irn = find_first([r"IRN\s*:\s*([a-fA-F0-9]{40,100})"], text)
    ack_no = find_first(
        [
            r"ACK No\s*:\s*ACK Date\s*:\s*([0-9]+)",
            r"Ack No\.?\s*[:\-]?\s*([0-9]+)",
        ],
        text,
    )
    ack_date = find_first(
        [
            r"ACK No\s*:\s*ACK Date\s*:\s*[0-9]+\s+([0-9]{1,2}[\/\-][0-9]{1,2}[\/\-][0-9]{2,4})",
            r"Ack Date\s*[:\-]?\s*([0-9]{1,2}[\/\-][0-9]{1,2}[\/\-][0-9]{2,4})",
        ],
        text,
    )
    eway_bill_number = find_first(
        [
            r"EWay Bill No\s*:\s*EWay Bill Date\s*:\s*([0-9 ]+)",
            r"E-Way Bill No\s*:\s*([0-9 ]+)",
            r"Eway Bill No\s*[:\-]?\s*([0-9 ]+)",
        ],
        text,
    ).replace(" ", "")
    eway_bill_date = find_first(
        [
            r"EWay Bill No\s*:\s*EWay Bill Date\s*:\s*[0-9 ]+\s+([0-9]{1,2}[\/\-][0-9]{1,2}[\/\-][0-9]{2,4})",
            r"E-Way Bill Date\s*[:\-]?\s*([0-9]{1,2}[\/\-][0-9]{1,2}[\/\-][0-9]{2,4})",
        ],
        text,
    )
    subtotal = find_first([r"Sub Total\s*:\s*([0-9,]+\.[0-9]{2})"], text)
    cgst = find_first([r"CGST\s*:\s*([0-9,]+\.[0-9]{2})"], text)
    sgst = find_first([r"SGST\s*:\s*([0-9,]+\.[0-9]{2})"], text)
    igst = find_first([r"IGST\s*:\s*([0-9,]+\.[0-9]{2})"], text)
    total_amount = find_first(
        [
            r"TOTAL\s*:\s*([0-9,]+\.[0-9]{2})",
            r"Grand Total\s*[:\-]?\s*([0-9,]+\.[0-9]{2})",
            r"Invoice Total\s*[:\-]?\s*([0-9,]+\.[0-9]{2})",
            r"Amount Payable\s*[:\-]?\s*([0-9,]+\.[0-9]{2})",
        ],
        text,
    )
    amount_in_words = find_first(
        [
            r"Rs\. In Words\s*:\s*(.*?)\s*HSN/",
            r"Amount In Words\s*[:\-]?\s*(.*?)(?:HSN|Tax|Total)",
        ],
        text,
    )

    return {
        "invoice_number": invoice_number,
        "invoice_date": invoice_date,
        "customer_order_number": customer_order_number,
        "customer_order_date": customer_order_date,
        "supplier_name": supplier_name,
        "buyer_name": buyer_name,
        "ship_to_name": ship_to_name,
        "irn": irn,
        "ack_no": ack_no,
        "ack_date": ack_date,
        "eway_bill_number": eway_bill_number,
        "eway_bill_date": eway_bill_date,
        "gst_numbers": extract_all_gst_numbers(text),
        "subtotal": clean_amount(subtotal),
        "cgst": clean_amount(cgst),
        "sgst": clean_amount(sgst),
        "igst": clean_amount(igst),
        "total_amount": clean_amount(total_amount),
        "amount_in_words": amount_in_words,
    }


def extract_invoice_line_items(text: str) -> List[Dict[str, Any]]:
    items = []
    pattern = re.compile(
        r"(?P<line_no>\d+)\s+"
        r"(?P<dc_no>[A-Z]{3,}[A-Z0-9\-\/]+)\s+"
        r"(?P<item_code>[A-Z0-9\-]+)\s+"
        r"(?P<description>.*?)\s+"
        r"(?P<uom>PAC|NOS|PCS|KG|KGS|EA|UNIT|UNITS|MTR|LTR|BOX|BOXES)\s+"
        r"(?P<hsn>[0-9]{6,8})\s+"
        r"(?P<quantity>[0-9]+(?:\.[0-9]+)?)\s+"
        r"(?P<rate>[0-9,]+\.[0-9]{2})\s+"
        r"(?P<discount_percent>[0-9]+\.[0-9]{2})\s+"
        r"(?P<gst_percent>[0-9]+\.[0-9]{2})\s+"
        r"(?P<value>[0-9,]+\.[0-9]{2})",
        flags=re.IGNORECASE | re.DOTALL,
    )

    for match in pattern.finditer(text):
        item = match.groupdict()
        items.append(
            {
                "line_no": item.get("line_no", ""),
                "description": re.sub(
                    r"\s+",
                    " ",
                    item.get("description", ""),
                ).strip(),
                "quantity": item.get("quantity", ""),
                "uom": item.get("uom", ""),
                "unit_price": "",
                "rate": clean_amount(item.get("rate", "")),
                "gst_percent": item.get("gst_percent", ""),
                "value": clean_amount(item.get("value", "")),
                "total_net_value": "",
                "item_code": item.get("item_code", ""),
                "dc_no": item.get("dc_no", ""),
                "hsn": item.get("hsn", ""),
                "discount_percent": item.get("discount_percent", ""),
            }
        )

    return items


def extract_po_header_fields(text: str) -> Dict[str, Any]:
    po_number = find_first(
        [
            r"Purchase Order\s*([0-9]+)",
            r"PO Number\s*[:\-]?\s*([0-9]+)",
            r"PO No\.?\s*[:\-]?\s*([0-9]+)",
        ],
        text,
    )
    op_reference = find_first(
        [
            r"OP\s*([0-9]+)",
            r"Purchase Order\s*[0-9]+\s*-\s*-\s*OP\s*([0-9]+)",
        ],
        text,
    )
    po_date = find_first(
        [
            r"Ordered\s*[0-9]+\s*([0-9]{1,2}[\/\-][0-9]{1,2}[\/\-][0-9]{2,4})",
            r"PO Date\s*[:\-]?\s*([0-9]{1,2}[\/\-][0-9]{1,2}[\/\-][0-9]{2,4})",
        ],
        text,
    )
    buyer_name = find_first(
        [
            r"Bill to Name and Address\s*(Jones Lang LaSalle.*?)\s*Contract No",
            r"(Jones Lang LaSalle Property Consultants \(India\) Private Limited)",
        ],
        text,
    )
    vendor_name = find_first(
        [
            r"Bill From\s*(Benir E Store Solutions Private Limited)",
            r"(Benir E Store Solutions Private Limited)",
            r"Vendor Name\s*[:\-]?\s*([A-Za-z0-9 &.,()\-]+)",
        ],
        text,
    )
    ship_to_name = find_first(
        [
            r"Ship To\s*Bill From\s*(.*?)\s*Benir E Store Solutions",
            r"(Yahoo Software Development India Pvt Ltd)",
        ],
        text,
    )
    payment_terms = find_first(
        [
            r"Net\s*([0-9]+\s*Days)\s*Payment Terms",
            r"Payment Terms\s*[:\-]?\s*([A-Za-z0-9 ]+)",
        ],
        text,
    )
    currency = find_first([r"Currency Code\s*([A-Z]{3})"], text)
    total_net_value = find_first(
        [
            r"Total net value excl tax\s*([0-9,]+\.[0-9]{2})\s*INR",
            r"Total Net Value\s*[:\-]?\s*([0-9,]+\.[0-9]{2})",
        ],
        text,
    )

    return {
        "po_number": po_number,
        "op_reference": op_reference,
        "po_date": po_date,
        "buyer_name": buyer_name,
        "vendor_name": vendor_name,
        "ship_to_name": ship_to_name,
        "payment_terms": payment_terms,
        "currency": currency,
        "total_net_value_excl_tax": clean_amount(total_net_value),
        "gst_numbers": extract_all_gst_numbers(text),
    }


def extract_po_line_items(text: str) -> List[Dict[str, Any]]:
    items = []
    pattern = re.compile(
        r"(?P<description>[A-Za-z][A-Za-z0-9\s\/\-\(\)\"\.]+?)\s+"
        r"(?P<unit_price>[0-9,]+\.[0-9]{2})\s+"
        r"(?P<quantity>[0-9]+\.[0-9]{2})\s+"
        r"(?P<delivery_date>[0-9]{1,2}[\/\-][0-9]{1,2}[\/\-][0-9]{2,4})\s+"
        r"(?P<total_net_value>[0-9,]+\.[0-9]{2})\s+"
        r"(?P<line_no>[0-9]+\.[0-9]{3})",
        flags=re.IGNORECASE,
    )
    blocked_text = [
        "Item Quantity Description",
        "Total net value",
        "Important PAYMENT",
        "Purchase Order",
        "JONES LANG LASALLE",
    ]

    for match in pattern.finditer(text):
        item = match.groupdict()
        description = re.sub(r"\s+", " ", item.get("description", "")).strip()

        if any(blocked.lower() in description.lower() for blocked in blocked_text):
            continue

        items.append(
            {
                "line_no": item.get("line_no", ""),
                "description": description,
                "quantity": item.get("quantity", ""),
                "uom": "",
                "unit_price": clean_amount(item.get("unit_price", "")),
                "rate": "",
                "gst_percent": "",
                "value": "",
                "total_net_value": clean_amount(item.get("total_net_value", "")),
                "delivery_date": item.get("delivery_date", ""),
            }
        )

    return items


def extract_delivery_challan_header_fields(text: str) -> Dict[str, Any]:
    challan_number = find_first(
        [
            r"Delivery Challan No\.?\s*[:\-]?\s*([A-Z0-9\-\/]+)",
            r"Challan No\.?\s*[:\-]?\s*([A-Z0-9\-\/]+)",
            r"DC No\.?\s*[:\-]?\s*([A-Z0-9\-\/]+)",
            r"\b(BOSDC[0-9A-Z\-\/]+)\b",
        ],
        text,
    )
    challan_date = find_first(
        [
            r"Challan Date\s*[:\-]?\s*([0-9]{1,2}[\/\-][0-9]{1,2}[\/\-][0-9]{2,4})",
            r"Delivery Date\s*[:\-]?\s*([0-9]{1,2}[\/\-][0-9]{1,2}[\/\-][0-9]{2,4})",
            r"Date\s*[:\-]?\s*([0-9]{1,2}[\/\-][0-9]{1,2}[\/\-][0-9]{2,4})",
        ],
        text,
    )
    supplier_name = find_first(
        [
            r"(Benir E Store Solutions Pvt Ltd)",
            r"(Benir E Store Solutions Private Limited)",
            r"Supplier Name\s*[:\-]?\s*([A-Za-z0-9 &.,()\-]+)",
        ],
        text,
    )
    buyer_name = find_first(
        [
            r"(Jones Lang LaSalle Property Consultants.*?)\s",
            r"Buyer Name\s*[:\-]?\s*([A-Za-z0-9 &.,()\-]+)",
        ],
        text,
    )
    ship_to_name = find_first(
        [
            r"(YAHOO SOFTWARE DEVELOPMENT INDIA PVT LTD)",
            r"(Yahoo Software Development India Pvt Ltd)",
            r"Ship To\s*[:\-]?\s*([A-Za-z0-9 &.,()\-]+)",
        ],
        text,
    )
    vehicle_number = find_first([r"Vehicle No\.?\s*[:\-]?\s*([A-Z0-9\- ]+)"], text)
    eway_bill_number = find_first(
        [
            r"EWay Bill No\.?\s*[:\-]?\s*([0-9 ]+)",
            r"E-Way Bill No\.?\s*[:\-]?\s*([0-9 ]+)",
        ],
        text,
    ).replace(" ", "")

    return {
        "challan_number": challan_number,
        "challan_date": challan_date,
        "supplier_name": supplier_name,
        "buyer_name": buyer_name,
        "ship_to_name": ship_to_name,
        "vehicle_number": vehicle_number,
        "eway_bill_number": eway_bill_number,
        "gst_numbers": extract_all_gst_numbers(text),
    }


def extract_delivery_challan_line_items(text: str) -> List[Dict[str, Any]]:
    items = extract_invoice_line_items(text)

    if items:
        return items

    simple_pattern = re.compile(
        r"(?P<line_no>\d+)\s+"
        r"(?P<description>[A-Za-z0-9 ,./()\-]+?)\s+"
        r"(?P<quantity>[0-9]+(?:\.[0-9]+)?)\s*"
        r"(?P<uom>PAC|NOS|PCS|KG|KGS|EA|UNIT|UNITS|MTR|LTR|BOX|BOXES)?",
        flags=re.IGNORECASE,
    )

    for match in simple_pattern.finditer(text):
        item = match.groupdict()
        description = re.sub(r"\s+", " ", item.get("description", "")).strip()

        if len(description) < 3:
            continue

        items.append(
            {
                "line_no": item.get("line_no", ""),
                "description": description,
                "quantity": item.get("quantity", ""),
                "uom": item.get("uom") or "",
                "unit_price": "",
                "rate": "",
                "gst_percent": "",
                "value": "",
                "total_net_value": "",
            }
        )

    return items


def validate_extracted_fields(
    document_type: str,
    header_fields: Dict[str, Any],
    line_items: List[Dict[str, Any]],
) -> Dict[str, Any]:
    mandatory_by_type = {
        "tax_invoice": [
            "invoice_number",
            "invoice_date",
            "supplier_name",
            "buyer_name",
            "total_amount",
        ],
        "PO": [
            "po_number",
            "po_date",
            "vendor_name",
            "buyer_name",
            "total_net_value_excl_tax",
        ],
        "Delivery Challan": [
            "challan_number",
            "challan_date",
            "supplier_name",
            "buyer_name",
        ],
    }
    mandatory_fields = mandatory_by_type.get(document_type, [])
    missing_fields = []

    for field in mandatory_fields:
        value = header_fields.get(field)
        if value is None or value == "" or value == []:
            missing_fields.append(field)

    if not line_items:
        missing_fields.append("line_items")

    return {
        "mandatory_fields": mandatory_fields + ["line_items"],
        "missing_fields": missing_fields,
        "is_complete": len(missing_fields) == 0,
    }


def extract_data_by_document_type(document_type: str, text: str) -> Dict[str, Any]:
    if document_type == "tax_invoice":
        header_fields = extract_invoice_header_fields(text)
        line_items = extract_invoice_line_items(text)
    elif document_type == "purchase_order":
        header_fields = extract_po_header_fields(text)
        line_items = extract_po_line_items(text)
    elif document_type == "delivery_challan":
        header_fields = extract_delivery_challan_header_fields(text)
        line_items = extract_delivery_challan_line_items(text)
    else:
        header_fields = {}
        line_items = []

    validation = validate_extracted_fields(
        document_type=document_type,
        header_fields=header_fields,
        line_items=line_items,
    )

    return {
        "header_fields": header_fields,
        "line_items": line_items,
        "validation": validation,
    }


def data_extraction_node(state):
    try:
        extracted_data = []

        for document in state.get("extracted_documents", []):
            document_type = document.get("document_type")
            document_name = document.get("document_name")
            document_path = document.get("document_path")

            if document_type == "Unknown":
                continue

            if not document_path or not os.path.exists(document_path):
                extracted_data.append(
                    {
                        "document_type": document_type,
                        "document_name": document_name,
                        "document_path": document_path,
                        "start_page": document.get("start_page"),
                        "end_page": document.get("end_page"),
                        "status": "error",
                        "raw_text_available": False,
                        "header_fields": {},
                        "line_items": [],
                        "validation": {
                            "mandatory_fields": [],
                            "missing_fields": ["document_path"],
                            "is_complete": False,
                        },
                        "error": "Sliced document path not found.",
                    }
                )
                continue

            text = extract_text_from_pdf(document_path)
            extraction_result = extract_data_by_document_type(
                document_type=document_type,
                text=text,
            )

            if not text.strip():
                extraction_status = "requires_ocr"
            elif extraction_result["validation"]["is_complete"]:
                extraction_status = "success"
            else:
                extraction_status = "success_with_missing_fields"

            extracted_data.append(
                {
                    "document_type": document_type,
                    "document_name": document_name,
                    "document_path": document_path,
                    "start_page": document.get("start_page"),
                    "end_page": document.get("end_page"),
                    "status": extraction_status,
                    "raw_text_available": bool(text.strip()),
                    "header_fields": extraction_result["header_fields"],
                    "line_items": extraction_result["line_items"],
                    "validation": extraction_result["validation"],
                }
            )

        return {
            **state,
            "extracted_data": extracted_data,
            "status": "data_extracted",
            "message": "Necessary fields extracted and populated into schema.",
        }
    except Exception as exc:
        return {
            **state,
            "status": "error",
            "message": "Data Extraction Agent failed.",
            "error": str(exc),
        }


def generate_response_node(state):
    expected_documents = {"Invoice", "PO", "Delivery Challan"}
    found_documents = {
        document.get("document_type")
        for document in state.get("extracted_documents", [])
        if document.get("document_type") != "Unknown"
    }
    missing_documents = list(expected_documents - found_documents)
    incomplete_documents = []

    for item in state.get("extracted_data", []):
        validation = item.get("validation", {})
        if not validation.get("is_complete", False):
            incomplete_documents.append(
                {
                    "document_type": item.get("document_type"),
                    "document_name": item.get("document_name"),
                    "missing_fields": validation.get("missing_fields", []),
                }
            )

    if state.get("status") == "error":
        final_status = "error"
    elif missing_documents:
        final_status = "partial_success"
    elif incomplete_documents:
        final_status = "success_with_missing_fields"
    else:
        final_status = "success"

    response = {
        "status": final_status,
        "message": "Document classification, splitting, and field extraction completed.",
        "input_file": state.get("input_file_name"),
        "processed_folder": state.get("output_folder"),
        "total_pages": state.get("total_pages", 0),
        "classified_pages": [
            {
                "page_number": page.get("page_number"),
                "document_type": page.get("document_type"),
                "confidence": page.get("confidence", 0.0),
                "reason": page.get("reason", ""),
            }
            for page in state.get("classified_pages", [])
        ],
        "extracted_documents": [
            {
                "document_type": document.get("document_type"),
                "document_name": document.get("document_name"),
                "document_path": document.get("document_path"),
                "start_page": document.get("start_page"),
                "end_page": document.get("end_page"),
            }
            for document in state.get("extracted_documents", [])
            if document.get("document_type") != "Unknown"
        ],
        "extracted_data": [
            {
                "document_type": item.get("document_type"),
                "document_name": item.get("document_name"),
                "document_path": item.get("document_path"),
                "start_page": item.get("start_page"),
                "end_page": item.get("end_page"),
                "status": item.get("status"),
                "raw_text_available": item.get("raw_text_available", False),
                "header_fields": item.get("header_fields", {}),
                "line_items": item.get("line_items", []),
                "validation": item.get(
                    "validation",
                    {
                        "mandatory_fields": [],
                        "missing_fields": [],
                        "is_complete": False,
                    },
                ),
            }
            for item in state.get("extracted_data", [])
        ],
        "missing_documents": missing_documents,
        "incomplete_documents": incomplete_documents,
    }

    return {
        **state,
        "status": final_status,
        "message": "Document classification, splitting, and field extraction completed.",
        "response": response,
    }


def error_node(state):
    response = {
        "status": "error",
        "message": state.get("message", "Workflow failed."),
        "input_file": state.get("input_file_name"),
        "processed_folder": state.get("output_folder"),
        "total_pages": state.get("total_pages", 0),
        "classified_pages": state.get("classified_pages", []),
        "extracted_documents": state.get("extracted_documents", []),
        "extracted_data": state.get("extracted_data", []),
        "missing_documents": [],
        "incomplete_documents": [],
        "error": state.get("error", "Unknown error occurred."),
    }

    return {
        **state,
        "status": "error",
        "response": response,
    }


def _route_after(status_to_node: str):
    def route(state):
        if state.get("status") == "error":
            return "error_node"
        return status_to_node

    return route


def build_document_classification_graph():
    from langgraph.graph import END, START, StateGraph

    workflow = StateGraph(DocumentAgentState)

    workflow.add_node("validate_input_node", validate_input_node)
    workflow.add_node("extract_text_node", extract_text_node)
    workflow.add_node("classify_pages_node", classify_pages_node)
    workflow.add_node("group_pages_node", group_pages_node)
    workflow.add_node("split_documents_node", split_documents_node)
    workflow.add_node("data_extraction_node", data_extraction_node)
    workflow.add_node("generate_response_node", generate_response_node)
    workflow.add_node("error_node", error_node)

    workflow.add_edge(START, "validate_input_node")
    workflow.add_conditional_edges(
        "validate_input_node",
        _route_after("extract_text_node"),
        {"extract_text_node": "extract_text_node", "error_node": "error_node"},
    )
    workflow.add_conditional_edges(
        "extract_text_node",
        _route_after("classify_pages_node"),
        {"classify_pages_node": "classify_pages_node", "error_node": "error_node"},
    )
    workflow.add_conditional_edges(
        "classify_pages_node",
        _route_after("group_pages_node"),
        {"group_pages_node": "group_pages_node", "error_node": "error_node"},
    )
    workflow.add_conditional_edges(
        "group_pages_node",
        _route_after("split_documents_node"),
        {"split_documents_node": "split_documents_node", "error_node": "error_node"},
    )
    workflow.add_conditional_edges(
        "split_documents_node",
        _route_after("data_extraction_node"),
        {"data_extraction_node": "data_extraction_node", "error_node": "error_node"},
    )
    workflow.add_conditional_edges(
        "data_extraction_node",
        _route_after("generate_response_node"),
        {"generate_response_node": "generate_response_node", "error_node": "error_node"},
    )

    workflow.add_edge("generate_response_node", END)
    workflow.add_edge("error_node", END)

    return workflow.compile()
