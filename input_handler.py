import base64
from typing import Dict, Any
from ocr_utils import extract_text_from_file
from openai_utils import is_azure_openai_enabled, query_openai_structured
from extractors import extract_fields_for_document, MANDATORY_FIELDS

print("input_handler: module loaded")


def process_document(file_bytes: bytes, filename: str, document_type: str) -> Dict[str, Any]:
    print(f"input_handler: process_document called for {filename} type={document_type}")
    data = extract_text_from_file(file_bytes, filename)
    pages = data.get("pages", [])
    tables = data.get("tables", [])

    fields, missing = extract_fields_for_document(document_type, pages, tables)
    method_used = "rule_based"

    if is_azure_openai_enabled() and missing:
        try:
            print("input_handler: invoking OpenAI extraction fallback")
            prompt = (
                "Extract structured fields for a document of type "
                f"{document_type}. "
                "Use the provided page text and table records. If a field is unavailable, return an empty string."
                "Document text pages:\n"
            )
            for page_num, page_text in enumerate(pages, start=1):
                prompt += f"Page {page_num}: {page_text}\n"

            prompt += "\nTables:\n"
            for page_tables in tables:
                prompt += f"{page_tables}\n"

            # prompt += "\nRespond with valid JSON only."

            extraction_result = query_openai_structured(prompt, document_type=document_type)
            fields = extraction_result.model_dump()
            # fields = extraction_result.get("extracted_fields", fields)
            # missing = extraction_result.get("missing_fields", missing)
            # required = extraction_result.get("required_fields", required)
            method_used = "gpt-4"
        except Exception as exc:
            print(f"input_handler: OpenAI extraction fallback failed: {exc}")
            method_used = "rule_based"

    # required = MANDATORY_FIELDS.get(document_type.lower().replace(" ", "_"), required)

    response = {
        "document_type": document_type,
        # "extracted_fields": fields,
        # "missing_fields": missing,
        # "required_fields": required,
        "fields": fields,
        "pages_count": len(pages),
        "method_used": method_used,
        "page_bytes_base64": base64.b64encode(file_bytes).decode("utf-8"),
    }
    return response
