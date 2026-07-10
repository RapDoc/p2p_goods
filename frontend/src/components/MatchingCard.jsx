function StatusBadge({ result }) {
  const success = result === "match";

  return (
    <span className={`status-chip ${success ? "success" : "error"}`}>
      {success ? "✓ MATCHED" : "✗ FAILED"}
    </span>
  );
}

export default function MatchingCard({ data }) {
  if (!data) {
    return <p className="muted">No matching result available.</p>;
  }

  return (
    <div className="matching-card">
      <div className="matching-header">
        <StatusBadge result={data.result} />
      </div>

      <div className="matching-summary">
        {data.summary}
      </div>

      <div className="match-section">
        <h4>Passed Checks</h4>

        {data.matches?.length ? (
          data.matches.map((m, idx) => (
            <div key={idx} className="match-item success">
              ✓ {m.replace("✓", "").trim()}
            </div>
          ))
        ) : (
          <div className="muted">None</div>
        )}
      </div>

      {data.mismatches?.length > 0 && (
        <div className="match-section">
          <h4>Failed Checks</h4>

          {data.mismatches.map((m, idx) => (
            <div key={idx} className="match-item error">
              ✗ {m}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}