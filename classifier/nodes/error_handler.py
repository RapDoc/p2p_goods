print("classifier.nodes.error_handler: module loaded")

def error_node(state):
    print("classifier.nodes.error_handler: error_node invoked")
    response = {
        "status": "error",
        "message": state.get("message", "Workflow failed."),
        "input_file": state.get("input_file_name"),
        "processed_folder": state.get("output_folder"),
        "total_pages": state.get("total_pages", 0),

        "classified_pages": state.get("classified_pages", []),
        "extracted_documents": state.get("extracted_documents", []),
        "extracted_data": state.get("extracted_data", []),

        "missing_documents": [],
        "incomplete_documents": [],
        "error": state.get("error", "Unknown error occurred.")
    }

    return {
        **state,
        "status": "error",
        "response": response
    }
