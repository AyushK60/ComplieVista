import type { ReactNode } from "react";

export type Tone = "exact" | "derived" | "ok" | "partial" | "blocked" | "unavailable";

export default function Badge({ tone = "unavailable", children, title }: { tone?: Tone; children: ReactNode; title?: string }) {
  return <span className={`badge ${tone}`} title={title}>{children}</span>;
}
