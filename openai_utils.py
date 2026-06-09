import os
from typing import Optional, Type, Dict

from dotenv import load_dotenv
from pydantic import BaseModel, Field
from langchain_core.messages import HumanMessage
from langchain_openai import AzureChatOpenAI

load_dotenv()

# ============================================================
# Common Models
# ============================================================

class SupplierDetails(BaseModel):
    name: Optional[str] = None
    address: Optional[str] = None
    gstin: Optional[str] = None


class ItemDetails(BaseModel):
    description: Optional[str] = None
    quantity: Optional[str] = None
    unit: Optional[str] = None
    unit_price: Optional[str] = None


# ============================================================
# Delivery Challan Schema
# ============================================================

class DeliveryChallanSchema(BaseModel):
    delivery_challan_number: Optional[str] = None
    date_of_issue: Optional[str] = None
    supplier_details: SupplierDetails = Field(
        default_factory=SupplierDetails
    )


# ============================================================
# Purchase Order Schema
# ============================================================

class PurchaseOrderSchema(BaseModel):
    po_number: Optional[str] = None
    po_date: Optional[str] = None

    buyer_name: Optional[str] = None
    buyer_address: Optional[str] = None
    buyer_gstin: Optional[str] = None

    supplier_name: Optional[str] = None
    supplier_address: Optional[str] = None
    supplier_gstin: Optional[str] = None

    delivery_address: Optional[str] = None
    billing_address: Optional[str] = None

    item_details: list[ItemDetails] = Field(default_factory=list)

    total_order_value: Optional[str] = None
    taxes: Optional[str] = None

    delivery_schedule: Optional[str] = None
    payment_terms: Optional[str] = None
    terms_conditions: Optional[str] = None

    authorized_signatory: Optional[str] = None


# ============================================================
# Tax Invoice Schema
# ============================================================

class TaxInvoiceSchema(BaseModel):
    invoice_number: Optional[str] = None
    invoice_date: Optional[str] = None

    quantity: Optional[str] = None
    unit_price: Optional[str] = None

    taxable_value: Optional[str] = None
    discount: Optional[str] = None
    gst_rates: Optional[str] = None

    total_invoice_value: Optional[str] = None


# ============================================================
# Schema Registry
# ============================================================

DOCUMENT_SCHEMA_MAPPING: Dict[str, Type[BaseModel]] = {
    "delivery_challan": DeliveryChallanSchema,
    "purchase_order": PurchaseOrderSchema,
    "tax_invoice": TaxInvoiceSchema,
}


# ============================================================
# Azure OpenAI Setup
# ============================================================

def _has_config_value(value: Optional[str]) -> bool:
    if not value:
        return False

    normalized = value.strip().lower()

    return not (
        normalized.startswith("replace-with")
        or "your-" in normalized
        or normalized in {"changeme", "todo"}
    )


def is_azure_openai_enabled() -> bool:
    required_values = [
        os.getenv("AZURE_OPENAI_API_KEY"),
        os.getenv("AZURE_OPENAI_ENDPOINT"),
        os.getenv("AZURE_OPENAI_DEPLOYMENT"),
        os.getenv("OPENAI_API_VERSION"),
    ]

    return all(_has_config_value(v) for v in required_values)


def get_llm(
    deployment: Optional[str] = None,
    temperature: float = 0.0,
    max_tokens: int = 2048,
) -> AzureChatOpenAI:

    if not is_azure_openai_enabled():
        raise ValueError("Azure OpenAI is not configured")

    deployment = (
        deployment
        or os.getenv("AZURE_OPENAI_DEPLOYMENT")
    )

    return AzureChatOpenAI(
        azure_deployment=deployment,
        api_version=os.getenv("OPENAI_API_VERSION"),
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
        api_key=os.getenv("AZURE_OPENAI_API_KEY"),
        temperature=temperature,
        max_tokens=max_tokens,
    )


# ============================================================
# Plain Text Query
# ============================================================

def query_openai(
    prompt: str,
    deployment: Optional[str] = None,
    max_tokens: int = 2048,
    temperature: float = 0.0,
) -> str:

    llm = get_llm(
        deployment=deployment,
        temperature=temperature,
        max_tokens=max_tokens,
    )

    response = llm.invoke(
        [HumanMessage(content=prompt)]
    )

    return response.content.strip()


# ============================================================
# Structured Query
# ============================================================

def query_openai_structured(
    prompt: str,
    document_type: str,
    deployment: Optional[str] = None,
    max_tokens: int = 2048,
    temperature: float = 0.0,
):

    if document_type not in DOCUMENT_SCHEMA_MAPPING:
        raise ValueError(
            f"Unsupported document_type: {document_type}"
        )

    schema = DOCUMENT_SCHEMA_MAPPING[document_type]

    llm = get_llm(
        deployment=deployment,
        temperature=temperature,
        max_tokens=max_tokens,
    )

    structured_llm = llm.with_structured_output(schema)

    extraction_prompt = f"""
You are an expert document extraction engine.

Extract all fields defined in the schema.

Rules:
- Return null if field not found.
- Do not hallucinate values.
- Preserve values exactly as seen.
- Extract only information present in the document.

Document Type:
{document_type}

Document Content:
{prompt}
"""

    return structured_llm.invoke(extraction_prompt)