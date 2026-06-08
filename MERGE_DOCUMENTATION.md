# P2P Goods - Merged Component Documentation

## Overview

The p2p_goods project has been successfully restructured to merge three separate FastAPI microservices into a unified single application. All endpoints are now accessible from a single `main.py` entry point in the root directory.

## Merged Components

### Component 1: Quality Evaluation (Original Root)
- **Endpoints**: `/evaluate-quality`, `/extract-fields`
- **Purpose**: Document quality assessment and field extraction
- **Dependencies**: `quality_checks`, `input_handler`, `schemas`

### Component 2: Document Classification & Extraction (ClassifierAndExtract/src)
- **Endpoints**: `/classify-and-split`, `/debug-extract-text`
- **Purpose**: Multi-document classification, splitting, and structured data extraction
- **Dependencies**: LangGraph workflow with multiple processing nodes

### Component 3: Health Check
- **Endpoint**: `/`
- **Purpose**: API health status and configuration overview

---

## New Project Structure

```
p2p_goods/
├── main.py                          # ✅ MERGED entry point (all 5 endpoints)
├── classifier/                      # ✅ NEW package (from ClassifierAndExtract/src)
│   ├── __init__.py
│   ├── state.py                     # DocumentAgentState definition
│   ├── graph.py                     # LangGraph workflow builder
│   └── nodes/                       # Processing pipeline nodes
│       ├── __init__.py
│       ├── validate_input.py
│       ├── extract_text.py
│       ├── classify_pages.py
│       ├── group_pages.py
│       ├── split_documents.py
│       ├── data_extraction.py       # Invoice/PO/DC field extraction
│       ├── error_handler.py
│       ├── generate_response.py
│       └── ocr_utils.py             # EasyOCR integration
│
├── quality_checks.py                # ✅ UNCHANGED
├── input_handler.py                 # ✅ UNCHANGED
├── schemas.py                       # ✅ UNCHANGED
├── extractors.py                    # ✅ UNCHANGED
├── image_utils.py                   # ✅ UNCHANGED
├── text_utils.py                    # ✅ UNCHANGED
├── ocr_utils.py                     # ✅ UNCHANGED
├── document_quality_schema.py        # ✅ UNCHANGED
│
├── data/                            # ✅ NEW folder structure
│   ├── uploads/
│   │   ├── quality_checks/         # Quality evaluation uploads
│   │   └── classifier/             # Classification uploads
│   └── Processed_docs/             # Classifier output
│
├── requirements.txt                 # ✅ UPDATED (combined deps)
├── ClassifierAndExtract/            # ⚠️ DEPRECATED (use classifier/ instead)
└── ...
```

---

## Unified API Endpoints

### Quality Evaluation Group

#### 1. `/evaluate-quality` (POST)
Evaluates document quality metrics including blurriness, contrast, resolution, and OCR confidence.

**Request**: `multipart/form-data` with file

**Response**:
```json
{
  "pages": [
    {
      "page_number": 1,
      "quality_score": 0.92,
      "is_compliant": true,
      "reasons": [],
      "quality_checks": {
        "page_blurriness": "PASS",
        "page_rotation": "PASS",
        "ocr_confidence_score": "PASS",
        ...
      }
    }
  ]
}
```

#### 2. `/extract-fields` (POST)
Extracts structured fields from documents (Invoice, PO, Delivery Challan).

**Request**: `multipart/form-data` with `document_type` and file

**Response**:
```json
{
  "document_type": "Invoice",
  "extracted_fields": {
    "invoice_number": "INV-2024-001",
    "invoice_date": "2024-01-15",
    ...
  },
  "missing_fields": [],
  "required_fields": ["invoice_number", "invoice_date", ...],
  "pages_count": 1
}
```

### Classification & Extraction Group

#### 3. `/classify-and-split` (POST)
Processes mixed document PDFs through complete workflow: classification → splitting → extraction.

**Request**: `multipart/form-data` with PDF file

**Response**:
```json
{
  "status": "success",
  "total_pages": 10,
  "classified_pages": [
    {
      "page_number": 1,
      "document_type": "Invoice",
      "confidence": 0.95,
      "reason": "Scores: PO=0, Delivery Challan=2, Invoice=8."
    }
  ],
  "extracted_documents": [
    {
      "document_type": "Invoice",
      "document_name": "Invoice_001.pdf",
      "document_path": "data/Processed_docs/Invoice_001.pdf",
      "start_page": 1,
      "end_page": 2
    }
  ],
  "extracted_data": [
    {
      "document_type": "Invoice",
      "document_name": "Invoice_001.pdf",
      "status": "success",
      "header_fields": {
        "invoice_number": "INV-2024-001",
        "total_amount": "50000.00"
      },
      "line_items": [...]
    }
  ]
}
```

#### 4. `/debug-extract-text` (POST)
Debug endpoint for troubleshooting text extraction (pypdf + EasyOCR).

