import base64
import io
import os
import uuid

from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pypdf import PdfReader, PdfWriter
from dataclasses import asdict
 
from normalization_utils import (
    NormalizedDocument,
    DOCUMENT_NORMALIZERS,
    resolve_vendors,
    build_match_key,
)

from matching_utils import(
    find_doc,
    get_page_for_doc,
    check_vendor_gstin,
    check_vendor_name,
    check_total_value,
    check_line_items,
    llm_interpret_mismatches
)

print("main: module loaded")

from classifier.classifier import (
    classify_pages_node,
    extract_text_node,
    group_pages_node,
    validate_input_node,
)
from input_handler import process_document
from quality_checks import evaluate_document
from schemas import DocumentQualityResponse, PageQualityResponse


# --------------------------------------------------
# Load environment variables
# --------------------------------------------------
load_dotenv()


# --------------------------------------------------
# App Config
# --------------------------------------------------
APP_TITLE = os.getenv("APP_TITLE", "P2P Document Processing API")
APP_DESCRIPTION = os.getenv(
    "APP_DESCRIPTION",
    "Document processing API for quality evaluation, document classification, and data extraction."
)
APP_VERSION = os.getenv("APP_VERSION", "1.0.0")

QUALITY_UPLOAD_FOLDER = os.getenv("QUALITY_UPLOAD_FOLDER", os.getenv("UPLOAD_FOLDER", "data/uploads/quality_checks"))
CLASSIFIER_UPLOAD_FOLDER = os.getenv("CLASSIFIER_UPLOAD_FOLDER", os.getenv("UPLOAD_FOLDER", "data/uploads/classifier"))
CLASSIFIER_OUTPUT_FOLDER = os.getenv("CLASSIFIER_OUTPUT_FOLDER", os.getenv("OUTPUT_FOLDER", "data/Processed_docs"))


# --------------------------------------------------
# Pydantic Models
# --------------------------------------------------
class QualityPackage(BaseModel):
    file_name: str
    quality_report: DocumentQualityResponse
    file_bytes_base64: str


class ClassifiedPage(BaseModel):
    page_number: int
    document_type: str
    confidence: float
    reason: str
    classification_method: str = "rule_based"
    text_extraction_method: str | None = None
    ocr_used: bool = False
    ocr_error: str | None = None


class GroupedDocument(BaseModel):
    document_type: str
    start_page: int
    end_page: int
    pages: list[int]


class DocumentPayload(BaseModel):
    document_type: str
    document_name: str
    document_bytes_base64: str
    start_page: int | None = None
    end_page: int | None = None


class ClassificationPackage(QualityPackage):
    classified_pages: list[ClassifiedPage]
    grouped_documents: list[GroupedDocument]
    documents: list[DocumentPayload]


class ClassifyDocumentsResponse(ClassificationPackage):
    pass


class ExtractDocumentResponse(BaseModel):
    document_type: str
    document_name: str
    extracted_fields: dict
    missing_fields: list
    required_fields: list
    pages_count: int
    method_used: str
    document_bytes_base64: str


class ExtractDataRequest(BaseModel):
    documents: list[DocumentPayload]


# --------------------------------------------------
# Agentic Flow Models
# --------------------------------------------------
class MergedPageData(BaseModel):
    page_number: int
    quality_score: float | None = None
    is_compliant: bool | None = None
    document_type: str | None = None
    classification_confidence: float | None = None
    classification_method: str | None = None


class AgentState(BaseModel):
    file_path: str
    file_name: str
    file_bytes_base64: str | None = None
    quality_pages: list[dict] = []
    classified_pages: list[dict] = []
    merged_pages: list[MergedPageData] = []
    documents: list[DocumentPayload] = []
    extracted_data: list[dict] = []
    status: str = "initiated"
    message: str = ""
    decision_1_passed: bool | None = None
    decision_1_reason: str | None = None


class AgentResponse(BaseModel):
    agent_name: str
    status: str
    output: dict
    timestamp: str | None = None


