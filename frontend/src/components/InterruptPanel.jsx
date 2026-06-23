import { useState } from "react";

export default function InterruptPanel({
  interrupt,
  loading,
  onResumeDecision1,
  onResumeDecision2,
}) {
  const [files, setFiles] = useState([]);
  const [reason, setReason] = useState("");

  if (!interrupt) return null;

  return (
    <section className="card warning-card">
      <div className="card-header">
        <h2>Human Review Required</h2>
      </div>

      <div className="interrupt-meta">
        <p><strong>Decision:</strong> {interrupt.decision}</p>
        <p><strong>Reason:</strong> {interrupt.reason}</p>
        <p><strong>Message:</strong> {interrupt.message}</p>
      </div>

      {interrupt.decision === "decision_1_failed" && (
        <div className="interrupt-section">
          <h3>Reupload Required Documents</h3>

          <div className="chip-list">
            {(interrupt.failed_doc_types || []).map((doc, idx) => (
              <span className="chip" key={idx}>{doc}</span>
            ))}
          </div>

          <input
            type="file"
            multiple
            accept=".pdf"
            onChange={(e) => setFiles(Array.from(e.target.files || []))}
          />

          {files.length > 0 && (
            <ul className="file-list">
              {files.map((file, idx) => (
                <li key={idx}>{file.name}</li>
              ))}
            </ul>
          )}

          <button
            className="primary-btn"
            disabled={loading || files.length === 0}
            onClick={() => onResumeDecision1(files)}
          >
            {loading ? "Submitting..." : "Submit Reuploaded Files"}
          </button>
        </div>
      )}

      {interrupt.decision === "decision_2_failed" && (
        <div className="interrupt-section">
          <h3>Approval Decision</h3>

          {interrupt.communication_payload && (
            <div className="sub-card">
              <div className="sub-card-title">Communication Payload</div>
              <pre>{JSON.stringify(interrupt.communication_payload, null, 2)}</pre>
            </div>
          )}

          <textarea
            className="text-area"
            rows="4"
            placeholder="Enter review reason..."
            value={reason}
            onChange={(e) => setReason(e.target.value)}
          />

          <div className="button-row">
            <button
              className="primary-btn"
              disabled={loading}
              onClick={() => onResumeDecision2(true, reason)}
            >
              Approve
            </button>
            <button
              className="danger-btn"
              disabled={loading}
              onClick={() => onResumeDecision2(false, reason)}
            >
              Reject
            </button>
          </div>
        </div>
      )}
    </section>
  );
}