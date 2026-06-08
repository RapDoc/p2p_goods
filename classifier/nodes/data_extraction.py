import os
import re
from typing import Dict, List, Any

from dotenv import load_dotenv
from pypdf import PdfReader

# Optional OCR fallback for image-only sliced documents
try:
    from .ocr_utils import easyocr_page_text
except Exception:
    easyocr_page_text = None


load_dotenv()

print("classifier.nodes.data_extraction: module loaded")

ENABLE_OCR = os.getenv("ENABLE_OCR", "True").lower() == "true"
OCR_MIN_TEXT_LENGTH = int(os.getenv("OCR_MIN_TEXT_LENGTH", "30"))


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
    """
    Extracts text from sliced PDF.
    Uses pypdf first.
    If page has weak/blank text, EasyOCR fallback is used.
    """

    reader = PdfReader(pdf_path)
    text_parts = []

    for index, page in enumerate(reader.pages):
        text = page.extract_text() or ""

        if (
            ENABLE_OCR
            and easyocr_page_text is not None
            and len(text.strip()) < OCR_MIN_TEXT_LENGTH
        ):
            try:
                ocr_text = easyocr_page_text(
                    input_file_path=pdf_path,
                    page_index=index
                )

                if len(ocr_text.strip()) > len(text.strip()):
                    text = ocr_text

            except Exception:
                pass

        text_parts.append(text)

    return normalize_text("\n".join(text_parts))


# -------------------------------------------------------------------
# INVOICE EXTRACTION
# -------------------------------------------------------------------

