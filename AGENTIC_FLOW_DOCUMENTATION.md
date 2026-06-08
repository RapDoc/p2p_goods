# Agentic Orchestration Flow Documentation

## Overview
The P2P Document Processing API now implements a multi-agent orchestration system that processes documents through a series of specialized agents and decision nodes. The orchestration handles document quality evaluation, classification, extraction, and normalization through an intelligent workflow with human-in-the-loop decision points.

## Agentic Flow Architecture

```
┌─────────────────┐
│  Input File     │
└────────┬────────┘
         │
    ┌────▼─────────────┐
    │ Quality Agent    │  → Evaluates page-wise quality metrics
    └────┬─────────────┘     (blur, skew, contrast, resolution, OCR conf)
         │
    ┌────▼────────────────┐
    │ Classifier Agent    │  → Classifies pages by document type (PO, Invoice, DC)
    └────┬────────────────┘     Groups consecutive pages
         │
    ┌────▼──────────────────────────────────────────────────────┐
    │ Merge Quality + Classifier Data                           │
    │ (Combine quality metrics with document type per page)     │
    └────┬───────────────────────────────────────────────────────┘
         │
    ┌────▼─────────────────────────────────────────────────────────────┐
    │ DECISION NODE 1: Quality & Completeness Check                    │
    │                                                                   │
    │ Pass Criteria:                                                    │
    │   - All pages quality_score >= 0.60 (60%)                        │
    │   - All expected document types present (PO, Invoice, DC)        │
    │                                                                   │
    │ If FAIL: Return with approval_required=True                      │
    │ (User can reupload missing documents or original high-quality)   │
    └────┬────────────────────────────────────────────────────────────┘
         │ PASS
    ┌────▼──────────────────┐
    │ Extraction Agent      │  → Splits PDF into separate docs per type
    └────┬──────────────────┘     Extracts structured fields:
         │                         - Invoice: number, date, supplier, buyer, GST, totals, line items
         │                         - PO: number, date, vendor, buyer, line items
         │                         - Delivery Challan: number, date, supplier, line items
    ┌────▼─────────────────────────┐
    │ Data Normalization (TODO)    │  → Normalize units, vendor names, currencies
    └────┬───────────────────────────┘     Standardize field formats
         │
    ┌────▼──────────────────────────┐
    │ 3-Way Matching (TODO)         │  → Match PO ↔ Invoice ↔ Delivery Challan
    └────┬───────────────────────────┘     Verify quantities, amounts, dates
         │
    ┌────▼─────────────────────────────────────────────────────────────┐
    │ DECISION NODE 2: Matching Validation (TODO)                      │
    │                                                                   │
    │ Pass Criteria:                                                    │
    │   - PO, Invoice, Delivery Challan quantities match                │
    │   - Amounts match within tolerance                               │
    │   - Dates are consistent                                         │
    │                                                                   │
    │ If FAIL: Call Communication Agent to raise discrepancy issue     │
    └────┬────────────────────────────────────────────────────────────┘
         │ PASS
    ┌────▼──────────────────────┐
    │ Communication Agent (TODO) │  → Formulate JSON messages for interface
    │ Approval Agent (TODO)      │  → Raise approval requests
    └────┬──────────────────────┘
         │
    ┌────▼──────────────────┐
    │ Response to Client    │
    └───────────────────────┘
```

## Agent Specifications

### 1. Quality Agent
**Purpose**: Evaluate document quality page-by-page using metrics like blur, skew, contrast, resolution, OCR confidence.

**Input**: File path and file bytes
**Output**: List of quality pages with metrics
**Implementation Location**: [quality_checks.py](quality_checks.py)

**Output Structure**:
```python
{
    "page_number": int,
    "quality_score": float,  # 0.0-1.0
    "is_compliant": bool,
    "reasons": [str],
    "quality_checks": {
        "page_blurriness": str,
        "page_rotation": str,
        "ocr_confidence_score": str,
        "resolution_validation": str,
        "crop_cutoff": str,
        "clarity_rating": str,
        "blank_page": str,
        "content_coverage": str
    },
    "analysis_method": "rule_based" | "gpt-4",
    "llm_quality_review": str | None,
    "page_bytes_base64": str
}
```

### 2. Classifier Agent
**Purpose**: Classify each page as PO, Invoice, Delivery Challan, or Unknown using keyword-based rules with optional GPT-4 fallback.

**Input**: File path and file bytes
**Output**: Classified pages list and grouped documents list
**Implementation Location**: [classifier/nodes/classify_pages.py](classifier/nodes/classify_pages.py)

**Output Structure**:
```python
# Classified Pages
{
    "page_number": int,
    "document_type": "PO" | "Invoice" | "Delivery Challan" | "Unknown",
    "confidence": float,  # 0.0-1.0
    "reason": str,
    "classification_method": "rule_based" | "gpt-4",
    "text_extraction_method": str | None,
    "ocr_used": bool,
    "ocr_error": str | None
}

# Grouped Documents
{
    "document_type": str,
    "start_page": int,
    "end_page": int,
    "pages": [int, int, ...]
}
```

