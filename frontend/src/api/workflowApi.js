const API_BASE = "http://localhost:8000";

async function handleJsonResponse(res, fallbackMessage) {
  if (!res.ok) {
    let msg = fallbackMessage;
    try {
      const data = await res.json();
      msg = data.detail || msg;
    } catch (_) {}
    throw new Error(msg);
  }
  return res.json();
}

/**
 * Read a text/event-stream response and emit each parsed event to onEvent.
 * Returns the final terminal event payload ("done" or "interrupted").
 */
async function consumeEventStream(res, fallbackMessage, onEvent) {
  if (!res.ok) {
    let msg = fallbackMessage;
    try {
      const data = await res.json();
      msg = data.detail || msg;
    } catch (_) {}
    throw new Error(msg);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();

  let buffer = "";
  let finalPayload = null;

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });

    // SSE events are separated by blank lines
    const parts = buffer.split("\n\n");
    buffer = parts.pop() || "";

    for (const part of parts) {
      const lines = part.split("\n");
      for (const line of lines) {
        if (!line.startsWith("data: ")) continue;

        const jsonStr = line.slice(6).trim();
        if (!jsonStr) continue;

        const payload = JSON.parse(jsonStr);
        if (onEvent) onEvent(payload);

        if (payload.event === "done" || payload.event === "interrupted") {
          finalPayload = payload;
        }
      }
    }
  }

  return finalPayload;
}

export async function orchestrateWorkflow(file, onEvent) {
  const formData = new FormData();
  formData.append("file", file);

  const res = await fetch(`${API_BASE}/graph/orchestrate`, {
    method: "POST",
    body: formData,
  });

  return consumeEventStream(res, "Failed to start workflow", onEvent);
}

export async function resumeDecision1(threadId, files, onEvent) {
  const formData = new FormData();
  files.forEach((file) => formData.append("files", file));

  const res = await fetch(`${API_BASE}/graph/resume/${threadId}`, {
    method: "POST",
    body: formData,
  });

  return consumeEventStream(res, "Failed to resume decision 1", onEvent);
}

export async function resumeDecision2(threadId, approved, reason, onEvent) {
  const formData = new FormData();
  formData.append("approved", approved);
  formData.append("reason", reason);

  const res = await fetch(`${API_BASE}/graph/resume-approval/${threadId}`, {
    method: "POST",
    body: formData,
  });

  return consumeEventStream(res, "Failed to resume decision 2", onEvent);
}

export async function fetchWorkflowState(threadId) {
  const res = await fetch(`${API_BASE}/graph/state/${threadId}`);
  return handleJsonResponse(res, "Failed to fetch workflow state");
}

export async function chatWithDocuments(threadId, question) {
  const formData = new FormData();
  formData.append("question", question);

  const res = await fetch(`${API_BASE}/graph/chat/${threadId}`, {
    method: "POST",
    body: formData,
  });

  return handleJsonResponse(res, "Failed to chat with documents");
}