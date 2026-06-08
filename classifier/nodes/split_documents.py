import os
from pypdf import PdfReader, PdfWriter

print("classifier.nodes.split_documents: module loaded")


def get_file_prefix(document_type):
    mapping = {
        "PO": "PO",
        "Delivery Challan": "Delivery_Challan",
        "Invoice": "Invoice"
    }

    return mapping.get(document_type, "Unknown")


def split_documents_node(state):
    print("classifier.nodes.split_documents: split_documents_node invoked")
    try:
        input_file_path = state["input_file_path"]
        output_folder = state["output_folder"]

        os.makedirs(output_folder, exist_ok=True)

        reader = PdfReader(input_file_path)

        extracted_documents = []

        counters = {
            "PO": 1,
            "Delivery Challan": 1,
            "Invoice": 1
        }

        for group in state["grouped_documents"]:
            document_type = group["document_type"]

            if document_type == "Unknown":
                continue

            writer = PdfWriter()

            for page_number in group["pages"]:
                writer.add_page(reader.pages[page_number - 1])

            counter = counters.get(document_type, 1)
            prefix = get_file_prefix(document_type)

            document_name = f"{prefix}_{counter:03d}.pdf"
            document_path = os.path.join(output_folder, document_name)

            with open(document_path, "wb") as output_file:
                writer.write(output_file)

            counters[document_type] = counter + 1

            extracted_documents.append({
                "document_type": document_type,
                "document_name": document_name,
                "document_path": document_path,
                "start_page": group["start_page"],
                "end_page": group["end_page"]
            })

        return {
            **state,
            "extracted_documents": extracted_documents,
            "status": "documents_split",
            "message": "Documents split and saved successfully."
        }

    except Exception as e:
        return {
            **state,
            "status": "error",
            "error": str(e),
            "message": "Document splitting failed."
        }