### 3. Decision Node 1: Quality & Completeness
**Purpose**: Validates that all pages meet minimum quality threshold and all expected document types are present.

**Pass Criteria**:
- All pages have `quality_score >= 0.60`
- All document types (PO, Invoice, Delivery Challan) are present in the batch

**Output**:
```python
{
    "passed": bool,
    "reason": str  # Details of any failures
}
```

**If FAILED**:
- Returns `approval_required=True`
- Prompts user to reupload missing documents or retry with better quality

### 4. Extraction Agent
**Purpose**: Splits the PDF into separate documents by type and prepares for structured field extraction.

**Input**: File bytes and grouped documents list
**Output**: List of document payloads with base64-encoded bytes

**Output Structure**:
```python
{
    "document_type": str,
    "document_name": str,  # Format: "PO_001.pdf", "Invoice_001.pdf", etc.
    "document_bytes_base64": str,
    "start_page": int | None,
    "end_page": int | None
}
```

### 5. Data Normalization Agent (TODO)
**Purpose**: Normalize extracted data for consistent processing.

**Responsibilities**:
- Standardize units (e.g., kg, grams → base unit)
- Normalize vendor names (remove variations, handle aliases)
- Normalize item names (handle variations, category mapping)
- Standardize currency formats and amounts
- Date format normalization

### 6. 3-Way Matching Agent (TODO)
**Purpose**: Perform cross-document matching to validate data consistency across PO, Invoice, and Delivery Challan.

**Matching Logic**:
- Quantity matching (PO qty ≈ Invoice qty ≈ DC qty)
- Amount matching (invoice amount ≈ PO amount within tolerance)
- Vendor matching (supplier in all documents)
- Date consistency (delivery date after PO date)

### 7. Decision Node 2: Matching Validation (TODO)
**Purpose**: Validates that 3-way matching succeeded.

**Pass Criteria**:
- Quantities match within tolerance
- Amounts match within tolerance
- Vendors/dates are consistent

**If FAILED**:
- Triggers Communication Agent to raise a discrepancy issue

### 8. Communication Agent (TODO)
**Purpose**: Formulates structured JSON messages for the user interface.

**Output Types**:
- Quality issue notifications
- Missing document alerts
- Matching discrepancy details
- Required action requests

### 9. Approval Agent (TODO)
**Purpose**: Raises approval requests for final approval or intervention.

**Responsibilities**:
- Submit to approval workflow
- Track approval status
- Handle rejections/revisions

---

## API Endpoints

### 1. POST /orchestrate (Main Orchestration Endpoint)
**Purpose**: Execute the complete agentic workflow on an uploaded document.

**Request**:
```
Content-Type: multipart/form-data
file: <PDF or image file>
```

**Response**:
```json
{
    "workflow_status": "success" | "decision_1_failed" | "extraction_agent_failed" | ...,
    "quality_report": {
        "pages": [
            {"page_number": 1, "quality_score": 0.85, ...}
        ]
    },
    "classified_pages": [
        {"page_number": 1, "document_type": "PO", "confidence": 0.95, ...}
    ],
    "extracted_data": [
        {
            "document_type": "Invoice",
            "document_name": "Invoice_001",
            "extracted_fields": {...},
            "missing_fields": [...],
            "method_used": "rule_based" | "gpt-4"
        }
    ],
    "decision_1_result": {
        "passed": true,
        "reason": "All quality checks passed"
    },
    "decision_2_result": {
        "status": "TODO"
    },
    "approval_required": false,
    "message": "Orchestration completed successfully",
    "file_bytes_base64": "base64_encoded_original_file"
}
```

**Status Codes**:
- `200`: Success - full orchestration completed
- `200`: Partial Success - completed up to a decision node failure
- `400`: Bad request (empty file, invalid format)
- `500`: Server error

### 2. POST /classify-documents (Classifier Agent Only)
**Purpose**: Run only the classifier agent on an uploaded file (useful for debugging or targeted classification).

**Request**:
```
Content-Type: multipart/form-data
file: <PDF or image file>
```

**Response**:
```json
{
    "file_name": "document.pdf",
    "classified_pages": [...],
    "grouped_documents": [...],
    "documents": [...],
    "file_bytes_base64": "base64_encoded_file"
}
```

### 3. GET / (Health Check)
**Purpose**: Check API status and view available endpoints.

**Response**:
```json
{
    "status": "running",
    "message": "P2P Document Processing API is running with agentic orchestration.",
    "version": "1.0.0",
    "endpoints": {
        "orchestrate": "/orchestrate - Full agentic workflow",
        "classify_documents": "/classify-documents - Classifier agent only",
        "health": "/ - Health check"
    },
    "agentic_flow": [
        "Input File",
        "Quality Agent",
        "Classifier Agent",
        "Decision Node 1 (Quality Check)",
        "Extraction Agent",
        "Data Normalization Agent (TODO)",
        "3-Way Matching Agent (TODO)",
        "Decision Node 2 (Matching Check)",
        "Communication Agent (TODO)",
        "Approval Agent (TODO)"
    ]
}
```

