from typing import TypedDict, List, Dict, Optional, Any

print("classifier.state: module loaded")


class DocumentAgentState(TypedDict):
    input_file_path: str
    input_file_name: str
    output_folder: str

    total_pages: int

    extracted_pages: List[Dict[str, Any]]
    classified_pages: List[Dict[str, Any]]
    grouped_documents: List[Dict[str, Any]]
    extracted_documents: List[Dict[str, Any]]

    # Data Extraction Agent output
    extracted_data: List[Dict[str, Any]]

    status: str
    message: str
    error: Optional[str]

    # Final schema response
    response: Optional[Dict[str, Any]]
