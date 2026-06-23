export default function JsonViewer({ data }) {
  return (
    <section className="card">
      <div className="card-header">
        <h2>Raw State JSON</h2>
      </div>
      <pre className="json-viewer">
        {data ? JSON.stringify(data, null, 2) : "No workflow state yet"}
      </pre>
    </section>
  );
}