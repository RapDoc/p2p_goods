export default function PdfPreview({ file }) {
  if (!file) {
    return (
      <section className="card">
        <div className="card-header">
          <h2>PDF Preview</h2>
        </div>
        <p className="muted">Upload a master PDF to preview it here.</p>
      </section>
    );
  }

  const pdfUrl = URL.createObjectURL(file);

  return (
    <section className="card pdf-preview-card">
      <div className="card-header">
        <h2>PDF Preview</h2>
      </div>

      <div className="pdf-preview-frame">
        <iframe
          src={pdfUrl}
          title="Master PDF Preview"
          width="100%"
          height="100%"
          style={{ border: "none" }}
        />
      </div>
    </section>
  );
}