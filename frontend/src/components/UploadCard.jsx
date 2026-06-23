export default function UploadCard({
  file,
  setFile,
  onStart,
  loading,
}) {
  return (
    <section className="card">
      <div className="card-header">
        <h2>Upload Master PDF</h2>
      </div>

      <div className="upload-box">
        <input
          type="file"
          accept=".pdf"
          onChange={(e) => setFile(e.target.files?.[0] || null)}
        />
        <p className="muted">
          Upload the combined PO / Invoice / Challan PDF to start the workflow.
        </p>

        {file && (
          <div className="file-pill">
            <span>{file.name}</span>
          </div>
        )}

        <button
          className="primary-btn"
          onClick={onStart}
          disabled={loading}
        >
          {loading ? "Processing..." : "Start Workflow"}
        </button>
      </div>
    </section>
  );
}