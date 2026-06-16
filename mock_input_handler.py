"""
Mock for input_handler.process_document — returns realistic extracted_fields
based on the real pipeline output received from mentor.

Usage:
    In main.py, temporarily replace:
        from input_handler import process_document
    with:
        from mock_input_handler import process_document

    Revert after testing.
"""

MOCK_EXTRACTED_DATA = {
    "tax_invoice": {
        "fields": {
            "invoice_number": "BOSSI2324-01927",
            "invoice_date": "07/06/2023",
            "quantity": "518",
            "unit_price": None,
            "taxable_value": "48183.00",
            "discount": None,
            "gst_rates": "CGST: 9%, SGST: 9%",
            "total_invoice_value": "56023.14",
        },
        "method_used": "gpt-4",
    },
    "e_way_bill": {
        "fields": {},
        "method_used": "rule_based",
    },
    "delivery_challan": {
        "fields": {
            "delivery_challan_number": "BOSDC2324-01312",
            "date_of_issue": "18/05/2023",
            "supplier_details": {
                "name": "Benir E Store Solutions Pvt Ltd",
                "address": "No. 135/1, Maruthi Industrial Estate, Next to Zuri Hotel, Whitefield, Bangalore, Karnataka - 560048",
                "gstin": "29AAECB7398D1ZC",
            },
        },
        "method_used": "gpt-4",
    },
    "purchase_order": {
        "fields": {
            "po_number": "4949080 - OP - 4700400001",
            "po_date": "15/05/2023",
            "buyer_name": "Jones Lang LaSalle Property Consultants (India) Private Limited",
            "buyer_address": "Level 13 & 14, Prestige Khoday Towers, No.5, Raj Bhavan Road, Bangalore KTK 560001",
            "buyer_gstin": "29AAACL2089B1ZO",
            "supplier_name": "Benir E Store Solutions Private Limited",
            "supplier_address": "135/1, Maruti Industrial Estate, Next To Zuri Hotel, Whitefield Road, Bangalore KTK 560048",
            "supplier_gstin": "29AAECB7398D1ZC",
            "delivery_address": "Torrey Pines Building, Embassy Golf Links Business Park, Domlur, Bangalore KTK 560071",
            "billing_address": "Jones Lang LaSalle Property Consultants India Pvt Ltd, 8th floor Block B-3, DLF World Tech park, Gurugram HYN 122001",
            "item_details": [
                {"description": "Tissue Napkin",             "quantity": "200.00", "unit": "1.000", "unit_price": "26.00"},
                {"description": "Nitrile hand gloves Blue",  "quantity": "10.00",  "unit": "2.000", "unit_price": "608.00"},
                {"description": "Ball Pen Cello Fine Gripper","quantity": "100.00", "unit": "3.000", "unit_price": "5.25"},
                {"description": "HRT KC 1005K",              "quantity": "24.00",  "unit": "4.000", "unit_price": "810.00"},
                {"description": "Masking Tape 1\"",          "quantity": "2.00",   "unit": "5.000", "unit_price": "680.00"},
                {"description": "Masking Tape 2\"",          "quantity": "2.00",   "unit": "6.000", "unit_price": "1,039.00"},
                {"description": "Xerox Paper A4 75gms",      "quantity": "30.00",  "unit": "7.000", "unit_price": "260.00"},
                {"description": "Paper plate 8 size",        "quantity": "150.00", "unit": "8.000", "unit_price": "38.00"},
            ],
            "total_order_value": "48,183.00",
            "taxes": "India GST 18%, India GST 12%",
            "delivery_schedule": "16/05/2023",
            "payment_terms": "Net 60 Days",
            "terms_conditions": "Payment is subjected to clause 3.6 under PO terms and conditions",
            "authorized_signatory": None,
        },
        "method_used": "gpt-4",
    },
}


def process_document(file_bytes: bytes, file_name: str, document_type: str) -> dict:
    """
    Mock replacement for input_handler.process_document.
    Returns realistic extracted fields based on real mentor pipeline output.
    Falls back to empty fields for unknown document types.
    """
    print(f"mock_input_handler: process_document called for {document_type} ({file_name})")
    result = MOCK_EXTRACTED_DATA.get(document_type, {"fields": {}, "method_used": "rule_based"})
    return {
        "fields": result["fields"],
        "method_used": result["method_used"],
    }