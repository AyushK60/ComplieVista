import Badge, { Tone } from "./Badge";
import { InfoTip } from "./Tooltip";

/**
 * Plain-language names for the honesty vocabulary. The raw code stays visible in
 * Technical mode (and in the tooltip) so nothing is hidden, only translated.
 */
type Entry = { label: string; tone: Tone; help: string };

export const STATUS: Record<string, Entry> = {
  EXACT: { label: "Exact", tone: "exact", help: "Taken directly from the tool's own output. Nothing was estimated or reconstructed." },
  DERIVED: { label: "Derived", tone: "derived", help: "Computed by CompileVista from exact data, for example an edge inferred from a block terminator." },
  APPROXIMATE: { label: "Approximate", tone: "derived", help: "A best-effort mapping. It may be off by a few positions." },
  UNAVAILABLE: { label: "Not available", tone: "unavailable", help: "This tool does not produce this information for this program, so none is shown." },
  AVAILABLE: { label: "Available", tone: "ok", help: "The real tool ran and produced this artifact." },
  PARTIAL: { label: "Partial", tone: "partial", help: "Some of this artifact was produced; the rest is capped or missing. The view says what." },
  BLOCKED: { label: "Blocked", tone: "blocked", help: "This step was refused by a safety rule, for example running unreviewed code." },
  OBSERVED: { label: "Observed", tone: "exact", help: "Recorded while the program ran. It reflects what actually happened in that run." },
  TRACE_TRUSTED: { label: "Trusted trace", tone: "exact", help: "This is a curated program, run with the observer outside the program's reach, so the recording is reliable." },
  UNTRUSTED_TARGET: { label: "Untrusted program", tone: "blocked", help: "This program ran in the same container as the recorder. It could have tampered with the recording, so the events are not guaranteed genuine." },
  INTEGRITY_SUSPECT: { label: "Integrity warning", tone: "blocked", help: "The recording's integrity checks failed. Treat the events with suspicion." },
};

export default function StatusBadge({ code, label, extra }: { code: string; label?: string; extra?: string }) {
  const e = STATUS[code] ?? { label: code, tone: "unavailable" as Tone, help: "" };
  return (
    <span className="statusbadge" data-status={code}>
      <Badge tone={e.tone}>{label ?? e.label}</Badge>
      <span className="tech-only statuscode"><code>{code}</code></span>
      {e.help && <InfoTip label={`What does ${label ?? e.label} mean?`}>{e.help}{extra ? ` ${extra}` : ""}</InfoTip>}
    </span>
  );
}
