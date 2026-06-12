"""
3-Way Matching Agent for P2P AP Automation Pipeline.

Source of truth: Purchase Order (PO)
Matches: Invoice and Delivery Challan against PO

Match fields:
  - Vendor GSTIN (PO supplier_gstin == Challan supplier_details.gstin)
  - Total value (PO total_order_value == Invoice total_invoice_value), tolerance ±1 rupee / ±0.01%
  - Line items (PO item_details vs Invoice quantity+unit_price), same tolerance
  - Canonical vendor name (PO supplier == Challan supplier)

Output:
  - result: "match" | "mismatch"
  - matches: list of fields that passed
  - mismatches: list of dicts with field, document_type, page_number, po_value, actual_value
"""

from typing import Optional


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

NUMERIC_TOLERANCE_ABS = 1.0       # ±1 rupee absolute
NUMERIC_TOLERANCE_REL = 0.0001    # ±0.01% relative


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def numeric_match(a: Optional[float], b: Optional[float]) -> bool:
    """Returns True if both values are within tolerance, or both are None."""
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    abs_diff = abs(a - b)
    rel_diff = abs_diff / max(abs(a), abs(b), 1e-9)
    return abs_diff <= NUMERIC_TOLERANCE_ABS or rel_diff <= NUMERIC_TOLERANCE_REL


def get_page_number(normalized_data: list[dict], document_type: str) -> Optional[int]:
    """Pull page number from match_key for the given document type."""
    for doc in normalized_data:
        if doc.get("document_type") == document_type:
            # match_key carries document_date but not page_number directly
            # page_number comes from classified_pages passed alongside normalized_data
            return doc.get("page_number")
    return None


def find_doc(normalized_data: list[dict], document_type: str) -> Optional[dict]:
    """Return the first normalized doc of the given type."""
    for doc in normalized_data:
        if doc.get("document_type") == document_type:
            return doc
    return None


def get_page_for_doc(classified_pages: list[dict], document_type: str) -> Optional[int]:
    """
    Return the first page number associated with a document type
    from the classifier output.
    """
    for page in classified_pages:
        if page.get("document_type") == document_type:
            return page.get("page_number")
    return None


def make_mismatch(
    field: str,
    document_type: str,
    page_number: Optional[int],
    po_value,
    actual_value,
    note: str = "",
) -> dict:
    return {
        "field": field,
        "document_type": document_type,
        "page_number": page_number,
        "po_value": po_value,
        "actual_value": actual_value,
        "note": note,
    }


# ---------------------------------------------------------------------------
# Match checks
# ---------------------------------------------------------------------------

def check_vendor_gstin(
    po_fields: dict,
    challan_fields: dict,
    challan_page: Optional[int],
    mismatches: list,
    matches: list,
):
    po_gstin = po_fields.get("supplier_gstin")
    challan_supplier = challan_fields.get("supplier_details") or {}
    challan_gstin = challan_supplier.get("gstin")

    if not po_gstin or not challan_gstin:
        matches.append("vendor_gstin: skipped (one or both missing)")
        return

    if po_gstin.upper().strip() == challan_gstin.upper().strip():
        matches.append(f"vendor_gstin: {po_gstin} ✓")
    else:
        mismatches.append(make_mismatch(
            field="vendor_gstin",
            document_type="delivery_challan",
            page_number=challan_page,
            po_value=po_gstin,
            actual_value=challan_gstin,
            note="Supplier GSTIN on challan does not match PO",
        ))


def check_vendor_name(
    po_fields: dict,
    challan_fields: dict,
    challan_page: Optional[int],
    mismatches: list,
    matches: list,
):
    po_vendor = po_fields.get("canonical_vendor_name")
    challan_vendor = (challan_fields.get("supplier_details") or {}).get("name")
    challan_canonical = challan_fields.get("canonical_vendor_name")

    # Use canonical if available, else raw
    cv = challan_canonical or challan_vendor

    if not po_vendor or not cv:
        matches.append("vendor_name: skipped (one or both missing)")
        return

    if po_vendor.lower().strip() == cv.lower().strip():
        matches.append(f"vendor_name: {po_vendor} ✓")
    else:
        mismatches.append(make_mismatch(
            field="vendor_name",
            document_type="delivery_challan",
            page_number=challan_page,
            po_value=po_vendor,
            actual_value=cv,
            note="Supplier name on challan does not match PO after normalization",
        ))


def check_total_value(
    po_fields: dict,
    invoice_fields: dict,
    invoice_page: Optional[int],
    mismatches: list,
    matches: list,
):
    po_total = po_fields.get("total_order_value")
    inv_total = invoice_fields.get("total_invoice_value")

    if po_total is None or inv_total is None:
        matches.append("total_value: skipped (one or both missing)")
        return

    if numeric_match(po_total, inv_total):
        matches.append(f"total_value: PO={po_total} Invoice={inv_total} ✓")
    else:
        mismatches.append(make_mismatch(
            field="total_value",
            document_type="tax_invoice",
            page_number=invoice_page,
            po_value=po_total,
            actual_value=inv_total,
            note=f"Invoice total {inv_total} differs from PO total {po_total} (diff={abs(inv_total - po_total):.2f})",
        ))


