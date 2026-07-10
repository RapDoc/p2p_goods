const STATUS = {
  upload: {
    title: "Uploading Master PDF",
    subtitle: "Preparing workflow...",
  },

  quality: {
    title: "Checking Document Quality",
    subtitle: "Verifying scan quality and readability...",
  },

  classifier: {
    title: "Classifying Documents",
    subtitle: "Identifying PO, Invoice and Challan...",
  },

  merge: {
    title: "Grouping Documents",
    subtitle: "Organizing pages into documents...",
  },

  extraction: {
    title: "Extracting Fields",
    subtitle: "Running OCR and GPT extraction...",
  },

  normalization: {
    title: "Normalizing Data",
    subtitle: "Converting extracted data to standard schema...",
  },

  matching: {
    title: "Performing 3-Way Match",
    subtitle: "Comparing PO, Invoice and Challan...",
  },

  rag_index: {
    title: "Building Knowledge Base",
    subtitle: "Preparing document chat...",
  },

  approval: {
    title: "Generating Approval Payload",
    subtitle: "Preparing finance approval...",
  },

  communication: {
    title: "Preparing Communication",
    subtitle: "Generating supplier communication...",
  },
};

export default function WorkflowStatusCard({
  currentNode,
  status,
  interrupt,
}) {
    if (!currentNode) {
    return (
        <section className="card workflow-status-card">
        <h2>Workflow Status</h2>

        <div className="status-icon">
            📄
        </div>

        <div className="status-title">
            Ready
        </div>

        <div className="status-subtitle">
            Upload a master PDF to start the workflow.
        </div>
        </section>
    );
    }
  if (interrupt) {
    return (
      <section className="card workflow-status-card">
        <h2>Workflow Status</h2>

        <div className="status-icon">⏸</div>

        <div className="status-title">
          Waiting for Human Review
        </div>

        <div className="status-subtitle">
          {interrupt.message}
        </div>
      </section>
    );
  }

  if (status === "success") {
    return (
      <section className="card workflow-status-card">
        <h2>Workflow Status</h2>

        <div className="status-icon success">
          ✅
        </div>

        <div className="status-title">
          Workflow Completed
        </div>

        <div className="status-subtitle">
          All documents processed successfully.
        </div>
      </section>
    );
  }

  const info =
    STATUS[currentNode] ||
    {
      title: "Ready",
      subtitle: "Waiting to start workflow...",
    };

  return (
    <section className="card workflow-status-card">
      <h2>Workflow Status</h2>

      <div className="spinner">
        ⟳
      </div>

      <div className="status-title">
        {info.title}
      </div>

      <div className="status-subtitle">
        {info.subtitle}
      </div>

      <div className="loading-bar">
        <div className="loading-fill" />
      </div>
    </section>
  );
}