# Architecture & Integration Guide

## System Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                     p2p_goods Main API                          │
│                    (main.py - Root Level)                       │
└─────────────────────────────────────────────────────────────────┘
                              ▼
                    ┌─────────────────┐
                    │  CORS Enabled   │
                    │  FastAPI App    │
                    └─────────────────┘
                              ▼
                    ┌─────────────────────────────────┐
                    │    5 Unified Endpoints          │
                    ├─────────────────────────────────┤
                    │ ├─ GET  /                       │
                    │ ├─ POST /evaluate-quality       │
                    │ ├─ POST /extract-fields         │
                    │ ├─ POST /classify-and-split     │
                    │ └─ POST /debug-extract-text     │
                    └─────────────────────────────────┘
                         ▼          ▼
            ┌──────────────┐      ┌──────────────────┐
            │   Quality    │      │   Classifier &   │
            │  Evaluation  │      │    Extraction    │
            │   Pipeline   │      │    Pipeline      │
            └──────────────┘      └──────────────────┘
                 ▼                        ▼
        ┌────────────────┐      ┌──────────────────────┐
        │ quality_checks │      │  classifier/         │
        │ input_handler  │      │  ├── graph.py        │
        │ extractors     │      │  ├── state.py        │
        │ schemas        │      │  └── nodes/          │
        └────────────────┘      │      ├── validate    │
                                │      ├── extract     │
                                │      ├── classify    │
                                │      ├── group       │
                                │      ├── split       │
                                │      ├── extract_data│
                                │      ├── generate    │
                                │      └── error       │
                                └──────────────────────┘
```

---

## Data Flow Diagrams

### Quality Evaluation Pipeline

```
File Upload
    ▼
validate_empty() 
    ▼
evaluate_document() ───► quality_checks.py
    │                   (for each page)
    ├─► image_utils.py ──┐
    ├─► text_utils.py ───┤
    └─► ocr_utils.py ────┤
                         ▼
                  Calculate Scores
                  (blur, contrast, 
                   resolution, etc.)
                         ▼
                   QualityChecks
                      Schema
                         ▼
                  DocumentQualityResponse
                         ▼
                      Client
```

### Field Extraction Pipeline

```
File Upload + Document Type
         ▼
  ocr_utils.extract_text_from_file()
         ▼
  ┌──────────────────────┐
  │ Extract Text & Tables│
  └──────────────────────┘
         ▼
  ┌──────────────────────────────────────┐
  │ extract_fields_for_document()         │
  ├──────────────────────────────────────┤
  │ Match document type:                 │
  │ • Invoice → invoice patterns         │
  │ • PO → purchase order patterns       │
  │ • DC → delivery challan patterns     │
  └──────────────────────────────────────┘
         ▼
  ┌──────────────────────┐
  │ Build Response with: │
  │ • extracted_fields   │
  │ • missing_fields     │
  │ • required_fields    │
  │ • pages_count        │
  └──────────────────────┘
         ▼
      Client
```

### Classification & Extraction Pipeline (LangGraph)

```
Upload File
    ▼
┌──────────────────────┐
│ validate_input_node  │  ✓ File exists? ✓ PDF?
└──────────────────────┘
         ▼
┌──────────────────────┐
│ extract_text_node    │  pypdf + EasyOCR fallback
└──────────────────────┘
         ▼
┌──────────────────────┐
│ classify_pages_node  │  Keyword matching → Type
└──────────────────────┘
         ▼
┌──────────────────────┐
│ group_pages_node     │  Group consecutive pages
└──────────────────────┘
         ▼
┌──────────────────────┐
│ split_documents_node │  Extract individual PDFs
└──────────────────────┘
         ▼
┌──────────────────────┐
│data_extraction_node  │  Extract fields per type
└──────────────────────┘
         ▼
┌──────────────────────┐
│generate_response_node│  Format & validate
└──────────────────────┘
         ▼
    Client Response
```

---

## Component Integration Points

### 1. Root ↔ Classifier Integration

**File**: `main.py`
```python
from classifier.graph import build_document_classification_graph

# Initialize LangGraph workflow
document_graph = build_document_classification_graph()

# In endpoint handler
final_state = document_graph.invoke(initial_state)
```

### 2. Node-to-Node Communication

**Pattern**: LangGraph StateDict
```python
# Each node receives full state
def node_handler(state: DocumentAgentState) -> DocumentAgentState:
    # Read from state
    input_path = state["input_file_path"]
    
    # Process
    result = do_processing(input_path)
    
    # Return updated state
    return {
        **state,
        "key": result,
        "status": "next_status"
    }
```

### 3. Conditional Routing

**Pattern**: Router functions guide workflow
```python
def route_after_extraction(state):
    if state.get("status") == "error":
        return "error_node"
    return "classify_pages_node"

workflow.add_conditional_edges(
    "extract_text_node",
    route_after_extraction,
    {
        "classify_pages_node": "classify_pages_node",
        "error_node": "error_node"
    }
)
```

---

## Module Dependencies

### Quality Evaluation Chain
```
main.py
  ├─► quality_checks.py
  │   ├─► image_utils.py
  │   ├─► text_utils.py
  │   └─► ocr_utils.py (root level)
  │
  ├─► input_handler.py
  │   ├─► ocr_utils.py
  │   └─► extractors.py
  │
  ├─► schemas.py
  │   └─► document_quality_schema.py
  │
  └─► document_quality_schema.py