def check_line_items(
    po_fields: dict,
    invoice_fields: dict,
    invoice_page: Optional[int],
    mismatches: list,
    matches: list,
):
    """
    Match PO line items against invoice.
    Matches on description (case-insensitive), then compares quantity and unit_price.
    Invoice may not have line items (extractor limitation) — skips gracefully.
    """
    po_items = po_fields.get("item_details") or []
    inv_quantity = invoice_fields.get("quantity")     # invoice has aggregate quantity
    inv_unit_price = invoice_fields.get("unit_price")

    if not po_items:
        matches.append("line_items: skipped (no PO items)")
        return

    # If invoice has individual line items, match per-item
    inv_items = invoice_fields.get("item_details") or []

    if inv_items:
        for po_item in po_items:
            po_desc = (po_item.get("description") or "").lower().strip()
            po_qty = po_item.get("quantity")
            po_price = po_item.get("unit_price")

            # Find matching invoice item by description
            matched_inv = next(
                (i for i in inv_items if (i.get("description") or "").lower().strip() == po_desc),
                None,
            )

            if not matched_inv:
                mismatches.append(make_mismatch(
                    field=f"line_item[{po_desc}]",
                    document_type="tax_invoice",
                    page_number=invoice_page,
                    po_value={"description": po_desc, "quantity": po_qty, "unit_price": po_price},
                    actual_value=None,
                    note=f"Item '{po_desc}' from PO not found in invoice",
                ))
                continue

            inv_qty = matched_inv.get("quantity")
            inv_price = matched_inv.get("unit_price")

            if not numeric_match(po_qty, inv_qty):
                mismatches.append(make_mismatch(
                    field=f"line_item[{po_desc}].quantity",
                    document_type="tax_invoice",
                    page_number=invoice_page,
                    po_value=po_qty,
                    actual_value=inv_qty,
                    note=f"Quantity mismatch for '{po_desc}'",
                ))
            else:
                matches.append(f"line_item[{po_desc}].quantity: {po_qty} ✓")

            if not numeric_match(po_price, inv_price):
                mismatches.append(make_mismatch(
                    field=f"line_item[{po_desc}].unit_price",
                    document_type="tax_invoice",
                    page_number=invoice_page,
                    po_value=po_price,
                    actual_value=inv_price,
                    note=f"Unit price mismatch for '{po_desc}'",
                ))
            else:
                matches.append(f"line_item[{po_desc}].unit_price: {po_price} ✓")

    else:
        # Invoice only has aggregate quantity — match total quantity against sum of PO items
        po_total_qty = sum(
            i.get("quantity") or 0
            for i in po_items
            if i.get("quantity") is not None
        )
        if inv_quantity is not None and po_total_qty:
            if numeric_match(po_total_qty, inv_quantity):
                matches.append(f"total_quantity: PO={po_total_qty} Invoice={inv_quantity} ✓")
            else:
                mismatches.append(make_mismatch(
                    field="total_quantity",
                    document_type="tax_invoice",
                    page_number=invoice_page,
                    po_value=po_total_qty,
                    actual_value=inv_quantity,
                    note=f"Aggregate quantity mismatch (diff={abs(inv_quantity - po_total_qty):.2f})",
                ))
        else:
            matches.append("line_items: skipped (invoice has no line items or quantity)")


# ---------------------------------------------------------------------------
# LLM mismatch interpretation
# ---------------------------------------------------------------------------

def llm_interpret_mismatches(
    mismatches: list[dict],
    po_fields: dict,
    invoice_fields: dict,
    challan_fields: dict,
) -> dict:
    """
    Called only when rule-based matching finds mismatches.
    Asks the LLM to interpret why the mismatches occurred and recommend an action.

    Returns:
        {
            "interpretation": str,       -- plain-English explanation of each mismatch
            "recommended_action": str,   -- "auto_approve" | "flag_for_review" | "reject"
            "reasoning": str             -- one sentence justifying the recommendation
        }
    """
    from openai_utils import query_openai
    import re, json as _json

    mismatch_lines = "\n".join(
        f"  - Field: {m['field']} | Document: {m['document_type']} | Page: {m['page_number']} "
        f"| PO value: {m['po_value']} | Actual value: {m['actual_value']} | Note: {m['note']}"
        for m in mismatches
    )

    prompt = f"""You are an expert accounts payable auditor reviewing a 3-way match result for Indian business documents.

The Purchase Order (PO) is the source of truth.

PO summary:
  - Supplier GSTIN: {po_fields.get('supplier_gstin')}
  - Total order value (pre-tax): {po_fields.get('total_order_value')}
  - GST rates on PO: {po_fields.get('taxes')}
  - Number of line items: {len(po_fields.get('item_details') or [])}

Invoice summary:
  - Total invoice value (post-tax): {invoice_fields.get('total_invoice_value')}
  - Taxable value: {invoice_fields.get('taxable_value')}
  - GST rates on invoice: {invoice_fields.get('gst_rates')}

Delivery Challan summary:
  - Supplier GSTIN: {(challan_fields.get('supplier_details') or {}).get('gstin')}

Mismatches found by rule-based matching:
{mismatch_lines}

For each mismatch, explain what likely caused it (e.g. GST addition, rounding, data entry error, genuine discrepancy).
Then recommend one of:
  - "auto_approve": mismatch is explainable and expected (e.g. GST added to PO pre-tax value)
  - "flag_for_review": mismatch is suspicious and needs human review
  - "reject": clear error or fraud indicator

Respond ONLY with a JSON object (no markdown, no explanation outside JSON):
{{
  "interpretation": "plain-English explanation of each mismatch",
  "recommended_action": "auto_approve | flag_for_review | reject",
  "reasoning": "one sentence justifying the recommendation"
}}"""

    try:
        raw = query_openai(prompt, max_tokens=512, temperature=0.0)
        raw = re.sub(r"```json|```", "", raw).strip()
        return _json.loads(raw)
    except Exception as e:
        print(f"matching_agent: llm_interpret_mismatches failed: {e}")
        return {
            "interpretation": "LLM interpretation unavailable",
            "recommended_action": "flag_for_review",
            "reasoning": f"Defaulting to flag_for_review due to LLM error: {e}",
        }