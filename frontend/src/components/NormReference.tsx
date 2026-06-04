import { useState } from "react";
import type { NormReference as NormReferenceType } from "../types";
import "./NormReference.css";

interface Props {
  reference: NormReferenceType;
}

export default function NormReference({ reference }: Props) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="norm-ref">
      <button
        className="norm-ref__header"
        onClick={() => setExpanded((v) => !v)}
        aria-expanded={expanded}
      >
        <span className="norm-ref__title">{reference.title}</span>
        <span className="norm-ref__article">{reference.article}</span>
        <span className="norm-ref__chevron">{expanded ? "▲" : "▼"}</span>
      </button>

      {expanded && (
        <div className="norm-ref__body">
          <blockquote className="norm-ref__excerpt">"{reference.excerpt}"</blockquote>
        </div>
      )}
    </div>
  );
}
