import os
import io
import time
import uuid
import base64
import sqlite3
import functools
from typing import TypedDict, Optional

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pypdf import PdfReader, PdfWriter

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import interrupt, Command

from main import (
    MergedPageData,
    quality_agent,
    classifier_agent,
    merge_quality_and_classifier_data,
    decision_node_1,
    extraction_agent,
    normalization_agent,
    matching_agent,
    decision_node_2,
    communication_agent,
    approval_agent,
    process_document,
    decode_base64,
    encode_bytes,
    save_bytes_to_folder,
    CLASSIFIER_UPLOAD_FOLDER,
)


# ===========================================================================
# 1. Graph State
# ===========================================================================

class GraphState(TypedDict):
    file_path: str
    file_name: str
    file_bytes_base64: Optional[str]

    quality_pages: list[dict]
    classified_pages: list[dict]
    grouped_documents: list[dict]
    merged_pages: list[dict]

    reuploaded_doc_bytes: dict   # doc_type -> base64 of reuploaded standalone PDF

    extracted_data: list[dict]
    normalized_data: list[dict]
    matching_result: dict

    decision_1_passed: Optional[bool]
    decision_1_reason: Optional[str]
    failed_doc_types: list[str]
    decision_2_passed: Optional[bool]
    decision_2_reason: Optional[str]

    communication_payload: Optional[dict]
    approval_payload: Optional[dict]

    status: str
    message: str


# ===========================================================================
# 2. Retry decorator
# ===========================================================================

def retry(max_retries: int = 3, delay: int = 2):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(state: GraphState) -> GraphState:
            for attempt in range(max_retries):
                try:
                    return func(state)
                except Exception as e:
                    print(f"{func.__name__} failed attempt {attempt + 1}/{max_retries}: {e}")
                    time.sleep(delay)
            return {**state, "status": "failed", "message": f"{func.__name__} failed after {max_retries} retries"}
        return wrapper
    return decorator


# ===========================================================================
# 3. Reupload reprocessing helper (ported from main.py /reupload logic)
# ===========================================================================

def _reprocess_reuploaded_files(state: GraphState, reuploaded: dict) -> dict:
    """
    reuploaded: {filename: base64_bytes}
    Runs quality + classifier on each reuploaded file, detects wrong documents,
    patches merged_pages / grouped_documents / classified_pages in-place on state.
    Returns wrong_document_errors keyed by filename (empty dict = all good).
    """
    merged_pages_raw = [dict(m) for m in state["merged_pages"]]
    grouped_documents = [dict(g) for g in state["grouped_documents"]]
    classified_pages = [dict(c) for c in state["classified_pages"]]
    expected_doc_types = set(state["failed_doc_types"])

    wrong_document_errors: dict = {}

    for filename, b64 in reuploaded.items():
        file_bytes = base64.b64decode(b64)
        temp_path = save_bytes_to_folder(file_bytes, filename, CLASSIFIER_UPLOAD_FOLDER)

        quality_pages, q_status = quality_agent(temp_path, filename)
        if q_status != "success":
            wrong_document_errors[filename] = f"quality check failed: {q_status}"
            continue

        new_classified, new_grouped, c_status = classifier_agent(temp_path, filename)
        if c_status != "success":
            wrong_document_errors[filename] = f"classification failed: {c_status}"
            continue

        detected_types = {g["document_type"] for g in new_grouped if g["document_type"] != "Unknown"}
        matched = detected_types.intersection(expected_doc_types)

        if not matched:
            wrong_document_errors[filename] = {
                "expected": list(expected_doc_types),
                "detected_as": ", ".join(detected_types) if detected_types else "unknown",
            }
            continue

        doc_type = next(iter(matched))

        old_group = next((g for g in grouped_documents if g["document_type"] == doc_type), None)
        new_group = next((g for g in new_grouped if g["document_type"] == doc_type), None)
        old_pages = set(old_group["pages"]) if old_group else set()
        if old_group and new_group:
            old_group.update(new_group)
        elif new_group:
            grouped_documents.append(dict(new_group))

        merged_pages_raw = [mp for mp in merged_pages_raw if mp["page_number"] not in old_pages]
        for i, qp in enumerate(quality_pages):
            new_cp = new_classified[i] if i < len(new_classified) else {}
            page_num = new_group["pages"][i] if new_group and i < len(new_group["pages"]) else (i + 1)
            merged_pages_raw.append({
                "page_number": page_num,
                "quality_score": qp.get("quality_score"),
                "is_compliant": qp.get("is_compliant"),
                "document_type": doc_type,
                "classification_confidence": new_cp.get("confidence"),
                "classification_method": new_cp.get("classification_method"),
            })

        classified_pages = [cp for cp in classified_pages if cp.get("document_type") != doc_type]
        classified_pages.extend(new_classified)

        state["reuploaded_doc_bytes"][doc_type] = b64

    state["merged_pages"] = merged_pages_raw
    state["grouped_documents"] = grouped_documents
    state["classified_pages"] = classified_pages

    return wrong_document_errors


