import { EmptyState } from "@/components/composites/EmptyState";
import { RatingBadge } from "@/components/composites/RatingBadge";
import { formatVotes } from "@/lib/utils";
import type { RatingSnapshot } from "@/lib/types";

interface RatingTimelineChartProps {
  snapshots: RatingSnapshot[];
}

function sparklinePath(snapshots: RatingSnapshot[]): string {
  if (snapshots.length === 0) return "";
  const w = 100;
  const h = 16;
  const ratings = snapshots.map((s) => s.averageRating);
  const min = Math.min(...ratings);
  const max = Math.max(...ratings);
  const range = max - min || 1;
  const step = w / (snapshots.length - 1 || 1);
  return snapshots
    .map((s, i) => {
      const y = h - ((s.averageRating - min) / range) * (h - 2) - 1;
      return `${i === 0 ? "M" : "L"}${(i * step).toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
}

function monthYear(dateStr: string): string {
  const d = new Date(dateStr);
  if (Number.isNaN(d.getTime())) return dateStr;
  return d.toLocaleDateString(undefined, { month: "short", year: "2-digit" });
}

export function RatingTimelineChart({ snapshots }: RatingTimelineChartProps) {
  const sorted = [...snapshots].sort((a, b) => a.snapshotDate.localeCompare(b.snapshotDate));

  if (sorted.length === 0) return <EmptyState title="No rating data" />;

  // A single snapshot is a stat, not a timeline — show a compact card.
  if (sorted.length <= 1) {
    const s = sorted[0]!;
    return (
      <div>
        <h3 className="mb-4 text-lg font-semibold">Rating history</h3>
        <div className="inline-flex items-center gap-3 rounded-xl border border-border bg-surface px-4 py-3">
          <RatingBadge rating={s.averageRating} size="md" />
          <div>
            <p className="text-sm font-medium">
              {s.averageRating.toFixed(1)}/10 · {formatVotes(s.numVotes)} votes
            </p>
            <p className="text-xs text-muted">
              Daily snapshot {s.snapshotDate === "latest" ? "· today" : monthYear(s.snapshotDate)}
            </p>
          </div>
        </div>
      </div>
    );
  }

  const latest = sorted[sorted.length - 1]!;
  const previous = sorted[sorted.length - 2]!;
  const delta = latest.averageRating - previous.averageRating;

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-lg font-semibold">Rating history</h3>
        <div className="flex items-center gap-3 text-sm">
          <RatingBadge rating={latest.averageRating} size="md" />
          <span className="text-muted">
            {latest.averageRating.toFixed(1)}/10 · {formatVotes(latest.numVotes)} votes
          </span>
          {delta !== 0 && (
            <span
              className={
                delta > 0 ? "text-accent-green-text" : "text-accent-red-text"
              }
            >
              {delta > 0 ? "▲" : "▼"} {Math.abs(delta).toFixed(1)}
            </span>
          )}
        </div>
      </div>

      <div className="rounded-xl border border-border bg-surface px-4 py-3">
        <svg
          viewBox="0 0 100 20"
          className="h-10 w-full"
          preserveAspectRatio="none"
          role="img"
          aria-label="Average rating over time"
        >
          <polyline
            points={sparklinePath(sorted)}
            fill="none"
            stroke="var(--color-accent-green-text, #4ade80)"
            strokeWidth="1.5"
            vectorEffect="non-scaling-stroke"
            strokeLinejoin="round"
            strokeLinecap="round"
          />
        </svg>
        <div className="mt-2 flex justify-between text-[10px] text-muted">
          <span>{monthYear(sorted[0]!.snapshotDate)}</span>
          <span>{monthYear(latest.snapshotDate)}</span>
        </div>
      </div>
    </div>
  );
}