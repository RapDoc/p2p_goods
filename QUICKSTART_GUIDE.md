# Quick Start Guide - Agentic Orchestration API

## Overview
The P2P Document Processing API now features a complete agentic orchestration system that automatically processes documents through multiple specialized agents with intelligent decision nodes and human-in-the-loop checkpoints.

---

## Quick Start

### 1. Start the API Server

```bash
cd c:\Users\WD254XR\OneDrive - EY\Desktop\Agentic\p2p_goods
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Expected output:
```
INFO:     Uvicorn running on http://0.0.0.0:8000
INFO:     Application startup complete
```

### 2. Access the API

- **Interactive Docs**: http://localhost:8000/docs
- **ReDoc Documentation**: http://localhost:8000/redoc
- **Health Check**: http://localhost:8000/

---

## Usage Examples

### Option A: Full Orchestration Workflow (Recommended)

**Process a complete document batch through all agents**:

```bash
curl -X POST "http://localhost:8000/orchestrate" \
  -F "file=@/path/to/document.pdf" \
  -H "accept: application/json"
```

**Response Example**:
```json
{
  "workflow_status": "success",
  "quality_report": {
    "pages": [
      {
        "page_number": 1,
        "quality_score": 0.85,
        "is_compliant": true,
        "analysis_method": "rule_based",
        "page_bytes_base64": "..."
      }
    ]
  },
  "classified_pages": [
    {
      "page_number": 1,
      "document_type": "PO",
      "confidence": 0.95,
      "classification_method": "rule_based"
    }
  ],
  "extracted_data": [
    {
      "document_type": "PO",
      "document_name": "PO_001",
      "extracted_fields": {
        "po_number": "PO-2024-001",
        "date": "2024-01-15",
        "vendor": "Acme Corp"
      },
      "missing_fields": [],
      "method_used": "rule_based"
    }
  ],
  "decision_1_result": {
    "passed": true,
    "reason": "All quality checks passed"
  },
  "approval_required": false,
  "message": "Orchestration completed successfully"
}
```

**Response Status Codes**:
- `200 - Success`: Full workflow completed
- `200 - Partial Success`: Workflow stopped at a decision node
- `400 - Bad Request`: Invalid file or empty upload
- `500 - Server Error`: Processing error

---

### Option B: Classification Only (Debugging)

**Test only the classifier agent**:

```bash
curl -X POST "http://localhost:8000/classify-documents" \
  -F "file=@/path/to/document.pdf" \
  -H "accept: application/json"
