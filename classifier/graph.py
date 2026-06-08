from langgraph.graph import StateGraph, START, END

print("classifier.graph: module loaded")

from .state import DocumentAgentState

from .nodes.validate_input import validate_input_node
from .nodes.extract_text import extract_text_node
from .nodes.classify_pages import classify_pages_node
from .nodes.group_pages import group_pages_node
from .nodes.split_documents import split_documents_node
from .nodes.data_extraction import data_extraction_node
from .nodes.generate_response import generate_response_node
from .nodes.error_handler import error_node


def route_after_validation(state):
    if state.get("status") == "error":
        return "error_node"
    return "extract_text_node"


def route_after_extraction(state):
    if state.get("status") == "error":
        return "error_node"
    return "classify_pages_node"


def route_after_classification(state):
    if state.get("status") == "error":
        return "error_node"
    return "group_pages_node"


def route_after_grouping(state):
    if state.get("status") == "error":
        return "error_node"
    return "split_documents_node"


def route_after_splitting(state):
    if state.get("status") == "error":
        return "error_node"
    return "data_extraction_node"


def route_after_data_extraction(state):
    if state.get("status") == "error":
        return "error_node"
    return "generate_response_node"


def build_document_classification_graph():
    print("classifier.graph: build_document_classification_graph invoked")
    workflow = StateGraph(DocumentAgentState)

    workflow.add_node("validate_input_node", validate_input_node)
    workflow.add_node("extract_text_node", extract_text_node)
    workflow.add_node("classify_pages_node", classify_pages_node)
    workflow.add_node("group_pages_node", group_pages_node)
    workflow.add_node("split_documents_node", split_documents_node)
    workflow.add_node("data_extraction_node", data_extraction_node)
    workflow.add_node("generate_response_node", generate_response_node)
    workflow.add_node("error_node", error_node)

    workflow.add_edge(START, "validate_input_node")

    workflow.add_conditional_edges(
        "validate_input_node",
        route_after_validation,
        {
            "extract_text_node": "extract_text_node",
            "error_node": "error_node"
        }
    )

    workflow.add_conditional_edges(
        "extract_text_node",
        route_after_extraction,
        {
            "classify_pages_node": "classify_pages_node",
            "error_node": "error_node"
        }
    )

    workflow.add_conditional_edges(
        "classify_pages_node",
        route_after_classification,
        {
            "group_pages_node": "group_pages_node",
            "error_node": "error_node"
        }
    )

    workflow.add_conditional_edges(
        "group_pages_node",
        route_after_grouping,
        {
            "split_documents_node": "split_documents_node",
            "error_node": "error_node"
        }
    )

    workflow.add_conditional_edges(
        "split_documents_node",
        route_after_splitting,
        {
            "data_extraction_node": "data_extraction_node",
            "error_node": "error_node"
        }
    )

    workflow.add_conditional_edges(
        "data_extraction_node",
        route_after_data_extraction,
        {
            "generate_response_node": "generate_response_node",
            "error_node": "error_node"
        }
    )

    workflow.add_edge("generate_response_node", END)
    workflow.add_edge("error_node", END)

    return workflow.compile()