def extract_invoice_header_fields(text: str) -> Dict[str, Any]:
    invoice_number = find_first([
        r"Invoice No\.?\s*Dated\s*([A-Z0-9\-\/]+)\s+[0-9]{1,2}[\/\-][0-9]{1,2}[\/\-][0-9]{2,4}",
        r"Invoice No\.?\s*[:\-]?\s*([A-Z0-9\-\/]+)",
        r"Tax Invoice No\.?\s*[:\-]?\s*([A-Z0-9\-\/]+)"
    ], text)

    invoice_date = find_first([
        r"Invoice No\.?\s*Dated\s*[A-Z0-9\-\/]+\s+([0-9]{1,2}[\/\-][0-9]{1,2}[\/\-][0-9]{2,4})",
        r"Invoice Date\s*[:\-]?\s*([0-9]{1,2}[\/\-][0-9]{1,2}[\/\-][0-9]{2,4})",
        r"Dated\s*[:\-]?\s*([0-9]{1,2}[\/\-][0-9]{1,2}[\/\-][0-9]{2,4})"
    ], text)

    customer_order_number = find_first([
        r"Customer Order No\s*Customer Order Date\s*([A-Z0-9\s\-\/]+?)\s+[0-9]{1,2}[\/\-][0-9]{1,2}[\/\-][0-9]{2,4}",
        r"Customer Order No\.?\s*[:\-]?\s*([A-Z0-9\s\-\/]+)"
    ], text)

    customer_order_date = find_first([
        r"Customer Order No\s*Customer Order Date\s*[A-Z0-9\s\-\/]+?\s+([0-9]{1,2}[\/\-][0-9]{1,2}[\/\-][0-9]{2,4})",
        r"Customer Order Date\s*[:\-]?\s*([0-9]{1,2}[\/\-][0-9]{1,2}[\/\-][0-9]{2,4})"
    ], text)

    supplier_name = find_first([
        r"^(Benir E Store Solutions Pvt Ltd)",
        r"Supplier Name\s*[:\-]?\s*([A-Za-z0-9 &.,()\-]+)",
        r"Seller\s*[:\-]?\s*([A-Za-z0-9 &.,()\-]+)"
    ], text)

    buyer_name = find_first([
        r"Bill TO ADDRESS:\s*(.*?)\s*Level",
        r"Bill To\s*[:\-]?\s*(.*?)\s*(?:Ship To|SHIP TO|GST)",
        r"Buyer Name\s*[:\-]?\s*([A-Za-z0-9 &.,()\-]+)"
    ], text)

    ship_to_name = find_first([
        r"SHIP TO ADDRESS\s*:\s*(.*?)\s*Torrey Pines",
        r"Ship To\s*[:\-]?\s*(.*?)\s*(?:Invoice No|GST|Place of supply)"
    ], text)

    irn = find_first([
        r"IRN\s*:\s*([a-fA-F0-9]{40,100})"
    ], text)

    ack_no = find_first([
        r"ACK No\s*:\s*ACK Date\s*:\s*([0-9]+)",
        r"Ack No\.?\s*[:\-]?\s*([0-9]+)"
    ], text)

    ack_date = find_first([
        r"ACK No\s*:\s*ACK Date\s*:\s*[0-9]+\s+([0-9]{1,2}[\/\-][0-9]{1,2}[\/\-][0-9]{2,4})",
        r"Ack Date\s*[:\-]?\s*([0-9]{1,2}[\/\-][0-9]{1,2}[\/\-][0-9]{2,4})"
    ], text)

    eway_bill_number = find_first([
        r"EWay Bill No\s*:\s*EWay Bill Date\s*:\s*([0-9 ]+)",
        r"E-Way Bill No\s*:\s*([0-9 ]+)",
        r"Eway Bill No\s*[:\-]?\s*([0-9 ]+)"
    ], text).replace(" ", "")

    eway_bill_date = find_first([
        r"EWay Bill No\s*:\s*EWay Bill Date\s*:\s*[0-9 ]+\s+([0-9]{1,2}[\/\-][0-9]{1,2}[\/\-][0-9]{2,4})",
        r"E-Way Bill Date\s*[:\-]?\s*([0-9]{1,2}[\/\-][0-9]{1,2}[\/\-][0-9]{2,4})"
    ], text)

    subtotal = find_first([
        r"Sub Total\s*:\s*([0-9,]+\.[0-9]{2})"
    ], text)

    cgst = find_first([
        r"CGST\s*:\s*([0-9,]+\.[0-9]{2})"
    ], text)

    sgst = find_first([
        r"SGST\s*:\s*([0-9,]+\.[0-9]{2})"
    ], text)

    igst = find_first([
        r"IGST\s*:\s*([0-9,]+\.[0-9]{2})"
    ], text)

    total_amount = find_first([
        r"TOTAL\s*:\s*([0-9,]+\.[0-9]{2})",
        r"Grand Total\s*[:\-]?\s*([0-9,]+\.[0-9]{2})",
        r"Invoice Total\s*[:\-]?\s*([0-9,]+\.[0-9]{2})",
        r"Amount Payable\s*[:\-]?\s*([0-9,]+\.[0-9]{2})"
    ], text)

    amount_in_words = find_first([
        r"Rs\. In Words\s*:\s*(.*?)\s*HSN/",
        r"Amount In Words\s*[:\-]?\s*(.*?)(?:HSN|Tax|Total)"
    ], text)

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
        "amount_in_words": amount_in_words
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
        flags=re.IGNORECASE | re.DOTALL
    )

    for match in pattern.finditer(text):
        item = match.groupdict()

        items.append({
            "line_no": item.get("line_no", ""),
            "description": re.sub(r"\s+", " ", item.get("description", "")).strip(),
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
            "discount_percent": item.get("discount_percent", "")
        })

    return items


# -------------------------------------------------------------------
# PO EXTRACTION
# -------------------------------------------------------------------

