import { ReactNode, useEffect, useId, useRef, useState } from "react";
import Icon from "./Icon";

/** Info popover: opens on hover, focus or click; Esc closes. Content is plain text/nodes. */
export function InfoTip({ children, label = "More information" }: { children: ReactNode; label?: string }) {
  const [open, setOpen] = useState(false);
  const id = useId();
  const ref = useRef<HTMLSpanElement | null>(null);
  useEffect(() => {
    if (!open) return;
    const off = (e: MouseEvent) => { if (!ref.current?.contains(e.target as Node)) setOpen(false); };
    document.addEventListener("mousedown", off);
    return () => document.removeEventListener("mousedown", off);
  }, [open]);
  return (
    <span className="infotip" ref={ref}
          onMouseEnter={() => setOpen(true)} onMouseLeave={() => setOpen(false)}>
      <button type="button" className="infotip-btn" aria-label={label} aria-expanded={open}
              aria-describedby={open ? id : undefined}
              onClick={(e) => { e.stopPropagation(); setOpen(true); }}
              onFocus={() => setOpen(true)} onBlur={() => setOpen(false)}
              onKeyDown={(e) => { if (e.key === "Escape") setOpen(false); }}>
        <Icon name="info" size={13} />
      </button>
      {open && <span role="tooltip" id={id} className="infotip-pop">{children}</span>}
    </span>
  );
}

/** Wraps any control with a short text tooltip (visual only; keep an aria-label on the control). */
export function Tip({ text, children }: { text: string; children: ReactNode }) {
  return <span className="tip" data-tip={text}>{children}</span>;
}
