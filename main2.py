from dotenv import load_dotenv

load_dotenv()

from typing import TypedDict, List, Optional
from main import (
    quality_agent,
    classifier_agent,
    merge_quality_and_classifier_data,
    decision_node_1,
    extraction_agent,
    decode_base64,
    process_document,
    matching_agent,
    approval_agent
)

from main import (save_bytes_to_folder, encode_bytes)
from fastapi import FastAPI, UploadFile


class GraphState(TypedDict):
    file_path: str
    file_name: str
    file_bytes_base64: Optional[str]

    quality_pages: List[dict]
    classified_pages: List[dict]
    grouped_documents: List[dict]
    merged_pages: List[dict]

    extracted_data: List[dict]
    matching_result: dict

    decision_1_passed: Optional[bool]
    decision_1_reason: Optional[str]
    decision_2_passed: Optional[bool]

    status: str
    message: str



import time
import functools

def retry(max_retries=3, delay=2):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(state):
            for attempt in range(max_retries):
                try:
                    return func(state)
                except Exception as e:
                    print(f"{func.__name__} failed attempt {attempt+1}: {e}")
                    time.sleep(delay)

            state["status"] = "failed"
            state["message"] = f"{func.__name__} failed after retries"
            return state
        return wrapper
    return decorator



@retry()
def quality_node(state: GraphState):
    pages, status = quality_agent(state["file_path"], state["file_name"])
    state["quality_pages"] = pages
    state["status"] = status
    return state


@retry()
def classifier_node(state):
    classified, grouped, status = classifier_agent(
        state["file_path"],
        state["file_name"]
    )
    state["classified_pages"] = classified
    state["grouped_documents"] = grouped
    state["status"] = status
    return state

def merge_node(state):
    state["merged_pages"] = merge_quality_and_classifier_data(
        state["quality_pages"],
        state["classified_pages"]
    )
    return state

def decision_1_node(state):
    passed, reason = decision_node_1(state["merged_pages"])

    state["decision_1_passed"] = passed
    state["decision_1_reason"] = reason

    if not passed:
        state["status"] = "awaiting_human"
        raise Exception("HUMAN_REVIEW_REQUIRED")

    return state


@retry()
def extraction_node(state):
    docs, status = extraction_agent(
        state["file_path"],
        state["grouped_documents"],
        decode_base64(state["file_bytes_base64"])
    )
    state["grouped_documents"] = docs
    return state


def extract_fields_node(state):
    extracted = []

    for doc in state["grouped_documents"]:
        doc_bytes = decode_base64(doc["document_bytes_base64"])

        result = process_document(
            doc_bytes,
            doc["document_name"],
            doc["document_type"]
        )

        extracted.append(result)

    state["extracted_data"] = extracted
    return state

@retry()
def matching_node(state):
    result, status = matching_agent(state["extracted_data"])
    state["matching_result"] = result
    return state


def decision_2_node(state):
    mismatches = state["matching_result"].get("mismatches", [])

    if mismatches:
        state["decision_2_passed"] = False
        state["status"] = "awaiting_human"
        raise Exception("HUMAN_REVIEW_REQUIRED")

    state["decision_2_passed"] = True
    return state


def approval_node(state):
    state["approval"] = approval_agent(state)
    return state


def route_decision_1(state):
    return "extraction" if state["decision_1_passed"] else "__end__"

def route_decision_2(state):
    return "approval" if state["decision_2_passed"] else "__end__"


from langgraph.checkpoint.sqlite import  SqliteSaver
import sqlite3

def get_checkpointer():
    conn = sqlite3.connect("data/workflow.db", check_same_thread=False)
    return SqliteSaver(conn)


from langgraph.graph import StateGraph

def build_graph():
    builder = StateGraph(GraphState)

    # Nodes
    builder.add_node("quality", quality_node)
    builder.add_node("classifier", classifier_node)
    builder.add_node("merge", merge_node)
    builder.add_node("decision_1", decision_1_node)
    builder.add_node("extraction", extraction_node)
    builder.add_node("extract_fields", extract_fields_node)
    builder.add_node("matching", matching_node)
    builder.add_node("decision_2", decision_2_node)
    builder.add_node("approval", approval_node)

    # Flow
    builder.set_entry_point("quality")
    builder.add_edge("quality", "classifier")
    builder.add_edge("classifier", "merge")
    builder.add_edge("merge", "decision_1")
    builder.add_conditional_edges("decision_1", route_decision_1)

    builder.add_edge("extraction", "extract_fields")
    builder.add_edge("extract_fields", "matching")
    builder.add_edge("matching", "decision_2")
    builder.add_conditional_edges("decision_2", route_decision_2)

    builder.add_edge("approval", "__end__")

    return builder.compile(checkpointer=get_checkpointer())


import os
from fastapi.middleware.cors import CORSMiddleware

# --------------------------------------------------
# App Config
# --------------------------------------------------
APP_TITLE = os.getenv("APP_TITLE", "P2P Document Processing API")
APP_DESCRIPTION = os.getenv(
    "APP_DESCRIPTION",
    "Document processing API for quality evaluation, document classification, and data extraction."
)
APP_VERSION = os.getenv("APP_VERSION", "1.0.0")

QUALITY_UPLOAD_FOLDER = os.getenv("QUALITY_UPLOAD_FOLDER", os.getenv("UPLOAD_FOLDER", "data/uploads/quality_checks"))
CLASSIFIER_UPLOAD_FOLDER = os.getenv("CLASSIFIER_UPLOAD_FOLDER", os.getenv("UPLOAD_FOLDER", "data/uploads/classifier"))
CLASSIFIER_OUTPUT_FOLDER = os.getenv("CLASSIFIER_OUTPUT_FOLDER", os.getenv("OUTPUT_FOLDER", "data/Processed_docs"))


from fastapi.responses import StreamingResponse
import json, uuid

app = FastAPI(
    title=APP_TITLE,
    description=APP_DESCRIPTION,
    version=APP_VERSION,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


os.makedirs(QUALITY_UPLOAD_FOLDER, exist_ok=True)
os.makedirs(CLASSIFIER_UPLOAD_FOLDER, exist_ok=True)
os.makedirs(CLASSIFIER_OUTPUT_FOLDER, exist_ok=True)

graph = build_graph()
# graph.get_graph().visualize("data/graph.png")
graph.get_graph().print_ascii()


@app.post("/orchestrate/stream")
async def orchestrate_stream(file: UploadFile):

    payload = await file.read()
    file_path = save_bytes_to_folder(payload, file.filename, CLASSIFIER_UPLOAD_FOLDER)

    state = {
        "file_path": file_path,
        "file_name": file.filename,
        "file_bytes_base64": encode_bytes(payload),

        "quality_pages": [],
        "classified_pages": [],
        "grouped_documents": [],
        "merged_pages": [],
        "extracted_data": [],
        "matching_result": {},

        "decision_1_passed": None,
        "decision_1_reason": None,
        "decision_2_passed": None,

        "status": "started",
        "message": ""
    }

    thread_id = str(uuid.uuid4())

    async def event_stream():
        for step in graph.invoke(
            state,
            config={"thread_id": thread_id}
        ):
            yield f"data: {json.dumps(step)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.post("/resume/{thread_id}")
async def resume(thread_id: str, override: bool = True):

    checkpoint = graph.get_state(config={"thread_id": thread_id})
    state = checkpoint.values

    state["decision_1_passed"] = override
    state["decision_2_passed"] = override

    result = graph.invoke(state, config={"thread_id": thread_id})

    return result
