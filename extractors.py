from typing import Dict, List, Tuple
from ocr_utils import find_field_regex


MANDATORY_FIELDS = {
    "delivery_challan": [
        "delivery_challan_number",
        "date_of_issue",
        "supplier_details",
        "name",
        "address",
        "gstin",
    ],
    "purchase_order": [
        "po_number",
        "po_date",
        "buyer_name",
        "buyer_address",
        "buyer_gstin",
        "supplier_name",
        "supplier_address",
        "supplier_gstin",
        "delivery_address",
        "billing_address",
        "item_details",
        "description",
        "quantity",
        "unit",
        "unit_price",
        "total_order_value",
        "taxes",
        "delivery_schedule",
        "payment_terms",
        "terms_conditions",
        "authorized_signatory",
    ],
    "tax_invoice": [
        "invoice_number",
        "invoice_date",
        "quantity",
        "unit_price",
        "taxable_value",
        "discount",
        "gst_rates",
        "total_invoice_value",
    ],
}


def extract_delivery_challan(pages: List[str], tables: List[List[dict]]) -> Tuple[Dict[str, str], List[str]]:
    text = "\n".join(pages)
    fields = {}
    missing = []

    patterns = {
        "delivery_challan_number": [r"Delivery\s*Challan\s*No\.?[:\s]*([A-Za-z0-9-\/]+)", r"DC\s*No\.?[:\s]*([A-Za-z0-9-\/]+)"],
        "date_of_issue": [r"Date\s*[:\s]*(\d{1,2}[\-/]\d{1,2}[\-/]\d{2,4})", r"Date\s*of\s*Issue[:\s]*(\d{1,2}[\-/]\d{1,2}[\-/]\d{2,4})"],
        "gstin": [r"GSTIN[:\s]*([0-9A-Z]{15})"],
        "name": [r"Name[:\s]*(.+)", r"To[:\s]*(.+)"],
    }

    for k in MANDATORY_FIELDS["delivery_challan"]:
        if k in patterns:
            val = find_field_regex(text, patterns[k])
            if val:
                fields[k] = val.strip()
            else:
                missing.append(k)
        elif k == "supplier_details":
            # heuristic: take block around 'Supplier' keyword
            import re

            m = re.search(r"Supplier[:\s]*([\s\S]{0,200})\n", text, flags=re.IGNORECASE)
            if m:
                fields[k] = m.group(1).strip()
            else:
                missing.append(k)
        elif k == "address":
            # look for address block after name
            import re

            m = re.search(r"(Address[:\s]*[\s\S]{5,200})\n", text, flags=re.IGNORECASE)
            if m:
                fields[k] = m.group(1).strip()
            else:
                missing.append(k)
        else:
            missing.append(k)

    return fields, missing


def extract_purchase_order(pages: List[str], tables: List[List[dict]]) -> Tuple[Dict[str, str], List[str]]:
    text = "\n".join(pages)
    fields = {}
    missing = []

    patterns = {
        "po_number": [r"Purchase\s*Order\s*No\.?[:\s]*([A-Za-z0-9-\/]+)", r"PO\s*No\.?[:\s]*([A-Za-z0-9-\/]+)"] ,
        "po_date": [r"PO\s*Date[:\s]*(\d{1,2}[\-/]\d{1,2}[\-/]\d{2,4})", r"Date\s*[:\s]*(\d{1,2}[\-/]\d{1,2}[\-/]\d{2,4})"],
        "buyer_gstin": [r"Buyer\s*GSTIN[:\s]*([0-9A-Z]{15})", r"GSTIN[:\s]*([0-9A-Z]{15})"],
        "supplier_gstin": [r"Supplier\s*GSTIN[:\s]*([0-9A-Z]{15})"],
        "total_order_value": [r"Total\s*Order\s*Value[:\s]*([0-9,\.]+)", r"Total[:\s]*INR\s*([0-9,\.]+)"]
    }

    for k in MANDATORY_FIELDS["purchase_order"]:
        if k in patterns:
            val = find_field_regex(text, patterns[k])
            if val:
                fields[k] = val.strip()
            else:
                missing.append(k)
        elif k in ["item_details", "description", "quantity", "unit", "unit_price", "taxes"]:
            # try from tables
            found = False
            for page_tables in tables:
                for t in page_tables:
                    # t expected as list of dict rows
                    if isinstance(t, list) and t:
                        fields[k] = t[0].get(k, str(t[0]))
                        found = True
                        break
                if found:
                    break
            if not found:
                missing.append(k)
        else:
            # simple heuristics for addresses and names
            import re

            if k.endswith("name"):
                m = re.search(r"(Buyer|Supplier)[:\s]*(.+)", text, flags=re.IGNORECASE)
                if m:
                    fields[k] = m.group(2).strip()
                else:
                    missing.append(k)
            elif k.endswith("address"):
                m = re.search(r"(Delivery|Billing|Address)[:\s]*([\s\S]{5,200})\n", text, flags=re.IGNORECASE)
                if m:
                    fields[k] = m.group(2).strip()
                else:
                    missing.append(k)
            else:
                missing.append(k)

    return fields, missing


def extract_tax_invoice(pages: List[str], tables: List[List[dict]]) -> Tuple[Dict[str, str], List[str]]:
    text = "\n".join(pages)
    fields = {}
    missing = []

    patterns = {
        "invoice_number": [r"Invoice\s*No\.?[:\s]*([A-Za-z0-9-\/]+)", r"Inv\.?\s*No\.?[:\s]*([A-Za-z0-9-\/]+)"],
        "invoice_date": [r"Invoice\s*Date[:\s]*(\d{1,2}[\-/]\d{1,2}[\-/]\d{2,4})"],
        "total_invoice_value": [r"Total\s*Amount[:\s]*INR?\s*([0-9,\.]+)", r"Grand\s*Total[:\s]*INR?\s*([0-9,\.]+)"]
    }

    for k in MANDATORY_FIELDS["tax_invoice"]:
        if k in patterns:
            val = find_field_regex(text, patterns[k])
            if val:
                fields[k] = val.strip()
            else:
                missing.append(k)
        elif k in ["quantity", "unit_price", "taxable_value", "discount", "gst_rates"]:
            # try tables
            found = False
            for page_tables in tables:
                for t in page_tables:
                    if isinstance(t, list) and t:
                        # take aggregate if present
                        row = t[0]
                        if k in row:
                            fields[k] = row.get(k)
                            found = True
                            break
                if found:
                    break
            if not found:
                missing.append(k)
        else:
            missing.append(k)

    return fields, missing


def extract_fields_for_document(document_type: str, pages: List[str], tables: List[List[dict]]):
    dt = document_type.lower().replace(" ", "_")
    if dt in ("delivery_challan", "delivery-challan", "delivery challan"):
        return extract_delivery_challan(pages, tables)
    if dt in ("purchase_order", "purchase-order", "purchase order"):
        return extract_purchase_order(pages, tables)
    if dt in ("tax_invoice", "tax-invoice", "tax invoice", "invoice"):
        return extract_tax_invoice(pages, tables)

    # unknown type
    return {}, ["unsupported_document_type"]
