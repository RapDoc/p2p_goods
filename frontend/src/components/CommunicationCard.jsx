export default function CommunicationCard({ data }) {
  if (!data) {
    return (
      <p className="muted">
        Communication payload will appear if the workflow is rejected.
      </p>
    );
  }

  return (
    <>
      <div className="info-row">
        <div className="info-label">To</div>
        <div className="info-value">{data.to}</div>
      </div>

      <div className="info-row">
        <div className="info-label">Subject</div>
        <div className="info-value">{data.subject}</div>
      </div>

      <div className="email-preview">
        {data.body}
      </div>
    </>
  );
}