function renderValue(value) {
  if (value === undefined || value === null || value === "") return "—";
  if (Array.isArray(value)) {
    return value.length ? value.join(", ") : "—";
  }
  if (typeof value === "object") {
    return JSON.stringify(value, null, 2);
  }
  return String(value);
}

function InfoRow({ label, value }) {
  return (
    <div className="info-row">
      <div className="info-label">{label}</div>
      <div className="info-value">{renderValue(value)}</div>
    </div>
  );
}

function findNormalizedDoc(state, targetType) {
  const items = Array.isArray(state?.normalized_data) ? state.normalized_data : [];
  return items.find((item) => item?.document_type === targetType) || null;
}

function findGroupedDoc(state, targetType) {
  const items = Array.isArray(state?.grouped_documents) ? state.grouped_documents : [];
  return items.find((item) => item?.document_type === targetType) || null;
}

function PoCard({ state }) {
  const doc = findNormalizedDoc(state, "purchase_order");
  const grouped = findGroupedDoc(state, "purchase_order");
  const fields = doc?.normalized_fields || {};

  return (
    <div className="sub-card doc-summary-card">
      <div className="sub-card-title">PO Information</div>

      <InfoRow label="Document Name" value={doc?.document_name || grouped?.document_name} />
      <InfoRow label="PO Number" value={fields.po_number} />
      <InfoRow label="PO Date" value={fields.po_date} />
      <InfoRow label="Supplier" value={fields.supplier_name} />
      <InfoRow label="Supplier GSTIN" value={fields.supplier_gstin} />
      <InfoRow label="Buyer" value={fields.buyer_name} />
      <InfoRow label="Total Order Value" value={fields.total_order_value} />
      <InfoRow label="Taxes" value={fields.taxes} />
      <InfoRow label="Payment Terms" value={fields.payment_terms} />
      <InfoRow label="Delivery Schedule" value={fields.delivery_schedule} />
      <InfoRow
        label="Pages"
        value={
          grouped?.start_page != null && grouped?.end_page != null
            ? `${grouped.start_page} - ${grouped.end_page}`
            : "—"
        }
      />

      <div className="doc-items-section">
        <div className="doc-items-title">Item Details</div>
        {Array.isArray(fields.item_details) && fields.item_details.length > 0 ? (
          <div className="item-table-wrap">
            <table className="item-table">
              <thead>
                <tr>
                  <th>Description</th>
                  <th>Qty</th>
                  <th>Unit Price</th>
                </tr>
              </thead>
              <tbody>
                {fields.item_details.map((item, idx) => (
                  <tr key={idx}>
                    <td>{item.description || "—"}</td>
                    <td>{item.quantity ?? "—"}</td>
                    <td>{item.unit_price ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="muted">No item details available.</div>
        )}
      </div>
    </div>
  );
}

function InvoiceCard({ state }) {
  const doc = findNormalizedDoc(state, "tax_invoice");
  const grouped = findGroupedDoc(state, "tax_invoice");
  const fields = doc?.normalized_fields || {};

  return (
    <div className="sub-card doc-summary-card">
      <div className="sub-card-title">Invoice Information</div>

      <InfoRow label="Document Name" value={doc?.document_name || grouped?.document_name} />
      <InfoRow label="Invoice Number" value={fields.invoice_number} />
      <InfoRow label="Invoice Date" value={fields.invoice_date} />
      <InfoRow label="Quantity" value={fields.quantity} />
      <InfoRow label="Unit Price" value={fields.unit_price} />
      <InfoRow label="Taxable Value" value={fields.taxable_value} />
      <InfoRow label="Discount" value={fields.discount} />
      <InfoRow label="GST Rates" value={fields.gst_rates} />
      <InfoRow label="Total Invoice Value" value={fields.total_invoice_value} />
      <InfoRow
        label="Pages"
        value={
          grouped?.start_page != null && grouped?.end_page != null
            ? `${grouped.start_page} - ${grouped.end_page}`
            : "—"
        }
      />
    </div>
  );
}

function ChallanCard({ state }) {
  const doc = findNormalizedDoc(state, "delivery_challan");
  const grouped = findGroupedDoc(state, "delivery_challan");
  const fields = doc?.normalized_fields || {};

  return (
    <div className="sub-card doc-summary-card">
      <div className="sub-card-title">Challan Information</div>

      <InfoRow label="Document Name" value={doc?.document_name || grouped?.document_name} />
      <InfoRow label="Challan Number" value={fields.delivery_challan_number} />
      <InfoRow label="Issue Date" value={fields.date_of_issue} />
      <InfoRow label="Supplier Name" value={fields.supplier_details?.name || fields.canonical_vendor_name} />
      <InfoRow label="Supplier GSTIN" value={fields.supplier_details?.gstin || fields.vendor_gstin} />
      <InfoRow label="Supplier Address" value={fields.supplier_details?.address} />
      <InfoRow
        label="Pages"
        value={
          grouped?.start_page != null && grouped?.end_page != null
            ? `${grouped.start_page} - ${grouped.end_page}`
            : "—"
        }
      />
    </div>
  );
}

function JsonBlock({ title, data }) {
  return (
    <div className="sub-card">
      <div className="sub-card-title">{title}</div>
      <pre>{data ? JSON.stringify(data, null, 2) : "null"}</pre>
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

      <div className="results-grid results-grid-docs">
        <PoCard state={state} />
        <InvoiceCard state={state} />
        <ChallanCard state={state} />
      </div>

      <div className="results-grid extra-results-grid">
        <JsonBlock title="Matching Result" data={state?.matching_result} />
        <JsonBlock title="Approval Payload" data={state?.approval_payload} />
        <JsonBlock title="Communication Payload" data={state?.communication_payload} />
      </div>
    </section>
  );
}