# ===========================================================================
# 4. Nodes
# ===========================================================================

@retry()
def quality_node(state: GraphState) -> GraphState:
    pages, status = quality_agent(state["file_path"], state["file_name"])
    if status != "success":
        return {**state, "status": "quality_failed", "message": status}
    return {**state, "quality_pages": pages, "status": "quality_done"}


@retry()
def classifier_node(state: GraphState) -> GraphState:
    classified, grouped, status = classifier_agent(state["file_path"], state["file_name"])
    if status != "success":
        return {**state, "status": "classifier_failed", "message": status}
    return {**state, "classified_pages": classified, "grouped_documents": grouped, "status": "classifier_done"}


def merge_node(state: GraphState) -> GraphState:
    merged = merge_quality_and_classifier_data(state["quality_pages"], state["classified_pages"])
    return {**state, "merged_pages": [m.model_dump() for m in merged], "status": "merge_done"}


def decision_1_node(state: GraphState) -> GraphState:
    merged_objs = [MergedPageData(**m) for m in state["merged_pages"]]
    passed, reason, failed_doc_types = decision_node_1(merged_objs)

    while not passed:
        human_input = interrupt({
            "decision": "decision_1_failed",
            "reason": reason,
            "failed_doc_types": failed_doc_types,
            "message": "Quality/presence check failed. Reupload the listed documents.",
        })

        if human_input.get("give_up"):
            return {
                **state,
                "decision_1_passed": False,
                "decision_1_reason": "Human ended reupload loop",
                "failed_doc_types": failed_doc_types,
                "status": "decision_1_abandoned",
            }

        reuploaded = human_input.get("reuploaded_files", {})
        state["failed_doc_types"] = failed_doc_types

        wrong_docs = _reprocess_reuploaded_files(state, reuploaded)

        if wrong_docs:
            reason = f"Wrong document(s) uploaded: {wrong_docs}"
            continue

        merged_objs = [MergedPageData(**m) for m in state["merged_pages"]]
        passed, reason, failed_doc_types = decision_node_1(merged_objs)

    return {
        **state,
        "decision_1_passed": True,
        "decision_1_reason": reason,
        "failed_doc_types": [],
        "status": "decision_1_done",
    }


@retry()
def extraction_node(state: GraphState) -> GraphState:
    original_bytes = decode_base64(state["file_bytes_base64"])
    reuploaded = state.get("reuploaded_doc_bytes") or {}
    reader = PdfReader(io.BytesIO(original_bytes))

    documents = []
    for group in state["grouped_documents"]:
        doc_type = group["document_type"]
        if doc_type == "Unknown":
            continue

        if doc_type in reuploaded:
            doc_bytes = base64.b64decode(reuploaded[doc_type])
        else:
            writer = PdfWriter()
            for page_number in group["pages"]:
                writer.add_page(reader.pages[page_number - 1])
            buf = io.BytesIO()
            writer.write(buf)
            doc_bytes = buf.getvalue()

        documents.append({
            "document_type": doc_type,
            "document_name": f"{doc_type}_{group['start_page']}_{group['end_page']}.pdf",
            "document_bytes_base64": encode_bytes(doc_bytes),
            "start_page": group["start_page"],
            "end_page": group["end_page"],
        })

    return {**state, "grouped_documents": documents, "status": "extraction_done"}


