import type { ReactNode } from "react";

export type TabItem<T extends string> = { id: T; label: ReactNode; hidden?: boolean };

/** The one tab strip: underline style, role=tablist, arrow-key navigation. */
export default function Tabs<T extends string>({ items, value, onChange, label, className = "" }: {
  items: Array<TabItem<T>>; value: T; onChange: (id: T) => void; label: string; className?: string;
}) {
  const visible = items.filter((i) => !i.hidden);
  const onKey = (e: React.KeyboardEvent) => {
    if (e.key !== "ArrowRight" && e.key !== "ArrowLeft") return;
    const i = visible.findIndex((t) => t.id === value);
    const n = visible[(i + (e.key === "ArrowRight" ? 1 : visible.length - 1)) % visible.length];
    onChange(n.id);
    e.preventDefault();
    const el = (e.currentTarget as HTMLElement).querySelectorAll<HTMLElement>('[role="tab"]')[visible.indexOf(n)];
    el?.focus();
  };
  return (
    <div role="tablist" aria-label={label} className={`tabs ${className}`} onKeyDown={onKey}>
      {visible.map((t) => (
        <button key={t.id} type="button" role="tab" aria-selected={value === t.id}
                className={value === t.id ? "active" : ""} onClick={() => onChange(t.id)}>
          {t.label}
        </button>
      ))}
    </div>
  );
}