---

## Implementation Details

### Agent Functions in [main.py](main.py)

1. **quality_agent(file_path, file_name)**
   - Reads file and calls evaluate_document()
   - Returns: (quality_pages, status)

2. **classifier_agent(file_path, file_name)**
   - Builds initial state with file path
   - Runs validation, text extraction, classification, grouping nodes
   - Returns: (classified_pages, grouped_documents, status)

3. **merge_quality_and_classifier_data(quality_pages, classified_pages)**
   - Merges outputs by page number
   - Creates MergedPageData objects combining both metrics
   - Returns: List of merged page data

4. **decision_node_1(merged_pages, quality_threshold=0.60)**
   - Checks quality_score >= threshold for all pages
   - Validates presence of all expected document types
   - Returns: (passed: bool, reason: str)

5. **extraction_agent(file_path, grouped_documents, file_bytes)**
   - Splits PDF using grouped_documents
   - Returns: (documents, status)

6. **normalization_agent(extracted_data)** (TODO)
7. **matching_agent(extracted_data)** (TODO)
8. **communication_agent(discrepancy_details)** (TODO)
9. **approval_agent(approval_data)** (TODO)

### State Models in [main.py](main.py)

- **AgentState**: Internal state object tracking data flow through agents
- **MergedPageData**: Combined page-level quality + classification data
- **OrchestrationResponse**: Final API response model

---

## Error Handling & Fallbacks

1. **Quality Agent Failure**:
   - Returns error status to user
   - Suggests document re-upload

2. **Classifier Agent Failure**:
   - Returns error status to user
   - Logs which node failed (validation, extraction, classification, grouping)

3. **Decision Node 1 Failure**:
   - Returns with `approval_required=True`
   - Provides detailed reasons for rejection
   - Suggests actions: reupload, improve quality, add missing docs

4. **Extraction Agent Failure**:
   - Returns error to user
   - Logs which document caused failure

5. **LLM Integration** (Optional via OpenAI):
   - Quality Agent can use GPT-4 for quality review if enabled
   - Classifier Agent can use GPT-4 for ambiguous classifications if enabled
   - Falls back to rule-based if OpenAI not configured or API fails

---

## Instrumentation & Debugging

All agents and nodes include print statements for execution tracing:

```python
print("orchestration: agent_name invoked")
print("orchestration: agent_name completed with status=X")
print("orchestration: decision_node_X result: passed=Y, reason=Z")
```

These are visible in server logs for debugging end-to-end flow.

---

## Configuration

**Environment Variables**:
- `QUALITY_UPLOAD_FOLDER`: Directory for uploaded files during quality check
- `CLASSIFIER_UPLOAD_FOLDER`: Directory for uploaded files during classification
- `CLASSIFIER_OUTPUT_FOLDER`: Directory for output documents after splitting
- `OPENAI_API_KEY`, `AZURE_OPENAI_ENDPOINT`, etc.: For optional LLM integration

**Quality Threshold**:
- Default: 0.60 (60%)
- Configurable in decision_node_1() call

**Document Types Expected**:
- PO (Purchase Order)
- Invoice
- Delivery Challan (DC)

---

## Future Enhancements

1. **Parallel Agent Execution**: Run Quality and Classifier agents in parallel instead of sequentially
2. **Agent Timeout Handling**: Set timeouts for long-running agents
3. **Async Agent Chains**: Enable callback-based agent orchestration
4. **Dynamic Workflow**: Route based on document content (e.g., skip Matching for single-document batches)
5. **Agent Logging**: Structured logging with correlation IDs for full audit trails
6. **Performance Metrics**: Track agent execution times and success rates
7. **Human-in-Loop UI**: Web interface for Decision Node 1/2 approvals

---

## Testing

### Test Orchestration Flow with Sample PDF
```bash
curl -X POST "http://localhost:8000/orchestrate" \
  -F "file=@sample_documents.pdf"
```

### Test Classifier Only
```bash
curl -X POST "http://localhost:8000/classify-documents" \
  -F "file=@sample_documents.pdf"
```

### Check Health
```bash
curl -X GET "http://localhost:8000/"
```

---

## Integration with External Systems

### Expected Integration Points

1. **Decision Node 1 Failure** → User Interface
   - Display: "Please upload missing documents" or "Please retry with better quality"
   - Action: User uploads replacement file → Restart orchestration

2. **Decision Node 2 Failure** → Communication Agent
   - Formulate discrepancy message
   - Forward to appropriate stakeholder for resolution

3. **Approval** → Approval Agent
   - Integrate with approval workflow (e.g., SAP, Oracle, custom approval system)
   - Track approval status and respond accordingly

---

## References

- Quality Agent: [quality_checks.py](quality_checks.py)
- Classifier Agent: [classifier/nodes/](classifier/nodes/)
- Data Extraction: [input_handler.py](input_handler.py)
- Main Orchestration: [main.py](main.py)
- Schemas: [schemas.py](schemas.py)