def extract_fields_node(state: GraphState) -> GraphState:
    extracted = []
    for doc in state["grouped_documents"]:
        doc_bytes = decode_base64(doc["document_bytes_base64"])
        result = process_document(doc_bytes, doc["document_name"], doc["document_type"])
        extracted.append({
            "document_type": doc["document_type"],
            "document_name": doc["document_name"],
            "extracted_fields": result["fields"],
            "method_used": result.get("method_used", "rule_based"),
        })
    return {**state, "extracted_data": extracted, "status": "extract_fields_done"}


@retry()
def normalization_node(state: GraphState) -> GraphState:
    normalized, status = normalization_agent(state["extracted_data"])
    return {**state, "normalized_data": normalized, "status": "normalization_done"}


@retry()
def matching_node(state: GraphState) -> GraphState:
    result, status = matching_agent(state["normalized_data"], state["classified_pages"])
    return {**state, "matching_result": result, "status": "matching_done"}


def decision_2_node(state: GraphState) -> GraphState:
    passed, reason = decision_node_2(state["matching_result"])

    if not passed:
        communication_payload = communication_agent(state["matching_result"])
        human_input = interrupt({
            "decision": "decision_2_failed",
            "reason": reason,
            "communication_payload": communication_payload,
            "message": "3-way match failed. Approve or reject.",
        })
        passed = human_input.get("approved", False)
        reason = human_input.get("reason", "Resumed after human review")
        return {
            **state,
            "decision_2_passed": passed,
            "decision_2_reason": reason,
            "communication_payload": communication_payload,
            "status": "decision_2_done",
        }

    return {**state, "decision_2_passed": True, "decision_2_reason": reason, "status": "decision_2_done"}


def approval_node(state: GraphState) -> GraphState:
    payload = approval_agent(state["matching_result"], state["normalized_data"])
    return {**state, "approval_payload": payload, "status": "success"}


def communication_node(state: GraphState) -> GraphState:
    payload = state.get("communication_payload") or communication_agent(state["matching_result"])
    return {**state, "communication_payload": payload, "status": "rejected"}


# ===========================================================================
# 5. Routers
# ===========================================================================

def route_after_decision_1(state: GraphState) -> str:
    return "extraction" if state["decision_1_passed"] else END


def route_after_decision_2(state: GraphState) -> str:
    return "approval" if state["decision_2_passed"] else "communication"


# ===========================================================================
# 6. Checkpointer + graph builder
# ===========================================================================

def get_checkpointer() -> SqliteSaver:
    os.makedirs("data", exist_ok=True)
    conn = sqlite3.connect("data/workflow.db", check_same_thread=False)
    return SqliteSaver(conn)


def build_graph():
    builder = StateGraph(GraphState)

    builder.add_node("quality", quality_node)
    builder.add_node("classifier", classifier_node)
    builder.add_node("merge", merge_node)
    builder.add_node("decision_1", decision_1_node)
    builder.add_node("extraction", extraction_node)
    builder.add_node("extract_fields", extract_fields_node)
    builder.add_node("normalization", normalization_node)
    builder.add_node("matching", matching_node)
    builder.add_node("decision_2", decision_2_node)
    builder.add_node("approval", approval_node)
    builder.add_node("communication", communication_node)

    builder.set_entry_point("quality")
    builder.add_edge("quality", "classifier")
    builder.add_edge("classifier", "merge")
    builder.add_edge("merge", "decision_1")
    builder.add_conditional_edges(
        "decision_1",
        route_after_decision_1,
        {
            "extraction": "extraction",
            END: END,
        }
    )

    builder.add_edge("extraction", "extract_fields")
    builder.add_edge("extract_fields", "normalization")
    builder.add_edge("normalization", "matching")
    builder.add_edge("matching", "decision_2")
    builder.add_conditional_edges(
        "decision_2",
        route_after_decision_2,
        {
            "approval": "approval",
            "communication": "communication",
        }
    )

    builder.add_edge("approval", END)
    builder.add_edge("communication", END)

    return builder.compile(checkpointer=get_checkpointer())


