import { useState } from "react";
import { chatWithDocuments } from "../api/workflowApi";

export default function RagChat({ threadId, onBack }) {
  const [messages, setMessages] = useState([
    {
      role: "assistant",
      content:
        "Ask me anything about the processed PO / Invoice / Challan documents for this workflow.",
      sources: [],
    },
  ]);
  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSend() {
    const trimmed = question.trim();
    if (!trimmed) return;
    if (!threadId) {
      alert("No workflow thread found. Run a workflow first.");
      return;
    }

    const userMessage = {
      role: "user",
      content: trimmed,
    };

    setMessages((prev) => [...prev, userMessage]);
    setQuestion("");

    try {
      setLoading(true);
      const data = await chatWithDocuments(threadId, trimmed);

      const assistantMessage = {
        role: "assistant",
        content: data.answer || "No answer returned.",
        sources: data.sources || [],
      };

      setMessages((prev) => [...prev, assistantMessage]);
    } catch (err) {
      console.error(err);
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: `Error: ${err.message || "Failed to chat with documents"}`,
          sources: [],
        },
      ]);
    } finally {
      setLoading(false);
    }
  }

  function handleKeyDown(e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  return (
    <div className="chat-page">
      <div className="chat-topbar">
        <div>
          <h2>Document Chat</h2>
          <p className="muted">
            Ask questions about the processed documents for this workflow.
          </p>
          <div className="thread-pill">
            Thread ID: <span>{threadId || "-"}</span>
          </div>
        </div>

        <button className="secondary-btn" onClick={onBack}>
          ← Back to Workflow
        </button>
      </div>

      <div className="chat-shell">
        <div className="chat-messages">
          {messages.map((msg, idx) => (
            <div
              key={idx}
              className={`chat-bubble ${msg.role === "user" ? "user" : "assistant"}`}
            >
              <div className="chat-role">
                {msg.role === "user" ? "You" : "RAG Assistant"}
              </div>
              <div className="chat-content">{msg.content}</div>

              {msg.role === "assistant" && msg.sources?.length > 0 && (
                <div className="chat-sources">
                  <div className="chat-sources-title">Sources</div>
                  <ul>
                    {msg.sources.map((source, sIdx) => (
                      <li key={sIdx}>
                        {typeof source === "string"
                          ? source
                          : JSON.stringify(source)}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          ))}

          {loading && (
            <div className="chat-bubble assistant">
              <div className="chat-role">RAG Assistant</div>
              <div className="chat-content">Thinking…</div>
            </div>
          )}
        </div>

        <div className="chat-input-bar">
          <textarea
            className="chat-textarea"
            rows="3"
            placeholder="Ask something like: What is the invoice amount? Was there any mismatch? Summarize the PO details."
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={handleKeyDown}
          />
          <button
            className="primary-btn"
            onClick={handleSend}
            disabled={loading || !question.trim()}
          >
            Send
          </button>
        </div>
      </div>
    </div>
  );
}