import { EmptyState } from "@/components/composites/EmptyState";
import type { RatingSnapshot } from "@/lib/types";

interface RatingTimelineChartProps {
  snapshots: RatingSnapshot[];
}

export function RatingTimelineChart({ snapshots }: RatingTimelineChartProps) {
  if (snapshots.length === 0) return <EmptyState title="No rating data" />;

  const maxVotes = Math.max(...snapshots.map((s) => s.numVotes), 1);

  return (
    <div>
      <h3 className="mb-4 text-lg font-semibold">Rating history</h3>
      <div className="flex items-end gap-1">
        {snapshots.map((s) => (
          <div
            key={s.snapshotDate}
            className="group relative flex flex-1 flex-col items-center"
          >
            <div
              className="w-full rounded-t bg-accent-green-bg transition-all hover:bg-accent-green-text"
              style={{ height: `${(s.numVotes / maxVotes) * 100}px` }}
            />
            <div className="mt-1 hidden text-[10px] text-muted group-hover:block">
              {s.averageRating.toFixed(1)}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
