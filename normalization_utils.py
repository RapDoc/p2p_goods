import re
import json
from datetime import datetime
from dataclasses import dataclass, field
from typing import Optional
from difflib import SequenceMatcher


# Constants

# Legal entity suffixes to strip before vendor comparison (order matters: longest first)
LEGAL_SUFFIX_PATTERNS = [
    r"\bprivate\s+limited\b",
    r"\bpvt[\.\s]+ltd[\.]?\b",
    r"\bpvt[\.\s]+limited\b",
    r"\blimited\b",
    r"\bltd[\.]?\b",
    r"\bllp\b",
    r"\binc[\.]?\b",
    r"\bcorp[\.]?\b",
    r"\bco[\.]?\b",
    r"\benterprises\b",
    r"\bgroup\b",
]

# Known date formats the extractor produces
DATE_FORMATS = [
    "%d/%m/%Y",
    "%m/%d/%Y",
    "%Y-%m-%d",
    "%d-%m-%Y",
    "%d %b %Y",
    "%d %B %Y",
    "%b %d, %Y",
]

# GSTIN regex for India: 2-digit state code + 10-char PAN + 1 entity + 1 check digit
GSTIN_RE = re.compile(r"\b\d{2}[A-Z]{5}\d{4}[A-Z]{1}[A-Z\d]{1}[Z]{1}[A-Z\d]{1}\b")

# Confidence threshold below which we call the LLM
VENDOR_MATCH_CONFIDENCE_THRESHOLD = 0.75


# Data models

@dataclass
class NormalizedVendor:
    original_name: str
    canonical_name: str           # title-cased, no legal suffixes
    gstin: Optional[str]
    normalization_method: str     # "rule_based" | "llm"


@dataclass
class NormalizedDocument:
    document_type: str            # tax_invoice | purchase_order | delivery_challan | e_way_bill
    document_name: str
    method_used: str              # original extraction method
    normalized_fields: dict       # full cleaned copy of extracted_fields
    match_key: dict = field(default_factory=dict)
    normalization_warnings: list[str] = field(default_factory=list)


# Rule-based helpers

def clean_numeric(value) -> Optional[float]:
    """Strip currency symbols, commas, spaces. Returns float or None."""
    if value is None:
        return None
    s = re.sub(r"[₹$€£,\s]", "", str(value).strip())
    try:
        return float(s)
    except ValueError:
        return None


