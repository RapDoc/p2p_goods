# Document Quality Evaluation Microservice

A FastAPI-based microservice that evaluates the quality and compliance of document uploads (images and PDFs) using image processing and OCR.

## Overview

This microservice provides a REST API endpoint to analyze documents for visual clarity, text extractability, and compliance. It supports common image and PDF document formats and evaluates quality consistently across all document types.
## Features

- Multi-format support: Accept JPEG, PNG, and PDF documents
- Multi-page support: Process PDF files with per-page quality evaluation
- Comprehensive quality evaluation: Checks clarity, orientation, resolution, and content coverage
- OCR-powered text extraction with confidence scoring
- Universal quality schemas: Consistent evaluation across all document types
- Compliance scoring with detailed reasoning
- Robust error handling for invalid files and processing failures

## API Endpoint

### POST /evaluate-quality

Evaluates the quality of an uploaded document.

Parameters:

- `file` (form field, file): Document file in JPEG, PNG, or PDF format

Response model:

```json
{
  "pages": [
    {
      "page_number": 1,
      "quality_score": 0.60,
      "is_compliant": true,
      "reasons": [],
      "flowback_status": null,
      "schema_version": "1.0",
      "quality_checks": {
        "Page Blurriness": "NO",
        "Page Rotation": "NO",
        "OCR Confidence Score": "85.5%",
        "Resolution/DPI Validation": "YES",
        "Crop Cutoff / margins": "NO",
        "Clarity Rating": "EXCELLENT",
        "Blank page": "NO",
        "Content Coverage": "GOOD"
      }
    }
  ]
}
```

For multi-page PDFs, the `pages` array will contain one result per page with the appropriate `page_number`.

## Project Structure

```
Quality_Agent/
main.py
quality_checks.py
document_quality_schema.py
schemas.py
image_utils.py
text_utils.py
requirements.txt
```

## Quick start

```bash
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn main:app --reload
```