class OrchestrationResponse(BaseModel):
    workflow_status: str
    quality_report: DocumentQualityResponse | None = None
    classified_pages: list[ClassifiedPage] = []
    extracted_data: list[dict] = []
    decision_1_result: dict | None = None
    decision_2_result: dict | None = None
    approval_required: bool = False
    communication_payload: dict | None = None
    approval_payload: dict | None = None
    message: str
    file_bytes_base64: str | None = None


# --------------------------------------------------
# FastAPI App Setup
# --------------------------------------------------
app = FastAPI(
    title=APP_TITLE,
    description=APP_DESCRIPTION,
    version=APP_VERSION,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


os.makedirs(QUALITY_UPLOAD_FOLDER, exist_ok=True)
os.makedirs(CLASSIFIER_UPLOAD_FOLDER, exist_ok=True)
os.makedirs(CLASSIFIER_OUTPUT_FOLDER, exist_ok=True)


# --------------------------------------------------
# Agent Orchestration Functions
# --------------------------------------------------

def quality_agent(file_path: str, file_name: str) -> tuple[list[dict], str]:
    """Quality Agent: Evaluates document quality page-wise."""
    print(f"orchestration: quality_agent invoked for {file_name}")
    try:
        with open(file_path, "rb") as f:
            file_bytes = f.read()
        quality_pages = evaluate_document(file_bytes, file_name)
        return quality_pages, "success"
    except Exception as e:
        print(f"orchestration: quality_agent failed: {e}")
        return [], f"quality_agent error: {str(e)}"


def classifier_agent(file_path: str, file_name: str) -> tuple[list[dict], list[dict], str]:
    """Classifier Agent: Classifies pages and groups documents."""
    print(f"orchestration: classifier_agent invoked for {file_name}")
    try:
        initial_state = build_initial_state(file_path, file_name)
        state = validate_input_node(initial_state)
        if state.get("status") == "error":
            return [], [], f"validation failed: {state.get('error')}"
        
        state = extract_text_node(state)
        if state.get("status") == "error":
            return [], [], f"text extraction failed: {state.get('error')}"
        
        state = classify_pages_node(state)
        if state.get("status") == "error":
            return [], [], f"classification failed: {state.get('error')}"
        
        state = group_pages_node(state)
        if state.get("status") == "error":
            return [], [], f"grouping failed: {state.get('error')}"
        
        return state.get("classified_pages", []), state.get("grouped_documents", []), "success"
    except Exception as e:
        print(f"orchestration: classifier_agent failed: {e}")
        return [], [], f"classifier_agent error: {str(e)}"


def merge_quality_and_classifier_data(quality_pages: list[dict], classified_pages: list[dict]) -> list[MergedPageData]:
    """Merge quality and classifier outputs by page number."""
    print("orchestration: merging quality and classifier data")
    print("-"*50, "quality_pages", "-"*50)
    # for page in quality_pages:
    #     print(page["page_number"])
    #     print(page["quality_score"])
    #     print(page["is_compliant"])
    #     print(page["reasons"])
    #     print(page["flowback_status"])
    #     print(page["schema_version"])
    #     print(page["quality_checks"])
    #     print(page["analysis_method"])

    print("-"*50, "classified_pages", "-"*50, classified_pages)
    merged = {}
    
    for page in quality_pages:
        page_num = page.get("page_number")
        merged[page_num] = MergedPageData(
            page_number=page_num,
            quality_score=page.get("quality_score"),
            is_compliant=page.get("is_compliant")
        )
    
    for page in classified_pages:
        page_num = page.get("page_number")
        if page_num in merged:
            merged[page_num].document_type = page.get("document_type")
            merged[page_num].classification_confidence = page.get("confidence")
            merged[page_num].classification_method = page.get("classification_method")
        else:
            merged[page_num] = MergedPageData(
                page_number=page_num,
                document_type=page.get("document_type"),
                classification_confidence=page.get("confidence"),
                classification_method=page.get("classification_method")
            )
    
    return sorted(merged.values(), key=lambda x: x.page_number)


def decision_node_1(merged_pages: list[MergedPageData], quality_threshold: float = 0.60) -> tuple[bool, str]:
    """Decision Node 1: Validates quality threshold and checks for missing documents."""
    print(f"orchestration: decision_node_1 checking {len(merged_pages)} pages with threshold {quality_threshold}")
    
    issues = []
    
    for page in merged_pages:
        if page.quality_score is not None and page.quality_score < quality_threshold:
            issues.append(f"Page {page.page_number}: quality {page.quality_score:.2f} below threshold")
    
    expected_types = {"purchase_order", "tax_invoice", "delivery_challan"}
    found_types = {page.document_type for page in merged_pages if page.document_type and page.document_type != "Unknown"}
    missing_types = expected_types - found_types
    
    if missing_types:
        issues.append(f"Missing document types: {', '.join(missing_types)}")
    
    passed = len(issues) == 0
    reason = "; ".join(issues) if issues else "All quality checks passed"
    
    print(f"orchestration: decision_node_1 result: passed={passed}, reason={reason}")
    return passed, reason


def extraction_agent(file_path: str, grouped_documents: list[dict], file_bytes: bytes) -> tuple[list[DocumentPayload], str]:
    """Extraction Agent: Splits PDF by document type and prepares for extraction."""
    print(f"orchestration: extraction_agent invoked")
    try:
        documents = split_pdf_bytes(file_bytes, grouped_documents)
        return documents, "success"
    except Exception as e:
        print(f"orchestration: extraction_agent failed: {e}")
        return [], f"extraction_agent error: {str(e)}"


def normalization_agent(extracted_data: list[dict]) -> tuple[list[dict], str]:
    """
    Args:
        extracted_data: list of dicts from extraction agent.
            Each dict: document_type, document_name, extracted_fields, method_used
 
    Returns:
        (normalized_data, status)
        Each item in normalized_data has the original keys plus:
          normalized_fields  — cleaned field values (floats, ISO dates, etc.)
          match_key          — flat dict for 3-way matching agent
          normalization_warnings — list of non-fatal issues found during cleaning
    """
    if not extracted_data:
        return [], "no_data"
 
    normalized_docs: list[NormalizedDocument] = []
 
    for item in extracted_data:
        doc_type = item.get("document_type", "unknown")
        raw_fields = item.get("extracted_fields") or {}
        warnings: list[str] = []
 
        normalizer = DOCUMENT_NORMALIZERS.get(doc_type)
        if normalizer:
            cleaned_fields = normalizer(raw_fields, warnings)
        else:
            cleaned_fields = dict(raw_fields)
            warnings.append(f"No normalizer defined for document_type '{doc_type}'")
 
        normalized_docs.append(NormalizedDocument(
            document_type=doc_type,
            document_name=item.get("document_name", ""),
            method_used=item.get("method_used", "unknown"),
            normalized_fields=cleaned_fields,
            normalization_warnings=warnings,
        ))
 
    try:
        vendor_map = resolve_vendors(normalized_docs)
    except Exception as e:
        vendor_map = {}
 
    for ndoc in normalized_docs:
        ndoc.match_key = build_match_key(ndoc, vendor_map)
        # Inline canonical vendor into fields so downstream agents don't need vendor_map
        if ndoc.match_key.get("canonical_vendor_name"):
            ndoc.normalized_fields["canonical_vendor_name"] = ndoc.match_key["canonical_vendor_name"]
        if ndoc.match_key.get("vendor_gstin"):
            ndoc.normalized_fields["vendor_gstin"] = ndoc.match_key["vendor_gstin"]
 
    output = [asdict(ndoc) for ndoc in normalized_docs]
    return output, "success"


def matching_agent(
    normalized_data: list[dict],
    classified_pages: list[dict],
) -> tuple[dict, str]:
    """
    Performs 3-way match: PO (source of truth) vs Invoice vs Delivery Challan.

    Args:
        normalized_data:  output of normalization_agent (list of normalized doc dicts)
        classified_pages: output of classifier_agent (list of page dicts with page_number + document_type)

    Returns:
        (result_dict, status)
        result_dict keys:
          result        — "match" | "mismatch"
          matches       — list of passed check descriptions
          mismatches    — list of mismatch dicts (field, document_type, page_number, po_value, actual_value, note)
          summary       — human-readable one-liner
    """
    print("matching_agent: starting 3-way match")

    po_doc      = find_doc(normalized_data, "purchase_order")
    invoice_doc = find_doc(normalized_data, "tax_invoice")
    challan_doc = find_doc(normalized_data, "delivery_challan")

    # Can't match without PO
    if not po_doc:
        return {
            "result": "mismatch",
            "matches": [],
            "mismatches": [],
            "summary": "3-way match failed: Purchase Order not found in normalized data",
        }, "error"

    po_fields      = po_doc.get("normalized_fields") or {}
    invoice_fields = (invoice_doc or {}).get("normalized_fields") or {}
    challan_fields = (challan_doc or {}).get("normalized_fields") or {}

    invoice_page = get_page_for_doc(classified_pages, "tax_invoice")
    challan_page = get_page_for_doc(classified_pages, "delivery_challan")

    matches:    list[str]  = []
    mismatches: list[dict] = []

    # ── Check 1: Vendor GSTIN (PO vs Challan) ──
    if challan_doc:
        check_vendor_gstin(po_fields, challan_fields, challan_page, mismatches, matches)
        check_vendor_name(po_fields, challan_fields, challan_page, mismatches, matches)
    else:
        matches.append("vendor checks: skipped (no delivery challan)")

    # ── Check 2: Total value (PO vs Invoice) ──
    if invoice_doc:
        check_total_value(po_fields, invoice_fields, invoice_page, mismatches, matches)
        check_line_items(po_fields, invoice_fields, invoice_page, mismatches, matches)
    else:
        matches.append("invoice checks: skipped (no tax invoice)")

    result = "match" if not mismatches else "mismatch"

    summary = (
        f"3-way match PASSED: {len(matches)} checks passed"
        if result == "match"
        else f"3-way match FAILED: {len(mismatches)} mismatch(es) found across {len(matches) + len(mismatches)} checks"
    )

    print(f"matching_agent: {summary}")

    # LLM interpretation — only on mismatch
    llm_interpretation = None
    if mismatches:
        print("matching_agent: invoking LLM to interpret mismatches")
        llm_interpretation = llm_interpret_mismatches(
            mismatches, po_fields, invoice_fields, challan_fields
        )
        print(f"matching_agent: LLM recommended action: {llm_interpretation.get('recommended_action')}")

    return {
        "result": result,
        "matches": matches,
        "mismatches": mismatches,
        "summary": summary,
        "llm_interpretation": llm_interpretation,
    }, "success"
    

def decision_node_2(matching_result: dict) -> tuple[bool, str]:
    """Decision Node 2: Validates 3-way match result."""
    print(f"orchestration: decision_node_2 checking matching result")
    
    result = matching_result.get("result")
    summary = matching_result.get("summary", "No summary available")
    mismatches = matching_result.get("mismatches", [])

    if result == "match":
        print(f"orchestration: decision_node_2 passed — {summary}")
        return True, summary

    mismatch_fields = [m.get("field", "unknown") for m in mismatches]
    reason = f"{summary}. Mismatched fields: {', '.join(mismatch_fields)}"
    
    print(f"orchestration: decision_node_2 failed — {reason}")
    return False, reason

def communication_agent(matching_result: dict) -> dict:
    """Communication Agent: Formulates a structured message payload for mismatch discrepancies."""
    print("orchestration: communication_agent invoked")

    mismatches = matching_result.get("mismatches", [])
    summary = matching_result.get("summary", "3-way match failed")
    llm_interpretation = matching_result.get("llm_interpretation") or {}

    discrepancy_table = [
        {
            "field": m.get("field"),
            "document_type": m.get("document_type"),
            "page_number": m.get("page_number"),
            "po_value": m.get("po_value"),
            "actual_value": m.get("actual_value"),
            "note": m.get("note"),
        }
        for m in mismatches
    ]

    email_body = llm_interpretation.get("email_draft") or llm_interpretation.get("recommended_action") or (
        f"Dear Vendor,\n\n"
        f"We have identified discrepancies during our 3-way matching process.\n\n"
        f"Summary: {summary}\n\n"
        f"Please review the discrepancies and revert at the earliest.\n\n"
        f"Regards,\nAccounts Payable Team"
    )

    payload = {
        "type": "communication",
        "summary": summary,
        "discrepancy_table": discrepancy_table,
        "llm_reasoning": llm_interpretation.get("reasoning"),
        "email": {
            "to": None,
            "subject": f"Discrepancy Notice — {len(mismatches)} mismatch(es) found",
            "body": email_body,
        },
        "actions": [
            {"id": "send_email", "label": "Send Email to Vendor"},
            {"id": "flag_for_review", "label": "Flag for Internal Review"},
            {"id": "escalate", "label": "Escalate to Manager"},
        ]
    }

    print(f"communication_agent: payload built with {len(discrepancy_table)} discrepancies")
    return payload


def approval_agent(matching_result: dict, normalized_data: list[dict]) -> dict:
    """Approval Agent: Raises approval request via chat interface with key fields and actions."""
    print("orchestration: approval_agent invoked")

    def get_key_fields(normalized_data: list[dict], doc_type: str) -> dict:
        doc = find_doc(normalized_data, doc_type)
        if not doc:
            return {}
        fields = doc.get("normalized_fields") or {}
        return {
            "vendor_name": fields.get("vendor_name") or fields.get("canonical_vendor_name"),
            "vendor_gstin": fields.get("vendor_gstin"),
            "total_value": fields.get("total_value") or fields.get("grand_total"),
            "document_number": fields.get("po_number") or fields.get("invoice_number") or fields.get("challan_number"),
            "document_date": fields.get("po_date") or fields.get("invoice_date") or fields.get("challan_date"),
        }

    payload = {
        "type": "approval",
        "summary": matching_result.get("summary"),
        "match_result": matching_result.get("result"),
        "documents": {
            "purchase_order": get_key_fields(normalized_data, "purchase_order"),
            "tax_invoice": get_key_fields(normalized_data, "tax_invoice"),
            "delivery_challan": get_key_fields(normalized_data, "delivery_challan"),
        },
        "matches": matching_result.get("matches", []),
        "actions": [
            {"id": "approve", "label": "Approve"},
            {"id": "reject", "label": "Reject"},
            {"id": "request_more_info", "label": "Request More Info"},
            {"id": "upload_supporting_doc", "label": "Upload Supporting Document"},
        ]
    }

    print(f"orchestration: approval_agent payload built for match result: {matching_result.get('result')}")
    return payload


# --------------------------------------------------
# Utility helpers
# --------------------------------------------------

def encode_bytes(data: bytes) -> str:
    return base64.b64encode(data).decode("utf-8")


def decode_base64(data: str) -> bytes:
    try:
        return base64.b64decode(data)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid base64 payload: {exc}")


def save_bytes_to_folder(file_bytes: bytes, filename: str, folder: str) -> str:
    os.makedirs(folder, exist_ok=True)
    unique_filename = f"{uuid.uuid4().hex}_{filename}"
    file_path = os.path.join(folder, unique_filename)
    with open(file_path, "wb") as f:
        f.write(file_bytes)
    return file_path


def split_pdf_bytes(pdf_bytes: bytes, grouped_documents: list[dict]) -> list[dict]:
    reader = PdfReader(io.BytesIO(pdf_bytes))
    documents = []
    print()
    for group in grouped_documents:
        document_type = group["document_type"]
        if document_type == "Unknown":
            continue

        writer = PdfWriter()
        for page_number in group["pages"]:
            writer.add_page(reader.pages[page_number - 1])

        buffer = io.BytesIO()
        writer.write(buffer)
        buffer.seek(0)
        document_bytes = buffer.getvalue()
        print(f"split_pdf_bytes: created document for type {document_type} with pages {group['pages']} and size {len(document_bytes)} bytes")
        documents.append({
            "document_type": document_type,
            "document_name": f"{document_type.replace(' ', '_')}_{group['start_page']}_{group['end_page']}.pdf",
            "document_bytes_base64": encode_bytes(document_bytes),
            "start_page": group["start_page"],
            "end_page": group["end_page"],
        })

    return documents


def build_initial_state(input_file_path: str, input_file_name: str) -> dict:
    return {
        "input_file_path": input_file_path,
        "input_file_name": input_file_name,
        "output_folder": CLASSIFIER_OUTPUT_FOLDER,
        "total_pages": 0,
        "extracted_pages": [],
        "classified_pages": [],
        "grouped_documents": [],
        "extracted_documents": [],
        "extracted_data": [],
        "status": "started",
        "message": "Workflow started.",
        "error": None,
        "response": None,
    }


# =====================================================
# API Endpoints - Agentic Orchestration
# =====================================================

@app.post("/orchestrate", response_model=OrchestrationResponse)
async def orchestrate(file: UploadFile):
    """
    Main orchestration endpoint: Runs the complete agentic flow.
    Input File -> Quality Agent -> Classifier Agent -> Decision 1 -> Extraction Agent -> Decision 2 -> Approval Agent
    """
    print("main: /orchestrate invoked")
    
    payload = await file.read()
    if not payload:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")
    
    try:
        temp_file_path = save_bytes_to_folder(payload, file.filename, CLASSIFIER_UPLOAD_FOLDER)
        file_bytes_b64 = encode_bytes(payload)
        
        # Step 1: Quality Agent
        quality_pages, quality_status = quality_agent(temp_file_path, file.filename)
        if quality_status != "success":
            return OrchestrationResponse(
                workflow_status="quality_agent_failed",
                message=quality_status,
                file_bytes_base64=file_bytes_b64
            )
        
        # Step 2: Classifier Agent
        classified_pages, grouped_documents, classifier_status = classifier_agent(temp_file_path, file.filename)
        if classifier_status != "success":
            return OrchestrationResponse(
                workflow_status="classifier_agent_failed",
                message=classifier_status,
                file_bytes_base64=file_bytes_b64
            )
        
        # Step 3: Merge data
        merged_pages = merge_quality_and_classifier_data(quality_pages, classified_pages)
        
        # Step 4: Decision Node 1
        decision_1_passed, decision_1_reason = decision_node_1(merged_pages, quality_threshold=0.60)
        
        if not decision_1_passed:
            return OrchestrationResponse(
                workflow_status="decision_1_failed",
                message=f"Quality checks failed. {decision_1_reason}",
                decision_1_result={"passed": False, "reason": decision_1_reason},
                approval_required=True,
                file_bytes_base64=file_bytes_b64
            )
        
        # Step 5: Extraction Agent
        documents, extraction_status = extraction_agent(temp_file_path, grouped_documents, payload)
        if extraction_status != "success":
            return OrchestrationResponse(
                workflow_status="extraction_agent_failed",
                message=extraction_status,
                file_bytes_base64=file_bytes_b64
            )
        # Step 6: Extract fields from each document
        extracted_data = []
        for document in documents:
            doc_bytes = decode_base64(document["document_bytes_base64"])
            extraction_result = process_document(
                doc_bytes,
                document["document_name"],
                document["document_type"]
            )
            extracted_data.append({
                "document_type": document["document_type"],
                "document_name": document["document_name"],
                "extracted_fields": extraction_result["fields"],
                # "missing_fields": extraction_result["missing_fields"],
                "method_used": extraction_result.get("method_used", "rule_based")
            })
        
        # Step 7: Normalization Agent
        normalized_data, norm_status = normalization_agent(extracted_data)
        print(f"main: Normalization completed with status: {norm_status}")

        # Step 8: Matching Agent
        matching_result, matching_status = matching_agent(normalized_data, classified_pages)
        print(f"main: Matching completed with status: {matching_status}")
        
        # Step 9: Decision Node 2
        decision_2_passed, decision_2_reason = decision_node_2(matching_result)

        if not decision_2_passed:
            communication_payload = communication_agent(matching_result)
            return OrchestrationResponse(
                workflow_status="decision_2_failed",
                message=f"3-way match failed. {decision_2_reason}",
                decision_2_result={"passed": False, "reason": decision_2_reason},
                approval_required=True,
                communication_payload=communication_payload,
                file_bytes_base64=file_bytes_b64
            )
        
        # Step 10: Approval Agent
        approval_payload = approval_agent(matching_result, normalized_data)

        return OrchestrationResponse(
            workflow_status="success",
            quality_report={"pages": quality_pages},
            classified_pages=[
                ClassifiedPage(
                    page_number=p.get("page_number"),
                    document_type=p.get("document_type"),
                    confidence=p.get("confidence"),
                    reason=p.get("reason"),
                    classification_method=p.get("classification_method", "rule_based")
                )
                for p in classified_pages
            ],
            extracted_data=extracted_data,
            decision_1_result={"passed": decision_1_passed, "reason": decision_1_reason},
            decision_2_result={"passed": decision_2_passed, "reason": decision_2_reason},
            approval_required=True,
            approval_payload=approval_payload,
            message="Orchestration completed successfully. Awaiting approval.",
            file_bytes_base64=file_bytes_b64
        )
    
    except Exception as e:
        print(f"main: /orchestrate error: {e}")
        raise HTTPException(status_code=500, detail=f"Orchestration failed: {str(e)}")


@app.post("/classify-documents")
async def classify_documents(file: UploadFile):
    """
    Simplified classifier endpoint: Classifies pages and groups documents.
    Does NOT use agentic orchestration - runs classification pipeline directly.
    Accepts file upload and returns classification results.
    
    Workflow:
    1. Validate input file
    2. Extract text page-wise
    3. Classify each page
    4. Group consecutive pages by document type
    5. Split into separate PDF documents
    """
    print("main: /classify-documents invoked")
    
    payload = await file.read()
    if not payload:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")
    
    try:
        # Save uploaded file temporarily
        temp_file_path = save_bytes_to_folder(payload, file.filename, CLASSIFIER_UPLOAD_FOLDER)
        file_bytes_b64 = encode_bytes(payload)
        
        # Step 1: Validate input
        print("main: /classify-documents - validating input")
        state = build_initial_state(temp_file_path, file.filename)
        state = validate_input_node(state)
        if state.get("status") == "error":
            raise HTTPException(status_code=400, detail=state.get("error") or state.get("message"))
        
        # Step 2: Extract text
        print("main: /classify-documents - extracting text")
        state = extract_text_node(state)
        if state.get("status") == "error":
            raise HTTPException(status_code=500, detail=state.get("error") or state.get("message"))
        
        # Step 3: Classify pages
        print("main: /classify-documents - classifying pages")
        state = classify_pages_node(state)
        if state.get("status") == "error":
            raise HTTPException(status_code=500, detail=state.get("error") or state.get("message"))
        
        # Step 4: Group documents
        print("main: /classify-documents - grouping documents")
        state = group_pages_node(state)
        if state.get("status") == "error":
            raise HTTPException(status_code=500, detail=state.get("error") or state.get("message"))
        
        # Step 5: Split documents
        print("main: /classify-documents - splitting documents")
        documents = split_pdf_bytes(payload, state.get("grouped_documents", []))
        
        # Return simplified response
        return {
            "file_name": file.filename,
            "classified_pages": state.get("classified_pages", []),
            "grouped_documents": state.get("grouped_documents", []),
            "documents": documents,
            "file_bytes_base64": file_bytes_b64,
            "total_pages": state.get("total_pages", 0),
            "status": "success",
            "message": "Classification completed successfully"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"main: /classify-documents error: {e}")
        raise HTTPException(status_code=500, detail=f"Classification failed: {str(e)}")



@app.get("/")
async def health_check():
    """
    Health check endpoint. Returns API status and folder configuration.
    """
    return {
        "status": "running",
        "message": "P2P Document Processing API is running with agentic orchestration.",
        "version": APP_VERSION,
        "endpoints": {
            "orchestrate": "/orchestrate - Full agentic workflow",
            "classify_documents": "/classify-documents - Classifier agent only",
            "health": "/ - Health check",
        },
        "agentic_flow": [
            "Input File",
            "Quality Agent",
            "Classifier Agent",
            "Decision Node 1 (Quality Check)",
            "Extraction Agent",
            "Data Normalization Agent",
            "3-Way Matching Agent",
            "Decision Node 2 (Matching Check)",
            "Communication Agent",
            "Approval Agent"
        ],
        "folder_config": {
            "quality_uploads": QUALITY_UPLOAD_FOLDER,
            "classifier_uploads": CLASSIFIER_UPLOAD_FOLDER,
            "classifier_output": CLASSIFIER_OUTPUT_FOLDER,
        },
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
