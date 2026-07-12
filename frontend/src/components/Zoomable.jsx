import React, { useState, useEffect } from "react";
import { createPortal } from "react-dom";

// A click-to-enlarge image (spec 07 §2/§5). Shows the thumbnail inline; on click opens a
// full-screen lightbox rendered via a portal (so no parent CSS constrains the enlarged image).
// Close on backdrop click, the × button, or Escape.
export default function Zoomable({ src, alt = "", caption }) {
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (!open) return;
    const onKey = (e) => e.key === "Escape" && setOpen(false);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  return (
    <>
      <img src={src} alt={alt} className="zoomable" loading="lazy"
        title="Click to enlarge" onClick={() => setOpen(true)} />
      {open && createPortal(
        <div className="lightbox" role="dialog" aria-modal="true" onClick={() => setOpen(false)}>
          <button className="lightbox-close" aria-label="Close" onClick={() => setOpen(false)}>×</button>
          <figure className="lightbox-fig" onClick={(e) => e.stopPropagation()}>
            <img src={src} alt={alt} />
            {caption && <figcaption>{caption}</figcaption>}
          </figure>
        </div>,
        document.body,
      )}
    </>
  );
}
