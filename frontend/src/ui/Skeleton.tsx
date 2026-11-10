/** Shimmer placeholder bars (replaces bare "loading…" text). Announced once via the live region. */
export default function Skeleton({ rows = 4, label = "Loading" }: { rows?: number; label?: string }) {
  return (
    <div className="skeleton" role="status" aria-label={label}>
      {Array.from({ length: rows }, (_, i) => <i key={i} style={{ width: `${92 - ((i * 17) % 40)}%` }} />)}
    </div>
  );
}
