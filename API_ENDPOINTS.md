# API Endpoints Quick Reference

## 🚀 Running the API

```bash
cd /path/to/p2p_goods
python main.py
```

API runs on: `http://localhost:8000`

---

## 📋 All Endpoints (5 Total)

### 1. Health Check
```
GET /
```
Returns API status and configuration.

---

### 2. Quality Evaluation
```
POST /evaluate-quality
Content-Type: multipart/form-data
Param: file (image/PDF)
```
Evaluates document quality metrics.

---

### 3. Field Extraction
```
POST /extract-fields
Content-Type: multipart/form-data
Param: document_type (Invoice|PO|Delivery Challan)
Param: file (PDF)
```
Extracts structured fields from documents.

---

### 4. Classify & Split
```
POST /classify-and-split
Content-Type: multipart/form-data
Param: file (PDF with mixed documents)
```
Full pipeline: classify → split → extract

---

### 5. Debug Text Extraction
```
POST /debug-extract-text
Content-Type: multipart/form-data
Param: file (PDF)
```
Troubleshoot text extraction issues.

---

## 📚 API Documentation

- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`

---

## 🔧 Quick Test with cURL

### Health Check
```bash
curl http://localhost:8000/
```

### Evaluate Quality
```bash
curl -X POST http://localhost:8000/evaluate-quality \
  -F "file=@document.pdf"
```

### Extract Fields
```bash
curl -X POST http://localhost:8000/extract-fields \
  -F "document_type=Invoice" \
  -F "file=@invoice.pdf"
```

### Classify & Split
```bash
curl -X POST http://localhost:8000/classify-and-split \
  -F "file=@mixed_documents.pdf"
```

### Debug Extract Text
```bash
curl -X POST http://localhost:8000/debug-extract-text \
  -F "file=@document.pdf"
```

---

## 📁 Folder Structure

```
data/
├── uploads/
│   ├── quality_checks/      # Quality evaluation uploads
│   └── classifier/          # Classification uploads
└── Processed_docs/          # Output documents
```

---

## 🎯 Response Status Codes

- **200**: Success
- **400**: Invalid request (empty file, unsupported type)
- **500**: Processing error

---

## 🔑 Environment Variables

```env
APP_TITLE=P2P Document Processing API
APP_VERSION=1.0.0
QUALITY_UPLOAD_FOLDER=data/uploads/quality_checks
CLASSIFIER_UPLOAD_FOLDER=data/uploads/classifier
CLASSIFIER_OUTPUT_FOLDER=data/Processed_docs
ENABLE_OCR=True
OCR_DPI=300
```

---

## ✅ Supported Document Types

- **Invoice** - Tax invoices, GST invoices
- **PO** - Purchase Orders
- **Delivery Challan** - Delivery notes, challan documents

---

## 📊 Document Type Keywords

The classifier uses keyword matching:

**Invoice**: invoice, tax invoice, invoice no, IRN, CGST, SGST, IGST
**PO**: purchase order, PO number, vendor, payment terms, ordered
**DC**: delivery challan, challan no, vehicle no, e-way bill, dispatch

---

## 🐛 Troubleshooting

### OCR Not Working
- Check ENABLE_OCR=True
- Verify EasyOCR is installed
- Check GPU settings if using CUDA

### Import Errors
```bash
python -c "from classifier.graph import build_document_classification_graph"
```

### Folder Permissions
Ensure write access to `data/uploads/` and `data/Processed_docs/`

---

## 📞 Support

For issues, check:
1. API logs (printed to console)
2. Response error messages
3. Use `/debug-extract-text` for extraction issues
4. Check `MERGE_DOCUMENTATION.md` for detailed info
