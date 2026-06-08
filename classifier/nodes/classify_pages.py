from openai_utils import is_openai_enabled, query_openai

print("classifier.nodes.classify_pages: module loaded")

# Confidence threshold for using OpenAI on digital pages (default 0.5 = 50%)
OPENAI_FALLBACK_THRESHOLD = 0.5


def _parse_openai_classification(response_text: str) -> str:
    response_text = response_text.lower()
    if "delivery challan" in response_text:
        return "Delivery Challan"
    if "purchase order" in response_text or "po" in response_text:
        return "PO"
    if "invoice" in response_text:
        return "Invoice"
    if "e way bill" in response_text or "e-way bill" in response_text:
        return "E-Way Bill"
    return "Unknown"


def classify_document_page(text: str, is_image_based: bool = False):
    """
    Classifies page text into:
    PO, Delivery Challan, Invoice, E-Way Bill, or Unknown.
    Works with both pypdf text and EasyOCR text.
    
    Args:
        text: Page text to classify
        is_image_based: True if page text was extracted via OCR (image-based page)
                       False if text was directly extracted from digital PDF
    
    Conditional OpenAI Usage:
        - Image-based pages (OCR used): Use OpenAI if enabled and rule-based confidence < 0.5
        - Digital pages: Use OpenAI if enabled and rule-based confidence < 0.5
    """

    text_lower = (text or "").lower()

    po_keywords = [
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
        "ordered"
    ]
    e_way_bill_keywords = [
        "e way bill",
        "e-way bill",
        "way bill",
        "gstin of supplier"
    ]

    dc_keywords = [
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
        "delivery address"
    ]

    invoice_keywords = [
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
        "grand total"
    ]

    po_score = sum(1 for keyword in po_keywords if keyword in text_lower)
    dc_score = sum(1 for keyword in dc_keywords if keyword in text_lower)
    invoice_score = sum(1 for keyword in invoice_keywords if keyword in text_lower)
    waybill_score = sum(1 for keyword in e_way_bill_keywords if keyword in text_lower)

    # Strong phrase boosts
    if "delivery challan" in text_lower:
        dc_score += 8

    if "purchase order" in text_lower:
        po_score += 8

    if "tax invoice" in text_lower or "invoice no" in text_lower:
        invoice_score += 8

    if "e way bill" in text_lower or "e-way bill" in text_lower:
        waybill_score += 8

    scores = {
        "PO": po_score,
        "Delivery Challan": dc_score,
        "Invoice": invoice_score,
        "E-Way Bill": waybill_score
    }

    best_type = max(scores, key=scores.get)
    best_score = scores[best_type]

    if best_score == 0:
        result = {
            "document_type": "Unknown",
            "confidence": 0.0,
            "reason": "No matching keywords found.",
            "classification_method": "rule_based"
        }
    else:
        confidence = min(best_score / 10, 1.0)
        result = {
            "document_type": best_type,
            "confidence": round(confidence, 2),
            "reason": f"Scores: PO={po_score}, Delivery Challan={dc_score}, Invoice={invoice_score}, E-Way Bill={waybill_score}.",
            "classification_method": "rule_based"
        }

    if is_openai_enabled():
        # Decision logic for when to use OpenAI:
        # 1. Image-based pages (OCR used): Use if rule-based confidence < threshold
        # 2. Digital pages: Use if rule-based confidence < threshold
        should_use_openai = best_score > 0 and confidence < OPENAI_FALLBACK_THRESHOLD
        
        if should_use_openai:
            try:
                print(f"classifier.nodes.classify_pages: Using OpenAI for {'image-based' if is_image_based else 'digital'} page (confidence={confidence:.2f})")
                prompt = (
                    "Classify the page text as one of: PO, Delivery Challan, Invoice, E-Way Bill, or Unknown. "
                    "Provide only the document type in a single word or phrase.\n\n"
                    f"Page text:\n{text}\n"
                )
                llm_response = query_openai(prompt, max_tokens=64)
                llm_type = _parse_openai_classification(llm_response)
                if llm_type != "Unknown":
                    result["document_type"] = llm_type
                    result["confidence"] = 1.0
                    result["reason"] = f"GPT-4 classification (used due to low rule-based confidence: {confidence:.2f})"
                    result["classification_method"] = "gpt-4"
                    print(f"classifier.nodes.classify_pages: OpenAI classified as {llm_type}")
            except Exception as exc:
                print(f"classifier.nodes.classify_pages: OpenAI classification fallback failed: {exc}")
        else:
            if best_score > 0:
                print(f"classifier.nodes.classify_pages: Skipping OpenAI (confidence={confidence:.2f} >= threshold={OPENAI_FALLBACK_THRESHOLD})")

    return result


def classify_pages_node(state):
    """
    LangGraph node:
    Classifies every extracted page into document type.
    
    For each page:
    1. Uses rule-based keyword matching
    2. If OpenAI enabled and rule-based confidence < threshold:
       - Image-based pages (OCR used): Call OpenAI
       - Digital pages: Call OpenAI
    """

    print("classifier.nodes.classify_pages: classify_pages_node invoked")

    try:
        classified_pages = []

        for page in state.get("extracted_pages", []):
            page_text = page.get("text", "")
            is_image_based = page.get("ocr_used", False)
            
            result = classify_document_page(page_text, is_image_based=is_image_based)

            classified_pages.append({
                "page_number": page.get("page_number"),
                "document_type": result.get("document_type"),
                "confidence": result.get("confidence"),
                "reason": result.get("reason"),
                "classification_method": result.get("classification_method", "rule_based"),

                # OCR/debug metadata
                "text_extraction_method": page.get("text_extraction_method"),
                "ocr_used": page.get("ocr_used", False),
                "ocr_error": page.get("ocr_error")
            })

        return {
            **state,
            "classified_pages": classified_pages,
            "status": "classified",
            "message": "Pages classified successfully."
        }

    except Exception as e:
        return {
            **state,
            "status": "error",
            "error": str(e),
            "message": "Page classification failed."
        }
