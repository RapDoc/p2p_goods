import os

print("classifier.nodes.validate_input: module loaded")


def validate_input_node(state):
    print("classifier.nodes.validate_input: validate_input_node invoked")
    input_file_path = state.get("input_file_path")

    if not input_file_path:
        return {
            **state,
            "status": "error",
            "error": "Input file path is missing.",
            "message": "Validation failed."
        }

    if not os.path.exists(input_file_path):
        return {
            **state,
            "status": "error",
            "error": "Input file does not exist.",
            "message": "Validation failed."
        }

    if not input_file_path.lower().endswith(".pdf"):
        return {
            **state,
            "status": "error",
            "error": "Only PDF files are supported.",
            "message": "Validation failed."
        }

    return {
        **state,
        "status": "validated",
        "message": "Input file validated successfully."
    }