def parse_date_iso(value: Optional[str]) -> Optional[str]:
    """
    Try all known date formats. Returns ISO 8601 (YYYY-MM-DD) or None.
    Defaults to DD/MM/YYYY on ambiguity (Indian document convention).
    """
    if not value:
        return None
    value = value.strip()
    if re.match(r"^\d{4}-\d{2}-\d{2}$", value):
        return value
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(value, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def strip_legal_suffixes(name: str) -> str:
    """Remove legal entity suffixes and return a clean title-cased string."""
    result = name.strip().lower()
    for pattern in LEGAL_SUFFIX_PATTERNS:
        result = re.sub(pattern, "", result, flags=re.IGNORECASE)
    result = re.sub(r"[\s.,;()\[\]]+$", "", result)
    result = re.sub(r"\s+", " ", result).strip().title()
    return result


def extract_gstin(text: Optional[str]) -> Optional[str]:
    """Pull first valid GSTIN from a free-text field."""
    if not text:
        return None
    m = GSTIN_RE.search(text.upper())
    return m.group(0) if m else None


def vendor_similarity(a: str, b: str) -> float:
    """SequenceMatcher similarity after stripping legal suffixes. Returns 0..1."""
    return SequenceMatcher(
        None,
        strip_legal_suffixes(a).lower(),
        strip_legal_suffixes(b).lower(),
    ).ratio()


# LLM fallback (uses project-standard openai_utils)

def llm_resolve_vendor(
    names: list[str],
    gstins: list[Optional[str]],
) -> dict:
    """
    Ask the LLM to pick the canonical name from a list of variant vendor names.
    Returns {"canonical_name": str, "are_same_entity": bool, "confidence": float, "reasoning": str}
    Falls back to rule-based result if the call fails.
    """
    from openai_utils import query_openai  # local import keeps utils dependency optional

    lines = "\n".join(
        f'  {i}. "{name}" (GSTIN: {gstin or "N/A"})'
        for i, (name, gstin) in enumerate(zip(names, gstins), 1)
    )
    prompt = (
        "You are a data normalization assistant for an accounts payable system.\n"
        "Below are variant spellings of what may be the same vendor, "
        "along with their GSTINs (Indian tax IDs) where available.\n\n"
        f"Vendor names:\n{lines}\n\n"
        "Respond ONLY with a JSON object (no markdown, no explanation) with keys:\n"
        '  "canonical_name": single best name (title case, no legal suffixes),\n'
        '  "are_same_entity": true if all names refer to the same company,\n'
        '  "confidence": 0.0-1.0,\n'
        '  "reasoning": one sentence\n'
    )

    try:
        raw = query_openai(prompt, max_tokens=256, temperature=0.0)
        raw = re.sub(r"```json|```", "", raw).strip()
        return json.loads(raw)
    except Exception as e:
        return {
            "canonical_name": strip_legal_suffixes(names[0]),
            "are_same_entity": False,
            "confidence": 0.0,
            "reasoning": f"LLM call failed: {e}",
        }


# Per-document field normalizers

def normalize_tax_invoice(fields: dict, warnings: list) -> dict:
    out = dict(fields)
    out["invoice_date"] = parse_date_iso(fields.get("invoice_date"))
    if not out["invoice_date"]:
        warnings.append("invoice_date could not be parsed")
    for key in ("quantity", "taxable_value", "total_invoice_value", "discount", "unit_price"):
        raw = fields.get(key)
        out[key] = clean_numeric(raw)
        if raw is not None and out[key] is None:
            warnings.append(f"{key}: could not parse '{raw}' as number")
    return out


def normalize_purchase_order(fields: dict, warnings: list) -> dict:
    out = dict(fields)
    out["po_date"] = parse_date_iso(fields.get("po_date"))
    out["delivery_schedule"] = parse_date_iso(fields.get("delivery_schedule"))
    out["total_order_value"] = clean_numeric(fields.get("total_order_value"))
    if out["total_order_value"] is None:
        warnings.append("total_order_value could not be parsed")
    out["item_details"] = [
        {**item, "quantity": clean_numeric(item.get("quantity")), "unit_price": clean_numeric(item.get("unit_price"))}
        for item in (fields.get("item_details") or [])
    ]
    return out


def normalize_delivery_challan(fields: dict, warnings: list) -> dict:
    out = dict(fields)
    out["date_of_issue"] = parse_date_iso(fields.get("date_of_issue"))
    return out


def normalize_e_way_bill(fields: dict, warnings: list) -> dict:
    return dict(fields)


DOCUMENT_NORMALIZERS = {
    "tax_invoice": normalize_tax_invoice,
    "purchase_order": normalize_purchase_order,
    "delivery_challan": normalize_delivery_challan,
    "e_way_bill": normalize_e_way_bill,
}


# Vendor resolution across documents

def resolve_vendors(documents: list[NormalizedDocument]) -> dict[str, NormalizedVendor]:
    """
    Collect all vendor mentions, group by GSTIN (exact) then name similarity,
    resolve each group to a canonical name (rule-based first, LLM fallback).
    Returns: original_name -> NormalizedVendor
    """
    candidates: list[tuple[str, Optional[str]]] = []

    for doc in documents:
        f, dt = doc.normalized_fields, doc.document_type
        if dt == "purchase_order":
            if supplier := f.get("supplier_name", ""):
                candidates.append((supplier, f.get("supplier_gstin")))
            if buyer := f.get("buyer_name", ""):
                candidates.append((buyer, f.get("buyer_gstin")))
        elif dt == "delivery_challan":
            supplier_info = f.get("supplier_details") or {}
            if name := supplier_info.get("name", ""):
                candidates.append((name, supplier_info.get("gstin")))

    if not candidates:
        return {}

    groups: list[list[tuple[str, Optional[str]]]] = []

    def find_group(name: str, gstin: Optional[str]) -> Optional[int]:
        for i, group in enumerate(groups):
            if gstin and any(g == gstin for _, g in group if g):
                return i
            if any(vendor_similarity(name, n) >= VENDOR_MATCH_CONFIDENCE_THRESHOLD for n, _ in group):
                return i
        return None

    for name, gstin in candidates:
        if not name:
            continue
        idx = find_group(name, gstin)
        if idx is not None:
            groups[idx].append((name, gstin))
        else:
            groups.append([(name, gstin)])

    vendor_map: dict[str, NormalizedVendor] = {}

    for group in groups:
        names = [n for n, _ in group]
        gstins = [g for _, g in group]
        best_gstin = next((g for g in gstins if g), None)
        longest = max(names, key=len)
        rule_canonical = strip_legal_suffixes(longest)
        rule_sim = min(vendor_similarity(n, longest) for n in names)

        if rule_sim >= VENDOR_MATCH_CONFIDENCE_THRESHOLD:
            canonical, method = rule_canonical, "rule_based"
        else:
            result = llm_resolve_vendor(names, gstins)
            canonical, method = result.get("canonical_name", rule_canonical), "llm"

        for original_name, gstin in group:
            vendor_map[original_name] = NormalizedVendor(
                original_name=original_name,
                canonical_name=canonical,
                gstin=best_gstin or gstin,
                normalization_method=method,
            )

    return vendor_map


# Match key builder

def build_match_key(doc: NormalizedDocument, vendor_map: dict[str, NormalizedVendor]) -> dict:
    """
    Flat dict for the 3-way matching agent.
    tax_invoice:      invoice_number, total_value, document_date
    purchase_order:   canonical_vendor_name, vendor_gstin, po_number, total_value, document_date
    delivery_challan: canonical_vendor_name, vendor_gstin, challan_number, document_date
    """
    f, dt = doc.normalized_fields, doc.document_type
    key: dict = {"document_type": dt}

    def vendor_name(name: Optional[str]) -> Optional[str]:
        if not name:
            return None
        return vendor_map[name].canonical_name if name in vendor_map else strip_legal_suffixes(name)

    def vendor_gstin(name: Optional[str], fallback: Optional[str] = None) -> Optional[str]:
        return vendor_map[name].gstin if (name and name in vendor_map) else fallback

    if dt == "tax_invoice":
        key.update(
            invoice_number=f.get("invoice_number"),
            total_value=f.get("total_invoice_value"),
            document_date=f.get("invoice_date"),
        )

    elif dt == "purchase_order":
        sn = f.get("supplier_name")
        key.update(canonical_vendor_name=vendor_name(sn), vendor_gstin=vendor_gstin(sn, f.get("supplier_gstin")),
                   po_number=f.get("po_number"),
                   total_value=f.get("total_order_value"), document_date=f.get("po_date"))

    elif dt == "delivery_challan":
        si = f.get("supplier_details") or {}
        sn = si.get("name")
        key.update(canonical_vendor_name=vendor_name(sn), vendor_gstin=vendor_gstin(sn, si.get("gstin")),
                   challan_number=f.get("delivery_challan_number"), document_date=f.get("date_of_issue"))

    elif dt == "e_way_bill":
        key["eway_bill_number"] = f.get("eway_bill_number")

    return key