from typing import Any
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import interrupt, Command

class State(TypedDict):
    # Upload
    uploaded_documents: list[dict]

    # Classification
    classified_documents: dict[str, list[dict]]

    # OCR
    ocr_confidence: float
    ocr_status: str 

    # HITL OCR review
    human_review_decision: str
    human_corrections: dict[str, Any]

    # Extraction
    extracted_data: dict[str, Any]

    # DC processing
    dc_summary: dict[str, Any]

    # Three-way match
    matching_results: dict[str, Any]

    # HITL approval
    approval_decision: str

    # Supplier loop
    supplier_query_status: str
    
OCR_THRESHOLD = 0.75

#Node 1 - Uploading Documents
def upload_documents(state: State) -> dict:
    docs = [
        {"id": "DOC-001", "name": "po.pdf"},
        {"id": "DOC-002", "name": "dc.pdf"},
        {"id": "DOC-003", "name": "invoice.pdf"},
    ]
    print("\n[upload_documents] Documents received:", [d["name"] for d in docs])
    return {
        "uploaded_documents": docs,
    }

#Node 2 - Classifying Documents
def classify_documents(state: State) -> dict:
    docs = state["uploaded_documents"]
    classified = {
        "Purchase Order": [docs[0]],
        "Delivery Challan": [docs[1]],
        "Invoice": [docs[2]],
    }

    print("\n[classify_documents] Classification complete")

    return {"classified_documents": classified}

#Node 3 - OCR Validation
def ocr_validation(state: State) -> dict:
    # TODO:
    # Integrate OCR engine
    # and compute actual confidence score
    
    # Simulate low-confidence scenario on first pass; high confidence after re-upload
    prior_decision = state.get("human_review_decision", "")
    confidence = 0.82 if prior_decision == "not_satisfactory" else 0.65
    status = "pass" if confidence >= OCR_THRESHOLD else "fail"

    print(f"\n[ocr_validation] Confidence: {confidence:.2f} → {status.upper()}")
    return {
        "ocr_confidence": confidence,
        "ocr_status": status,
    }

#Conditional Routing OCR
def route_ocr(state: State) -> str:
    if state["ocr_status"] == "pass":
        return "data_extraction"
    return "human_review"

#Node 4 - Human Review Agent
def human_review_agent(state: State) -> Command:
    ocr_payload = {
        "ocr_confidence": state["ocr_confidence"],
        "raw_ocr_output": {"po_number": None, "amount": "5?000"},
        "message": "OCR confidence below threshold. Please review and correct or request re-upload.",
    }
    human_response: dict = interrupt(ocr_payload)

    decision   = human_response.get("decision", "not_satisfactory")
    corrections = human_response.get("corrections", {})

    print(f"\n[human_review_agent] Decision: {decision}")
    if corrections:
        print(f"  Corrections: {corrections}")

    next_node = "data_extraction" if decision == "satisfactory" else "upload_documents"
    return Command(
        update={
            "human_review_decision": decision,
            "human_corrections":     corrections,
        },
        goto=next_node,
    )

#Node 5 - Data Extraction
def data_extraction(state: State) -> dict:
    # TODO:
    # Extract structured fields from PO/DC/Invoice documents
    base_extraction = {
        "po_number":      "PO-123",
        "invoice_number": "INV-456",
        "vendor":         "ABC Ltd",
        "amount":         50000,
    }
    corrections = state.get("human_corrections", {})
    extracted = {**base_extraction, **corrections}   # corrections win

    print("\n[data_extraction] Extracted data:", extracted)
    return {
        "extracted_data": extracted,
    }

#Node 6 - DC Processing
def dc_processing(state: State) -> dict:
    # TODO:
    # Parse Delivery Challans and aggregate quantities/date-wise deliveries
    summary = {
        "dc_count":       2,
        "total_quantity": 15,
        "date_wise": {
            "2024-05-22": 10,
            "2024-05-26": 5,
        },
    }
    print("\n[dc_processing] DC summary:", summary)
    return {
        "dc_summary": summary,
    }

#Node 7 - Three Way Matching
def three_way_matching(state: State) -> dict:
    # TODO:
    # Implement actual PO vs DC vs Invoice matching logic
    
    # Flip this flag to demo the mismatch path
    SIMULATE_MISMATCH = False

    if SIMULATE_MISMATCH:
        result = {
            "status": "mismatch",
            "issues": ["Invoice quantity exceeds delivered quantity"],
        }
    else:
        result = {"status": "matched", "issues": []}

    print(f"\n[three_way_matching] Match result: {result['status']}")
    if result["issues"]:
        print(f"  Issues: {result['issues']}")

    return {
        "matching_results": result,
    }

