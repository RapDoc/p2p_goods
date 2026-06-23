const API_BASE = "http://localhost:8000";

async function handleResponse(res, fallbackMessage) {
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

export async function orchestrateWorkflow(file) {
  const formData = new FormData();
  formData.append("file", file);

  const res = await fetch(`${API_BASE}/graph/orchestrate`, {
    method: "POST",
    body: formData,
  });

  return handleResponse(res, "Failed to start workflow");
}

export async function resumeDecision1(threadId, files) {
  const formData = new FormData();
  files.forEach((file) => formData.append("files", file));

  const res = await fetch(`${API_BASE}/graph/resume/${threadId}`, {
    method: "POST",
    body: formData,
  });

  return handleResponse(res, "Failed to resume decision 1");
}

export async function resumeDecision2(threadId, approved, reason) {
  const formData = new FormData();
  formData.append("approved", approved);
  formData.append("reason", reason);

  const res = await fetch(`${API_BASE}/graph/resume-approval/${threadId}`, {
    method: "POST",
    body: formData,
  });

  return handleResponse(res, "Failed to resume decision 2");
}