def extract_po_header_fields(text: str) -> Dict[str, Any]:
    po_number = find_first([
        r"Purchase Order\s*([0-9]+)",
        r"PO Number\s*[:\-]?\s*([0-9]+)",
        r"PO No\.?\s*[:\-]?\s*([0-9]+)"
    ], text)

    op_reference = find_first([
        r"OP\s*([0-9]+)",
        r"Purchase Order\s*[0-9]+\s*-\s*-\s*OP\s*([0-9]+)"
    ], text)

    po_date = find_first([
        r"Ordered\s*[0-9]+\s*([0-9]{1,2}[\/\-][0-9]{1,2}[\/\-][0-9]{2,4})",
        r"PO Date\s*[:\-]?\s*([0-9]{1,2}[\/\-][0-9]{1,2}[\/\-][0-9]{2,4})"
    ], text)

    buyer_name = find_first([
        r"Bill to Name and Address\s*(Jones Lang LaSalle.*?)\s*Contract No",
        r"(Jones Lang LaSalle Property Consultants \(India\) Private Limited)"
    ], text)

    vendor_name = find_first([
        r"Bill From\s*(Benir E Store Solutions Private Limited)",
        r"(Benir E Store Solutions Private Limited)",
        r"Vendor Name\s*[:\-]?\s*([A-Za-z0-9 &.,()\-]+)"
    ], text)

    ship_to_name = find_first([
        r"Ship To\s*Bill From\s*(.*?)\s*Benir E Store Solutions",
        r"(Yahoo Software Development India Pvt Ltd)"
    ], text)

    payment_terms = find_first([
        r"Net\s*([0-9]+\s*Days)\s*Payment Terms",
        r"Payment Terms\s*[:\-]?\s*([A-Za-z0-9 ]+)"
    ], text)

    currency = find_first([
        r"Currency Code\s*([A-Z]{3})"
    ], text)

    total_net_value = find_first([
        r"Total net value excl tax\s*([0-9,]+\.[0-9]{2})\s*INR",
        r"Total Net Value\s*[:\-]?\s*([0-9,]+\.[0-9]{2})"
    ], text)

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
        "gst_numbers": extract_all_gst_numbers(text)
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
        flags=re.IGNORECASE
    )

    blocked_text = [
        "Item Quantity Description",
        "Total net value",
        "Important PAYMENT",
        "Purchase Order",
        "JONES LANG LASALLE"
    ]

    for match in pattern.finditer(text):
        item = match.groupdict()
        description = re.sub(r"\s+", " ", item.get("description", "")).strip()

        if any(blocked.lower() in description.lower() for blocked in blocked_text):
            continue

        items.append({
            "line_no": item.get("line_no", ""),
            "description": description,
            "quantity": item.get("quantity", ""),
            "uom": "",
            "unit_price": clean_amount(item.get("unit_price", "")),
            "rate": "",
            "gst_percent": "",
            "value": "",
            "total_net_value": clean_amount(item.get("total_net_value", "")),
            "delivery_date": item.get("delivery_date", "")
        })

    return items


# -------------------------------------------------------------------
# DELIVERY CHALLAN EXTRACTION
# -------------------------------------------------------------------

def extract_delivery_challan_header_fields(text: str) -> Dict[str, Any]:
    challan_number = find_first([
        r"Delivery Challan No\.?\s*[:\-]?\s*([A-Z0-9\-\/]+)",
        r"Challan No\.?\s*[:\-]?\s*([A-Z0-9\-\/]+)",
        r"DC No\.?\s*[:\-]?\s*([A-Z0-9\-\/]+)",
        r"\b(BOSDC[0-9A-Z\-\/]+)\b"
    ], text)

    challan_date = find_first([
        r"Challan Date\s*[:\-]?\s*([0-9]{1,2}[\/\-][0-9]{1,2}[\/\-][0-9]{2,4})",
        r"Delivery Date\s*[:\-]?\s*([0-9]{1,2}[\/\-][0-9]{1,2}[\/\-][0-9]{2,4})",
        r"Date\s*[:\-]?\s*([0-9]{1,2}[\/\-][0-9]{1,2}[\/\-][0-9]{2,4})"
    ], text)

    supplier_name = find_first([
        r"(Benir E Store Solutions Pvt Ltd)",
        r"(Benir E Store Solutions Private Limited)",
        r"Supplier Name\s*[:\-]?\s*([A-Za-z0-9 &.,()\-]+)"
    ], text)

    buyer_name = find_first([
        r"(Jones Lang LaSalle Property Consultants.*?)\s",
        r"Buyer Name\s*[:\-]?\s*([A-Za-z0-9 &.,()\-]+)"
    ], text)

    ship_to_name = find_first([
        r"(YAHOO SOFTWARE DEVELOPMENT INDIA PVT LTD)",
        r"(Yahoo Software Development India Pvt Ltd)",
        r"Ship To\s*[:\-]?\s*([A-Za-z0-9 &.,()\-]+)"
    ], text)

    vehicle_number = find_first([
        r"Vehicle No\.?\s*[:\-]?\s*([A-Z0-9\- ]+)"
    ], text)

    eway_bill_number = find_first([
        r"EWay Bill No\.?\s*[:\-]?\s*([0-9 ]+)",
        r"E-Way Bill No\.?\s*[:\-]?\s*([0-9 ]+)"
    ], text).replace(" ", "")

    return {
        "challan_number": challan_number,
        "challan_date": challan_date,
        "supplier_name": supplier_name,
        "buyer_name": buyer_name,
        "ship_to_name": ship_to_name,
        "vehicle_number": vehicle_number,
        "eway_bill_number": eway_bill_number,
        "gst_numbers": extract_all_gst_numbers(text)
    }


