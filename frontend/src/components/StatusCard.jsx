export default function StatusCard({ threadId, status, interrupt }) {
  const statusClass =
    status === "success"
      ? "status success"
      : status === "rejected"
      ? "status rejected"
      : status === "interrupted"
      ? "status interrupted"
      : "status neutral";

  return (
    <section className="card">
      <div className="card-header">
        <h2>Workflow Status</h2>
      </div>

      <div className="status-grid">
        <div>
          <div className="label">Thread ID</div>
          <div className="value mono">{threadId || "-"}</div>
        </div>

        <div>
          <div className="label">Status</div>
          <div className={statusClass}>{status || "Not started"}</div>
        </div>

        <div>
          <div className="label">Human Review</div>
          <div className="value">
            {interrupt ? interrupt.decision : "Not required"}
          </div>
        </div>
      </div>
    </section>
  );
}