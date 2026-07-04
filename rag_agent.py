import os
import json
import pickle
from typing import Optional

import numpy as np

# Lazy imports for heavy deps so module import is cheap
_model = None
_faiss = None


RAG_BASE_DIR = "data/rag"
EMBED_MODEL_NAME = "all-MiniLM-L6-v2"
TOP_K = 10             # retrieve wide, let the LLM filter
CHUNK_SIZE = 1500      # larger OCR chunks on natural boundaries
CHUNK_OVERLAP = 200


# ---------------------------------------------------------------------------
# Lazy loaders
# ---------------------------------------------------------------------------

def _get_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        print(f"rag_agent: loading embedding model {EMBED_MODEL_NAME}")
        _model = SentenceTransformer(EMBED_MODEL_NAME)
    return _model


def _get_faiss():
    global _faiss
    if _faiss is None:
        import faiss
        _faiss = faiss
    return _faiss


# ---------------------------------------------------------------------------
# Chunking helpers
# ---------------------------------------------------------------------------

def _chunk_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """
    Structure-aware chunker: splits on paragraph/line boundaries rather than
    blindly mid-word, and only packs whole lines into each chunk. Keeps related
    rows (e.g. a table) together far more often than a fixed char window.
    """
    if not text:
        return []
    text = text.strip()

    # Split into natural blocks (paragraphs / lines), preserving order
    blocks = [b for b in text.split("\n") if b.strip()]

    chunks: list[str] = []
    current: list[str] = []
    current_len = 0

    for block in blocks:
        block_len = len(block) + 1  # +1 for the newline
        # If adding this block overflows the chunk, flush current first
        if current_len + block_len > size and current:
            chunks.append("\n".join(current))
            # Start next chunk with an overlap tail of the previous chunk
            if overlap > 0:
                tail = "\n".join(current)[-overlap:]
                current = [tail]
                current_len = len(tail)
            else:
                current = []
                current_len = 0
        current.append(block)
        current_len += block_len

    if current:
        chunks.append("\n".join(current))

    return chunks


def _build_documents(
    normalized_data: list[dict],
    matching_result: dict,
    ocr_texts: dict,
) -> list[dict]:
    """
    Turn pipeline outputs into a flat list of {text, metadata} chunks for indexing.

    General strategy (no per-question hand-crafting):
      - One chunk per document holding ALL its structured fields (lists rendered
        readably, not as JSON) so field groups stay together.
      - Raw OCR split on natural line/paragraph boundaries via _chunk_text.
      - One chunk for the 3-way match outcome.
    Redundancy (structured + raw OCR) means most questions hit something relevant;
    wide retrieval (TOP_K) + a synthesis-oriented prompt handle the rest.
    """
    docs: list[dict] = []

    # 1. Structured fields — one chunk per document, lists rendered readably.
    for nd in normalized_data:
        doc_type = nd.get("document_type", "unknown")
        fields = nd.get("normalized_fields") or {}
        lines = [f"Document type: {doc_type}"]
        for k, v in fields.items():
            if isinstance(v, list):
                # Render list-of-dicts (e.g. item_details) as readable rows
                lines.append(f"{k}:")
                for idx, item in enumerate(v, 1):
                    if isinstance(item, dict):
                        parts = ", ".join(f"{ik}: {iv}" for ik, iv in item.items())
                        lines.append(f"  {idx}. {parts}")
                    else:
                        lines.append(f"  {idx}. {item}")
            elif isinstance(v, dict):
                parts = ", ".join(f"{ik}: {iv}" for ik, iv in v.items())
                lines.append(f"{k}: {parts}")
            else:
                lines.append(f"{k}: {v}")
        docs.append({
            "text": "\n".join(lines),
            "metadata": {"source": f"{doc_type}_fields", "doc_type": doc_type},
        })

    # 2. Raw OCR text — chunked on natural boundaries, per document type.
    for doc_type, text in (ocr_texts or {}).items():
        for i, chunk in enumerate(_chunk_text(text)):
            docs.append({
                "text": chunk,
                "metadata": {"source": f"{doc_type}_ocr_{i}", "doc_type": doc_type},
            })

    # 3. Match results — one chunk.
    if matching_result:
        summary = matching_result.get("summary", "")
        result = matching_result.get("result", "")
        match_lines = [f"3-way match result: {result}", f"Summary: {summary}"]
        for m in matching_result.get("matches", []):
            match_lines.append(f"PASS: {m}")
        for mm in matching_result.get("mismatches", []):
            match_lines.append(
                f"MISMATCH: field={mm.get('field')} "
                f"PO={mm.get('po_value')} actual={mm.get('actual_value')} "
                f"note={mm.get('note')}"
            )
        interp = matching_result.get("llm_interpretation") or {}
        if interp.get("interpretation"):
            match_lines.append(f"Interpretation: {interp['interpretation']}")
        docs.append({
            "text": "\n".join(match_lines),
            "metadata": {"source": "matching_result", "doc_type": "match"},
        })

    return docs