# ===========================================================================
# 7. FastAPI endpoints
# ===========================================================================

app = FastAPI(title="P2P LangGraph API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

graph = build_graph()
try:
    graph.get_graph().print_ascii()
except Exception:
    pass


def _strip_bytes(state: dict) -> dict:
    if not state:
        return state
    return {k: v for k, v in state.items() if k not in ("file_bytes_base64", "reuploaded_doc_bytes")}


def _extract_interrupt(result: dict):
    interrupts = result.get("__interrupt__")
    if interrupts:
        return interrupts[0].value
    return None


@app.post("/graph/orchestrate")
async def orchestrate(file: UploadFile):
    payload = await file.read()
    if not payload:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    file_path = save_bytes_to_folder(payload, file.filename, CLASSIFIER_UPLOAD_FOLDER)

    initial_state = {
        "file_path": file_path,
        "file_name": file.filename,
        "file_bytes_base64": encode_bytes(payload),
        "quality_pages": [], "classified_pages": [], "grouped_documents": [], "merged_pages": [],
        "reuploaded_doc_bytes": {},
        "extracted_data": [], "normalized_data": [], "matching_result": {},
        "decision_1_passed": None, "decision_1_reason": None, "failed_doc_types": [],
        "decision_2_passed": None, "decision_2_reason": None,
        "communication_payload": None, "approval_payload": None,
        "status": "started", "message": "",
    }

    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}
    result = graph.invoke(initial_state, config=config)

    interrupt_payload = _extract_interrupt(result)
    if interrupt_payload:
        return {"thread_id": thread_id, "status": "interrupted", "interrupt": interrupt_payload, "state": _strip_bytes(result)}
    return {"thread_id": thread_id, "status": result.get("status"), "state": _strip_bytes(result)}


@app.post("/graph/resume/{thread_id}")
async def resume_decision_1(thread_id: str, files: list[UploadFile] = File(...)):
    config = {"configurable": {"thread_id": thread_id}}
    snapshot = graph.get_state(config)
    if not snapshot.values:
        raise HTTPException(status_code=404, detail=f"Thread '{thread_id}' not found")

    reuploaded_files = {}
    for f in files:
        b = await f.read()
        if b:
            reuploaded_files[f.filename] = base64.b64encode(b).decode("utf-8")

    result = graph.invoke(Command(resume={"reuploaded_files": reuploaded_files}), config=config)

    interrupt_payload = _extract_interrupt(result)
    if interrupt_payload:
        return {"thread_id": thread_id, "status": "interrupted", "interrupt": interrupt_payload, "state": _strip_bytes(result)}
    return {"thread_id": thread_id, "status": result.get("status"), "state": _strip_bytes(result)}


@app.post("/graph/resume-approval/{thread_id}")
async def resume_decision_2(thread_id: str, approved: bool = Form(...), reason: str = Form("Resumed by human")):
    config = {"configurable": {"thread_id": thread_id}}
    snapshot = graph.get_state(config)
    if not snapshot.values:
        raise HTTPException(status_code=404, detail=f"Thread '{thread_id}' not found")

    result = graph.invoke(Command(resume={"approved": approved, "reason": reason}), config=config)

    interrupt_payload = _extract_interrupt(result)
    if interrupt_payload:
        return {"thread_id": thread_id, "status": "interrupted", "interrupt": interrupt_payload, "state": _strip_bytes(result)}
    return {"thread_id": thread_id, "status": result.get("status"), "state": _strip_bytes(result)}


@app.get("/graph/state/{thread_id}")
async def get_state(thread_id: str):
    config = {"configurable": {"thread_id": thread_id}}
    snapshot = graph.get_state(config)
    if not snapshot.values:
        raise HTTPException(status_code=404, detail=f"Thread '{thread_id}' not found")
    return {
        "thread_id": thread_id,
        "status": snapshot.values.get("status"),
        "next": snapshot.next,
        "state": _strip_bytes(snapshot.values),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)