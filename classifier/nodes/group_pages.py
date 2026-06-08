print("classifier.nodes.group_pages: module loaded")

def group_pages_node(state):
    print("classifier.nodes.group_pages: group_pages_node invoked")
    try:
        classified_pages = state["classified_pages"]

        grouped_documents = []

        if not classified_pages:
            return {
                **state,
                "grouped_documents": [],
                "status": "grouped",
                "message": "No classified pages found."
            }

        current_type = classified_pages[0]["document_type"]
        current_pages = [classified_pages[0]["page_number"]]

        for page in classified_pages[1:]:
            page_type = page["document_type"]
            page_number = page["page_number"]

            if page_type == current_type:
                current_pages.append(page_number)
            else:
                grouped_documents.append({
                    "document_type": current_type,
                    "start_page": current_pages[0],
                    "end_page": current_pages[-1],
                    "pages": current_pages
                })

                current_type = page_type
                current_pages = [page_number]

        grouped_documents.append({
            "document_type": current_type,
            "start_page": current_pages[0],
            "end_page": current_pages[-1],
            "pages": current_pages
        })

        return {
            **state,
            "grouped_documents": grouped_documents,
            "status": "grouped",
            "message": "Pages grouped by document type successfully."
        }

    except Exception as e:
        return {
            **state,
            "status": "error",
            "error": str(e),
            "message": "Page grouping failed."
        }