# ---------------------------------------------------------------------------
# Index build / load
# ---------------------------------------------------------------------------

def _thread_dir(thread_id: str) -> str:
    return os.path.join(RAG_BASE_DIR, thread_id)


def build_rag_index(
    thread_id: str,
    normalized_data: list[dict],
    matching_result: dict,
    ocr_texts: Optional[dict] = None,
) -> int:
    """
    Build and persist a FAISS index for this thread.
    Returns the number of chunks indexed.
    """
    faiss = _get_faiss()
    model = _get_model()

    docs = _build_documents(normalized_data, matching_result, ocr_texts or {})
    if not docs:
        print("rag_agent: no documents to index")
        return 0

    texts = [d["text"] for d in docs]
    embeddings = model.encode(texts, convert_to_numpy=True, show_progress_bar=False)
    embeddings = np.asarray(embeddings, dtype="float32")

    dim = embeddings.shape[1]
    index = faiss.IndexFlatL2(dim)
    index.add(embeddings)

    out_dir = _thread_dir(thread_id)
    os.makedirs(out_dir, exist_ok=True)
    faiss.write_index(index, os.path.join(out_dir, "index.faiss"))
    with open(os.path.join(out_dir, "docs.pkl"), "wb") as f:
        pickle.dump(docs, f)

    print(f"rag_agent: indexed {len(docs)} chunks for thread {thread_id}")
    return len(docs)


def _load_index(thread_id: str):
    faiss = _get_faiss()
    out_dir = _thread_dir(thread_id)
    index_path = os.path.join(out_dir, "index.faiss")
    docs_path = os.path.join(out_dir, "docs.pkl")
    if not (os.path.exists(index_path) and os.path.exists(docs_path)):
        return None, None
    index = faiss.read_index(index_path)
    with open(docs_path, "rb") as f:
        docs = pickle.load(f)
    return index, docs


# ---------------------------------------------------------------------------
# Chat
# ---------------------------------------------------------------------------

def chat_with_documents(thread_id: str, question: str, top_k: int = TOP_K) -> dict:
    """
    Retrieve relevant chunks for this thread and answer the question.
    Returns {"answer": str, "sources": list[str]}.
    """
    index, docs = _load_index(thread_id)
    if index is None:
        return {
            "answer": "No knowledge base found for this session. Has the pipeline finished processing?",
            "sources": [],
        }

    model = _get_model()
    q_emb = model.encode([question], convert_to_numpy=True).astype("float32")
    distances, indices = index.search(q_emb, min(top_k, len(docs)))

    retrieved = [docs[i] for i in indices[0] if 0 <= i < len(docs)]
    context = "\n\n---\n\n".join(d["text"] for d in retrieved)
    sources = [d["metadata"]["source"] for d in retrieved]

    prompt = (
        "You are an assistant answering questions about a set of processed business "
        "documents (purchase order, tax invoice, delivery challan) and their 3-way "
        "match results.\n\n"
        "The context below is assembled from multiple retrieved sections — structured "
        "fields, raw document text, and match results. The information needed to answer "
        "may be SPREAD ACROSS several sections, so read all of them and synthesize.\n"
        "- If asked to list things (items, amounts, etc.), gather them from EVERY relevant "
        "section, not just the first.\n"
        "- For numeric differences (e.g. PO vs invoice totals), reason about tax: PO totals "
        "are pre-tax, invoice totals include GST.\n"
        "- Only state facts supported by the context. If something truly isn't present, say so.\n\n"
        f"Context:\n{context}\n\n"
        f"Question: {question}\n\n"
        "Answer:"
    )

    try:
        from openai_utils import query_openai
        answer = query_openai(prompt, max_tokens=512, temperature=0.0)
    except Exception as e:
        answer = f"(LLM unavailable: {e})\n\nRetrieved context:\n{context}"

    return {"answer": answer, "sources": sources}


# ---------------------------------------------------------------------------
# OCR text grouping helper
# ---------------------------------------------------------------------------

def group_ocr_by_doc_type(
    extracted_pages: list[dict],
    classified_pages: list[dict],
) -> dict:
    """
    Combine raw OCR text per document type.

    extracted_pages: [{"page_number": int, "text": str, ...}, ...]
    classified_pages: [{"page_number": int, "document_type": str, ...}, ...]

    Returns: {doc_type: "concatenated text of all its pages"}
    """
    # page_number -> doc_type
    page_to_type = {
        cp["page_number"]: cp.get("document_type", "unknown")
        for cp in classified_pages
    }

    grouped: dict[str, list[str]] = {}
    for ep in extracted_pages:
        page_num = ep.get("page_number")
        text = ep.get("text", "")
        if not text:
            continue
        doc_type = page_to_type.get(page_num, "unknown")
        grouped.setdefault(doc_type, []).append(text)

    return {dt: "\n\n".join(texts) for dt, texts in grouped.items()}