```

### Classification Chain
```
main.py
  └─► classifier/graph.py
      ├─► classifier/state.py
      │
      └─► classifier/nodes/
          ├─► validate_input.py
          │
          ├─► extract_text.py
          │   └─► ocr_utils.py (classifier)
          │
          ├─► classify_pages.py
          │
          ├─► group_pages.py
          │
          ├─► split_documents.py
          │
          ├─► data_extraction.py
          │   ├─► ocr_utils.py (classifier)
          │   └─► (regex patterns for Invoice/PO/DC)
          │
          ├─► generate_response.py
          │
          └─► error_handler.py
```

---

## Folder & File Organization

### Responsibilities by Module

```
Quality Evaluation (Original Components)
├── quality_checks.py        → Page-by-page metrics
├── image_utils.py           → Image processing
├── text_utils.py            → Text analysis
├── ocr_utils.py            → Tesseract OCR
├── extractors.py           → Field patterns
└── schemas.py              → Response schemas

Classification & Extraction (New classifier/)
├── graph.py                → LangGraph workflow
├── state.py                → State definitions
└── nodes/
    ├── validate_input.py   → Input validation
    ├── extract_text.py     → pypdf + EasyOCR
    ├── classify_pages.py   → Keyword classification
    ├── group_pages.py      → Page grouping
    ├── split_documents.py  → PDF splitting
    ├── data_extraction.py  → Structured extraction
    ├── generate_response.py → Response formatting
    └── error_handler.py    → Error flow

Utility Modules
├── document_quality_schema.py  → Quality schemas
├── input_handler.py            → Request processing
└── requirements.txt            → Dependencies
```

---

## Import Resolution

### From main.py (Root Context)

```python
# Root modules - direct imports
from quality_checks import evaluate_document
from input_handler import process_document
from schemas import DocumentQualityResponse

# Classifier package - relative imports
from classifier.graph import build_document_classification_graph
from classifier.nodes.extract_text import extract_text_node
```

### Within Classifier Package

```python
# In classifier/graph.py
from .state import DocumentAgentState  # Relative
from .nodes.validate_input import validate_input_node  # Relative

# In classifier/nodes/extract_text.py
from .ocr_utils import easyocr_page_text  # Relative
```

---

## Environment Variables Flow

```
.env file
    ▼
load_dotenv()
    ▼
┌──────────────────────────────────┐
│ main.py reads env vars           │
├──────────────────────────────────┤
│ • APP_TITLE                      │
│ • APP_VERSION                    │
│ • QUALITY_UPLOAD_FOLDER          │
│ • CLASSIFIER_UPLOAD_FOLDER       │
│ • CLASSIFIER_OUTPUT_FOLDER       │
│ • ENABLE_OCR                     │
│ • OCR_DPI                        │
│ • etc.                           │
└──────────────────────────────────┘
    ▼
Used in:
├─► FastAPI config
├─► Folder creation
├─► Classifier nodes (via dotenv)
└─► OCR configuration
```

---

## Error Handling Flow

```
Request to any endpoint
    ▼
┌──────────────────────────────┐
│ Try Processing               │
└──────────────────────────────┘
    ▼ (Success)              ▼ (Error)
 Return Result         HTTPException
                       (400/500 status)
                              ▼
                         Error Response
```

### In LangGraph Workflow

```
Any Node Error
    ▼
set state["status"] = "error"
    ▼
Router functions check status
    ▼
Route to error_node
    ▼
error_node generates error response
    ▼
Workflow ends with error state
```

---

## Scalability Considerations

### Current Design
- Single-threaded async processing
- FastAPI with uvicorn handles concurrency
- LangGraph manages internal workflow state

### Improvements for Scale
1. **Async Node Processing**: Use AsyncGraph variant
2. **Job Queue**: Add Celery/RQ for async jobs
3. **Caching**: Redis for extracted text
4. **Load Balancing**: Multiple uvicorn instances
5. **Database**: Store results instead of files

---

## Testing Endpoints

### Integration Test Sequence

```bash
# 1. Health check
curl http://localhost:8000/

# 2. Quality evaluation
curl -X POST http://localhost:8000/evaluate-quality \
  -F "file=@test_doc.pdf"

# 3. Field extraction
curl -X POST http://localhost:8000/extract-fields \
  -F "document_type=Invoice" \
  -F "file=@invoice.pdf"

# 4. Classification & Split
curl -X POST http://localhost:8000/classify-and-split \
  -F "file=@mixed_docs.pdf"

# 5. Debug extraction
curl -X POST http://localhost:8000/debug-extract-text \
  -F "file=@test_doc.pdf"
```

---

## Migration Checklist

- [x] Classifier package created
- [x] All node files migrated
- [x] Graph workflow updated
- [x] State definitions moved
- [x] Root main.py merged
- [x] Imports updated (relative)
- [x] Folder paths organized
- [x] CORS middleware configured
- [x] Error handling integrated
- [x] Documentation created

---

## Version Control Notes

**Before Merge**: Two separate services + coordination
**After Merge**: Single unified service with clear package separation

**Breaking Changes**: None - backward compatible endpoints

**Database/Storage**: Files remain in `data/` folders (no DB required yet)
