print("classifier.nodes.generate_response: module loaded")

def generate_response_node(state):
    print("classifier.nodes.generate_response: generate_response_node invoked")
    expected_documents = {"Invoice", "PO", "Delivery Challan"}

    found_documents = {
        document.get("document_type")
        for document in state.get("extracted_documents", [])
        if document.get("document_type") != "Unknown"
    }

    missing_documents = list(expected_documents - found_documents)

    incomplete_documents = []

    for item in state.get("extracted_data", []):
        validation = item.get("validation", {})

        if not validation.get("is_complete", False):
            incomplete_documents.append({
                "document_type": item.get("document_type"),
                "document_name": item.get("document_name"),
                "missing_fields": validation.get("missing_fields", [])
            })

    if state.get("status") == "error":
        final_status = "error"
    elif missing_documents:
        final_status = "partial_success"
    elif incomplete_documents:
        final_status = "success_with_missing_fields"
    else:
        final_status = "success"

    response = {
        "status": final_status,
        "message": "Document classification, splitting, and field extraction completed.",
        "input_file": state.get("input_file_name"),
        "processed_folder": state.get("output_folder"),
        "total_pages": state.get("total_pages", 0),

        "classified_pages": [
            {
                "page_number": page.get("page_number"),
                "document_type": page.get("document_type"),
                "confidence": page.get("confidence", 0.0),
                "reason": page.get("reason", "")
            }
            for page in state.get("classified_pages", [])
        ],

        "extracted_documents": [
            {
                "document_type": document.get("document_type"),
                "document_name": document.get("document_name"),
                "document_path": document.get("document_path"),
                "start_page": document.get("start_page"),
                "end_page": document.get("end_page")
            }
            for document in state.get("extracted_documents", [])
            if document.get("document_type") != "Unknown"
        ],

        "extracted_data": [
            {
                "document_type": item.get("document_type"),
                "document_name": item.get("document_name"),
                "document_path": item.get("document_path"),
                "start_page": item.get("start_page"),
                "end_page": item.get("end_page"),
                "status": item.get("status"),
                "raw_text_available": item.get("raw_text_available", False),
                "header_fields": item.get("header_fields", {}),
                "line_items": item.get("line_items", []),
                "validation": item.get("validation", {
                    "mandatory_fields": [],
                    "missing_fields": [],
                    "is_complete": False
                })
            }
            for item in state.get("extracted_data", [])
        ],

        "missing_documents": missing_documents,
        "incomplete_documents": incomplete_documents
    }

    return {
        **state,
        "status": final_status,
        "message": "Document classification, splitting, and field extraction completed.",
        "response": response
    }
