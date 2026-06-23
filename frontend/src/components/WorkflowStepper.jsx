const STEPS = [
  { key: "upload", label: "Upload" },
  { key: "quality", label: "Quality" },
  { key: "classifier", label: "Classification" },
  { key: "decision_1", label: "Decision 1" },
  { key: "extraction", label: "Extraction" },
  { key: "normalization", label: "Normalization" },
  { key: "matching", label: "3-Way Match" },
  { key: "decision_2", label: "Decision 2" },
  { key: "final", label: "Final Outcome" },
];

function getStepState(index, status, state, interrupt, simulatedStep) {
  // While workflow is running, use simulated progress
  if (simulatedStep > 0 && !interrupt && status !== "success" && status !== "rejected") {
    if (index + 1 < simulatedStep) return "done";
    if (index + 1 === simulatedStep) return "active";
    return "pending";
  }

  // Once real backend result arrives, use actual state
  const stepKey = STEPS[index].key;

  if (!status) return "pending";

  if (stepKey === "upload") return state ? "done" : "pending";
  if (stepKey === "quality" && state?.quality_pages?.length) return "done";
  if (stepKey === "classifier" && state?.classified_pages?.length) return "done";
  if (stepKey === "decision_1" && state?.decision_1_passed !== null) {
    return interrupt?.decision === "decision_1_failed" ? "active" : "done";
  }
  if (stepKey === "extraction" && state?.grouped_documents?.length) return "done";
  if (stepKey === "normalization" && state?.normalized_data?.length) return "done";
  if (stepKey === "matching" && state?.matching_result && Object.keys(state.matching_result).length) return "done";
  if (stepKey === "decision_2" && state?.decision_2_passed !== null) {
    return interrupt?.decision === "decision_2_failed" ? "active" : "done";
  }
  if (stepKey === "final" && (status === "success" || status === "rejected")) return "done";

  return "pending";
}

export default function WorkflowStepper({ status, state, interrupt, simulatedStep }) {
  return (
    <section className="card">
      <div className="card-header">
        <h2>Workflow Progress</h2>
      </div>

      <div className="stepper">
        {STEPS.map((step, index) => {
          const stepState = getStepState(index, status, state, interrupt, simulatedStep);

          return (
            <div key={step.key} className="step-wrapper">
              <div className={`step ${stepState}`}>
                <div className="step-circle">{index + 1}</div>
                <div className="step-label">{step.label}</div>
              </div>
              {index < STEPS.length - 1 && <div className="step-line" />}
            </div>
          );
        })}
      </div>
    </section>
  );
}