def extract_delivery_challan_line_items(text: str) -> List[Dict[str, Any]]:
    """
    Reuses invoice-style item format when DC rows are similar.
    Also supports simpler item lines from OCR.
    """

    items = extract_invoice_line_items(text)

    if items:
        return items

    simple_pattern = re.compile(
        r"(?P<line_no>\d+)\s+"
        r"(?P<description>[A-Za-z0-9 ,./()\-]+?)\s+"
        r"(?P<quantity>[0-9]+(?:\.[0-9]+)?)\s*"
        r"(?P<uom>PAC|NOS|PCS|KG|KGS|EA|UNIT|UNITS|MTR|LTR|BOX|BOXES)?",
        flags=re.IGNORECASE
    )

    for match in simple_pattern.finditer(text):
        item = match.groupdict()

        description = re.sub(r"\s+", " ", item.get("description", "")).strip()

        if len(description) < 3:
            continue

        items.append({
            "line_no": item.get("line_no", ""),
            "description": description,
            "quantity": item.get("quantity", ""),
            "uom": item.get("uom") or "",
            "unit_price": "",
            "rate": "",
            "gst_percent": "",
            "value": "",
            "total_net_value": ""
        })

    return items


# -------------------------------------------------------------------
# VALIDATION + ROUTER
# -------------------------------------------------------------------

def validate_extracted_fields(
    document_type: str,
    header_fields: Dict[str, Any],
    line_items: List[Dict[str, Any]]
) -> Dict[str, Any]:

    mandatory_by_type = {
        "Invoice": [
            "invoice_number",
            "invoice_date",
            "supplier_name",
            "buyer_name",
            "total_amount"
        ],
        "PO": [
            "po_number",
            "po_date",
            "vendor_name",
            "buyer_name",
            "total_net_value_excl_tax"
        ],
        "Delivery Challan": [
            "challan_number",
            "challan_date",
            "supplier_name",
            "buyer_name"
        ]
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
        "is_complete": len(missing_fields) == 0
    }


def extract_data_by_document_type(document_type: str, text: str) -> Dict[str, Any]:
    if document_type == "Invoice":
        header_fields = extract_invoice_header_fields(text)
        line_items = extract_invoice_line_items(text)

    elif document_type == "PO":
        header_fields = extract_po_header_fields(text)
        line_items = extract_po_line_items(text)

    elif document_type == "Delivery Challan":
        header_fields = extract_delivery_challan_header_fields(text)
        line_items = extract_delivery_challan_line_items(text)

    else:
        header_fields = {}
        line_items = []

    validation = validate_extracted_fields(
        document_type=document_type,
        header_fields=header_fields,
        line_items=line_items
    )

    return {
        "header_fields": header_fields,
        "line_items": line_items,
        "validation": validation
    }


def data_extraction_node(state):
    """
    LangGraph Data Extraction Agent node.
    Reads sliced PDFs from Processed_docs and populates extracted_data.
    """

    print("classifier.nodes.data_extraction: data_extraction_node invoked")
    try:
        extracted_data = []

        for document in state.get("extracted_documents", []):
            document_type = document.get("document_type")
            document_name = document.get("document_name")
            document_path = document.get("document_path")

            if document_type == "Unknown":
                continue

            if not document_path or not os.path.exists(document_path):
                extracted_data.append({
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
                        "is_complete": False
                    },
                    "error": "Sliced document path not found."
                })
                continue

            text = extract_text_from_pdf(document_path)
            raw_text_available = bool(text.strip())

            extraction_result = extract_data_by_document_type(
                document_type=document_type,
                text=text
            )

            if not raw_text_available:
                extraction_status = "requires_ocr"
            elif extraction_result["validation"]["is_complete"]:
                extraction_status = "success"
            else:
                extraction_status = "success_with_missing_fields"

            extracted_data.append({
                "document_type": document_type,
                "document_name": document_name,
                "document_path": document_path,
                "start_page": document.get("start_page"),
                "end_page": document.get("end_page"),
                "status": extraction_status,
                "raw_text_available": raw_text_available,
                "header_fields": extraction_result["header_fields"],
                "line_items": extraction_result["line_items"],
                "validation": extraction_result["validation"]
            })

        return {
            **state,
            "extracted_data": extracted_data,
            "status": "data_extracted",
            "message": "Necessary fields extracted and populated into schema."
        }

    except Exception as e:
        return {
            **state,
            "status": "error",
            "message": "Data Extraction Agent failed.",
            "error": str(e)
        }