**Request**: `multipart/form-data` with PDF file

**Response**:
```json
{
  "status": "text_extracted",
  "total_pages": 5,
  "pages": [
    {
      "page_number": 1,
      "text_extraction_method": "pypdf",
      "ocr_used": false,
      "ocr_error": null,
      "text_preview": "Invoice No. INV-2024-001..."
    }
  ]
}
```

### Health & Status

#### 5. `/` (GET)
Health check endpoint with configuration details.

**Response**:
```json
{
  "status": "running",
  "message": "P2P Document Processing API is running.",
  "version": "1.0.0",
  "endpoints": {...},
  "folder_config": {
    "quality_uploads": "data/uploads/quality_checks",
    "classifier_uploads": "data/uploads/classifier",
    "classifier_output": "data/Processed_docs"
  }
}
```

---

## Key Changes & Improvements

### ✅ What Changed

1. **Single Entry Point**: All functionality now accessible from root `main.py`
2. **Organized Package Structure**: 
   - Classifier logic moved to `classifier/` package
   - Relative imports updated to work from root context
3. **Folder Organization**: 
   - Uploads separated by purpose: `data/uploads/quality_checks` and `data/uploads/classifier`
   - Processing output in `data/Processed_docs`
4. **Import Paths**: 
   - `from classifier.graph import build_document_classification_graph()`
   - `from classifier.nodes.extract_text import extract_text_node`
5. **Environment Configuration**: 
   - Folder paths configurable via environment variables
   - Unified app configuration

### ✅ What Stayed the Same

- All original functionality preserved
- All quality check logic unchanged
- All extraction logic unchanged
- Backward compatible response formats

---

## Running the Application

### Prerequisites
```bash
pip install -r requirements.txt
```

### Start the Server
```bash
python main.py
```

Server runs on `http://0.0.0.0:8000`

### Access API Documentation
- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`

---

## Environment Configuration

Configure behavior via environment variables:

```env
# App Configuration
APP_TITLE=P2P Document Processing API
APP_DESCRIPTION=Comprehensive document processing...
APP_VERSION=1.0.0

# Folder Configuration
QUALITY_UPLOAD_FOLDER=data/uploads/quality_checks
CLASSIFIER_UPLOAD_FOLDER=data/uploads/classifier
CLASSIFIER_OUTPUT_FOLDER=data/Processed_docs

# OCR Configuration (classifier)
ENABLE_OCR=True
OCR_LANGUAGE=en
OCR_DPI=300
EASYOCR_GPU=False
OCR_MIN_TEXT_LENGTH=30
```

---

## File Reference Map

### Quality Evaluation Pipeline
- `quality_checks.py` → `evaluate_single_page()` → `/evaluate-quality`
- `input_handler.py` → `process_document()` → `/extract-fields`
- `extractors.py` → Field extraction logic
- `text_utils.py`, `image_utils.py` → Support utilities

### Classification & Extraction Pipeline
- `classifier/graph.py` → `build_document_classification_graph()`
- `classifier/state.py` → `DocumentAgentState` (LangGraph state)
- `classifier/nodes/` → Individual processing steps:
  - `validate_input.py` → File validation
  - `extract_text.py` → pypdf + EasyOCR
  - `classify_pages.py` → Document type classification
  - `group_pages.py` → Group pages by type
  - `split_documents.py` → Extract individual PDFs
  - `data_extraction.py` → Extract structured fields
  - `generate_response.py` → Format response
  - `error_handler.py` → Error handling

---

## Migration Guide (from old structure)

### Old Structure
```
├── main.py (root) → /evaluate-quality, /extract-fields
├── ClassifierAndExtract/src/main.py → /classify-and-split, /debug-extract-text
```

### New Structure
```
├── main.py (root) → ALL 5 endpoints
├── classifier/ → All classification logic
```

### No Breaking Changes
- Same endpoint paths
- Same request/response formats
- Drop-in replacement for both services

---

## Support & Troubleshooting

### OCR Issues
If EasyOCR is slow or fails:
1. Ensure ENABLE_OCR is set correctly
2. Check OCR_GPU setting (requires CUDA for GPU support)
3. Verify OCR_LANGUAGE matches your documents
4. Use `/debug-extract-text` endpoint to diagnose

### Import Errors
Ensure classifier package is importable:
```bash
python -c "from classifier.graph import build_document_classification_graph; print('OK')"
```

### Folder Permissions
Ensure write permissions for:
- `data/uploads/quality_checks/`
- `data/uploads/classifier/`
- `data/Processed_docs/`

---

## Version Info

- **Merge Date**: 2024-06-07
- **Python Version**: 3.8+
- **FastAPI**: >=0.95.0
- **LangGraph**: Latest
- **PyPDF**: Latest
- **EasyOCR**: >=1.7.0