```

**Response Example**:
```json
{
  "file_name": "document.pdf",
  "classified_pages": [
    {
      "page_number": 1,
      "document_type": "PO",
      "confidence": 0.95,
      "classification_method": "rule_based"
    }
  ],
  "grouped_documents": [
    {
      "document_type": "PO",
      "start_page": 1,
      "end_page": 2,
      "pages": [1, 2]
    }
  ],
  "documents": [
    {
      "document_type": "PO",
      "document_name": "PO_001.pdf",
      "document_bytes_base64": "..."
    }
  ],
  "file_bytes_base64": "..."
}
```

---

### Option C: Health Check

**Check API status and available endpoints**:

```bash
curl -X GET "http://localhost:8000/"
```

**Response**:
```json
{
  "status": "running",
  "message": "P2P Document Processing API is running with agentic orchestration.",
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

## Understanding the Workflow

### Step-by-Step Flow

1. **File Upload** → Validate file is not empty

2. **Quality Agent** → Evaluates page-wise quality metrics
   - Page blurriness, rotation, resolution
   - OCR confidence
   - Content coverage
   - Returns quality_score (0.0-1.0) for each page

3. **Classifier Agent** → Classifies pages by document type
   - Identifies document types: PO, Invoice, Delivery Challan, Unknown
   - Groups consecutive pages of same type
   - Returns confidence score (0.0-1.0) for each classification

4. **Merge Data** → Combines quality + classification metrics by page number

5. **Decision Node 1: Quality & Completeness Check**
   - ✓ PASS if: all quality_scores >= 0.60 AND all expected document types present
   - ✗ FAIL if: any page quality < 0.60 OR missing document types
   - If FAIL: Returns `approval_required=True` with detailed reasons

6. **Extraction Agent** (if Decision 1 passed)
   - Splits PDF into separate documents by type
   - Prepares for structured field extraction

7. **Field Extraction**
   - Extracts: Invoice numbers, dates, amounts, vendor info, line items
   - Extracts: PO numbers, dates, items, quantities
   - Extracts: Delivery Challan details
   - Tracks method_used: "rule_based" or "gpt-4" (if LLM enabled)

8. **Data Normalization Agent** (TODO)
   - Standardize units, vendor names, currencies
   - Format normalization

9. **3-Way Matching Agent** (TODO)
   - Validate PO ↔ Invoice ↔ Delivery Challan consistency
   - Check quantities, amounts, dates

10. **Decision Node 2: Matching Validation** (TODO)
    - ✓ PASS if: All documents match within tolerance
    - ✗ FAIL if: Mismatches detected
    - If FAIL: Triggers Communication Agent

11. **Final Response** → Return results to client

---

## Handling Decision Node Failures

### Decision Node 1 Failure (Quality or Completeness)

**Response Format**:
```json
{
  "workflow_status": "decision_1_failed",
  "decision_1_result": {
    "passed": false,
    "reason": "Page 1: quality 0.45 below threshold; Missing document types: Invoice"
  },
  "approval_required": true,
  "message": "Quality checks failed. Page 1: quality 0.45 below threshold; Missing document types: Invoice"
}
```

**User Actions**:
1. Reupload missing documents (e.g., Invoice)
2. Retry with higher-quality scans
3. Skip low-quality pages if allowed by business logic

---

## Configuration

### Environment Variables

Create a `.env` file in the project root:

```bash
# Folder Configuration
QUALITY_UPLOAD_FOLDER=data/uploads/quality_checks
CLASSIFIER_UPLOAD_FOLDER=data/uploads/classifier
CLASSIFIER_OUTPUT_FOLDER=data/Processed_docs

# Optional: Azure OpenAI for LLM Fallback
OPENAI_API_TYPE=azure
AZURE_OPENAI_API_KEY=your-api-key
AZURE_OPENAI_ENDPOINT=https://your-instance.openai.azure.com/
OPENAI_API_VERSION=2024-05-01-preview
AZURE_OPENAI_DEPLOYMENT=gpt-4

# App Configuration
APP_TITLE=P2P Document Processing API
APP_VERSION=1.0.0
```

### Quality Threshold

The default quality threshold is **0.60 (60%)**. To change it, modify this line in [main.py](main.py):

```python
decision_1_passed, decision_1_reason = decision_node_1(merged_pages, quality_threshold=0.70)  # Change to 0.70 for 70%
```

---

## Understanding Response Fields

### OrchestrationResponse Fields

| Field | Type | Description |
|-------|------|-------------|
| `workflow_status` | string | Final status: "success", "decision_1_failed", "extraction_agent_failed", etc. |
| `quality_report` | object | Page-wise quality metrics from Quality Agent |
| `classified_pages` | array | Page classifications from Classifier Agent |
| `extracted_data` | array | Structured field extractions |
| `decision_1_result` | object | Decision Node 1 validation result: {passed, reason} |
| `decision_2_result` | object | Decision Node 2 result (TODO implementation) |
| `approval_required` | boolean | True if manual approval needed (e.g., Decision 1 failed) |
| `message` | string | Human-readable summary |
| `file_bytes_base64` | string | Original file bytes encoded in base64 |

---

## Logging & Debugging

All agents print invocation and status information to stdout:

```
orchestration: quality_agent invoked for document.pdf
orchestration: quality_agent completed with status=success
orchestration: classifier_agent invoked for document.pdf
orchestration: classifier_agent completed with status=success
orchestration: merging quality and classifier data
orchestration: decision_node_1 checking 5 pages with threshold 0.60
orchestration: decision_node_1 result: passed=True, reason=All quality checks passed
orchestration: extraction_agent invoked
```

**Monitor logs**:
```bash
# Watch server logs for real-time debugging
tail -f server.log
```

---

## Advanced Usage

### Handling Partial Results

If the workflow stops at Decision Node 1:

```python
response = requests.post(
    "http://localhost:8000/orchestrate",
    files={"file": open("document.pdf", "rb")}
).json()

if response["approval_required"]:
    print(f"Approval needed: {response['decision_1_result']['reason']}")
    # Handle user interaction / reupload
else:
    # Process extracted_data
    for doc in response["extracted_data"]:
        print(f"{doc['document_type']}: {doc['extracted_fields']}")
```

### Using Classifier Independently

If you only need classification (e.g., document routing):

```python
response = requests.post(
    "http://localhost:8000/classify-documents",
    files={"file": open("document.pdf", "rb")}
).json()

for page in response["classified_pages"]:
    print(f"Page {page['page_number']}: {page['document_type']} (confidence: {page['confidence']})")
```

---

## Performance Notes

- **Quality Agent**: ~2-5 seconds per document (depending on page count and OCR usage)
- **Classifier Agent**: ~3-8 seconds per document (text extraction + classification)
- **Total Orchestration**: ~5-15 seconds for a typical 3-4 page multi-document batch

Enable optional LLM for fallback to GPT-4 classification/quality review if rule-based accuracy is insufficient.

---

## Troubleshooting

### "Empty file uploaded"
```
Response: 400 Bad Request - Uploaded file is empty
Solution: Ensure your file upload includes actual content
```

### "Quality Agent failed"
```
Response: workflow_status = "quality_agent_failed"
Message: Explains which quality check failed
Solution: Verify PDF is readable and has content
```

### "Decision 1 failed - quality below threshold"
```
Response: workflow_status = "decision_1_failed", approval_required = True
Solution: Reupload with higher-quality scan or provide missing documents
```

### OpenAI Integration Not Working
```
If OPENAI_API_KEY not set, system falls back to rule-based classification/quality
This is normal and expected - no action required
```

---

## API Documentation

For interactive API documentation:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

Both provide:
- Endpoint descriptions
- Request/response schemas
- Try-it-out functionality

---

## File Locations

| Component | Location |
|-----------|----------|
| Main API | [main.py](main.py) |
| Agentic Flow Docs | [AGENTIC_FLOW_DOCUMENTATION.md](AGENTIC_FLOW_DOCUMENTATION.md) |
| Quality Agent | [quality_checks.py](quality_checks.py) |
| Classifier Agent | [classifier/nodes/classify_pages.py](classifier/nodes/classify_pages.py) |
| Extraction Agent | [input_handler.py](input_handler.py) |
| Data Models | [schemas.py](schemas.py) |
| Workflow Orchestration | [classifier/graph.py](classifier/graph.py) |

---

## Next Steps

### For Developers
1. Implement Data Normalization Agent for unit/vendor standardization
2. Implement 3-Way Matching Agent for PO-Invoice-DC validation
3. Implement Communication Agent for discrepancy messaging
4. Add parallel agent execution for performance
5. Create web UI for Decision Node approvals

### For Integration
1. Connect Decision Node 1 failures to UI for user reupload handling
2. Connect Decision Node 2 failures to communication workflow
3. Integrate Approval Agent with your approval system (SAP, Oracle, etc.)
4. Set up monitoring and alerting for agent failures
5. Configure LLM integration with appropriate API keys

---

## Support

For issues or questions:
1. Check server logs for detailed error messages
2. Review AGENTIC_FLOW_DOCUMENTATION.md for architecture details
3. Test individual agents via /classify-documents endpoint
4. Verify environment variables are set correctly
5. Check that input files are valid PDFs or images

---

## Version History

- **v1.0.0** (Current): Full agentic orchestration with Decision Node 1 implementation
- **v0.9.0**: Azure OpenAI integration with fallback to rule-based
- **v0.8.0**: Initial 3-endpoint architecture

---

Last Updated: 2024
