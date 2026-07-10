function InfoRow({ label, value }) {
  return (
    <div className="info-row">
      <div className="info-label">{label}</div>
      <div className="info-value">{value ?? "—"}</div>
    </div>
  );
}

function DocumentCard({ title, doc }) {
  if (!doc) return null;

  return (
    <div className="approval-document">
      <h4>{title}</h4>

      <InfoRow label="Number" value={doc.document_number} />
      <InfoRow label="Vendor" value={doc.vendor_name} />
      <InfoRow label="GSTIN" value={doc.vendor_gstin} />
      <InfoRow label="Date" value={doc.document_date} />
      <InfoRow label="Amount" value={doc.total_value} />
    </div>
  );
}

export default function ApprovalCard({ data }) {
  if (!data)
    return <p className="muted">No approval payload available.</p>;

  return (
    <>
      <InfoRow label="Type" value={data.type} />
      <InfoRow label="Result" value={data.match_result} />
      <InfoRow label="Summary" value={data.summary} />

      <DocumentCard
        title="Purchase Order"
        doc={data.documents?.purchase_order}
      />

      <DocumentCard
        title="Invoice"
        doc={data.documents?.tax_invoice}
      />

      <DocumentCard
        title="Delivery Challan"
        doc={data.documents?.delivery_challan}
      />

      <div className="approval-actions">
        <h4>Available Actions</h4>

        <div className="action-buttons">
          {data.actions?.map((a) => (
            <button
              key={a.id}
              className="secondary-btn"
              disabled
            >
              {a.label}
            </button>
          ))}
        </div>
      </div>
    </>
  );
}