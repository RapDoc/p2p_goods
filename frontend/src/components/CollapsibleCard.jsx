import { useState } from "react";

export default function CollapsibleCard({
  title,
  defaultOpen = false,
  children,
}) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <section className="card">
      <div
        className="collapse-header"
        onClick={() => setOpen(!open)}
      >
        <h2>{title}</h2>

        <span className={`collapse-arrow ${open ? "open" : ""}`}>
          ▼
        </span>
      </div>

      {open && (
        <div className="collapse-body">
          {children}
        </div>
      )}
    </section>
  );
}