#Node 8 - Human Approval Agent
def human_approval_agent(state: State) -> Command:
    approval_payload = {
        "extracted_data":  state.get("extracted_data"),
        "dc_summary":      state.get("dc_summary"),
        "matching_results": state.get("matching_results"),
        "message": "Please review and approve, reject, or raise a supplier query.",
    }

    human_response: dict = interrupt(approval_payload)
    decision = human_response.get("decision", "approve")
    print(f"\n[human_approval_agent] Decision: {decision.upper()}")

    if(decision=="reject"):
        next_node = END
    elif(decision=="raise_query"):
        next_node = "supplier_loop"
    else:
        next_node = "trigger_payment"
        
    return Command(
        update={"approval_decision": decision},
        goto=next_node,
    )

#Node 9 - Supplier Loop
def supplier_loop(state: State) -> dict:
    # TODO:
    # Integrate supplier communication workflow
    # and capture supplier response
    
    print("\n[supplier_loop] Query sent to supplier.")
    # Simulate resolution after one round
    query_status = "resolved"
    print(f"  Supplier query status: {query_status}")
    return {
        "supplier_query_status": query_status,
    }


#Conditional Supply Route
def route_supplier(state: State) -> str:
    if state["supplier_query_status"] == "resolved":
        return "trigger_payment"
    return END

#Node 10 - Trigger Payment
def trigger_payment(state: State) -> dict:
    # TODO:
    # Integrate payment/ERP workflow
    print("\n[trigger_payment] ✓ Payment Triggered")
    return {
    }


builder = StateGraph(State)

#Adding Nodes
builder.add_node("upload_documents", upload_documents)
builder.add_node("classify_documents", classify_documents)
builder.add_node("ocr_validation", ocr_validation)
builder.add_node("human_review", human_review_agent)
builder.add_node("data_extraction", data_extraction)
builder.add_node("dc_processing", dc_processing)
builder.add_node("three_way_matching", three_way_matching)
builder.add_node("human_approval", human_approval_agent)
builder.add_node("supplier_loop", supplier_loop)
builder.add_node("trigger_payment", trigger_payment)

#Adding Edges
builder.add_edge(START, "upload_documents")

builder.add_edge("upload_documents", "classify_documents")
builder.add_edge("classify_documents", "ocr_validation")

builder.add_edge("data_extraction", "dc_processing")
builder.add_edge("dc_processing", "three_way_matching")
builder.add_edge("three_way_matching", "human_approval")

builder.add_edge("trigger_payment", END)

#Adding Conditional Edges
builder.add_conditional_edges(
    "ocr_validation",
    route_ocr,
    {
        "data_extraction": "data_extraction",
        "human_review": "human_review",
    },
)

builder.add_conditional_edges(
    "supplier_loop",
    route_supplier,
    {
        "trigger_payment": "trigger_payment",
        END: END,
    },
)

#Compiling Graph
checkpointer = MemorySaver()
graph = builder.compile(
    checkpointer=checkpointer
)

#Initial State defined
initial_state:State = {
    "uploaded_documents":   [],
    "classified_documents": {},
    "ocr_confidence":       0.0,
    "ocr_status":           "",
    "human_review_decision": "",
    "human_corrections":    {},
    "extracted_data":       {},
    "dc_summary":           {},
    "matching_results":     {},
    "approval_decision":    "",
    "supplier_query_status": "",
}

config = {"configurable": {"thread_id": "1"}}

#Run graph on initial state
print("Step 1 — Running graph until OCR interrupt")
result = graph.invoke(initial_state, config)
print("\nGraph paused. Interrupt payload:", result)

print("Step 2 — Resuming with human OCR review decision")
ocr_response = Command(resume={
    "decision":    "satisfactory",
    "corrections": {"po_number": "PO-123", "amount": 50000},
})
result = graph.invoke(ocr_response, config)
print("\nGraph paused. Interrupt payload:", result)

print("Step 3 — Resuming with human approval decision")
approval_response = Command(resume={"decision": "approve"})
result = graph.invoke(approval_response, config)
print("\nFinal result:", result)
