function renderValue(data) {
  if (data === undefined) return "undefined";
  if (data === null) return "null";
  return JSON.stringify(data, null, 2);
}

function OptionalBlock({ title, data }) {
  const hasData =
    data !== null &&
    data !== undefined &&
    (
      (Array.isArray(data) && data.length > 0) ||
      (typeof data === "object" && !Array.isArray(data) && Object.keys(data).length > 0) ||
      (typeof data === "string" && data.trim().length > 0)
    );

  if (!hasData) return null;

  return (
    <div className="sub-card">
      <div className="sub-card-title">{title}</div>
      <pre>{renderValue(data)}</pre>
    </div>
  );
}

function AlwaysBlock({ title, data }) {
  return (
    <div className="sub-card">
      <div className="sub-card-title">{title}</div>
      <pre>{renderValue(data)}</pre>
    </div>
  );
}

export default function ResultsPanel({ state }) {
  if (!state) return null;

  return (
    <section className="card results-panel">
      <div className="card-header">
        <h2>Workflow Outputs</h2>
      </div>

      <div className="results-grid">
        <OptionalBlock title="Extracted Data" data={state?.extracted_data} />
        <OptionalBlock title="Normalized Data" data={state?.normalized_data} />
        <OptionalBlock title="Matching Result" data={state?.matching_result} />

        {/* always show these two */}
        <AlwaysBlock title="Approval Payload" data={state?.approval_payload} />
        <AlwaysBlock title="Communication Payload" data={state?.communication_payload} />
      </div>
    </section>
  );
}