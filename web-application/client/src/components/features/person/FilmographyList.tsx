import { Link } from "react-router";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/composites/EmptyState";
import { formatRole } from "@/lib/utils";
import type { FilmographyEntry } from "@/lib/types";

interface FilmographyListProps {
  entries: FilmographyEntry[];
  isLoading?: boolean;
}

export function FilmographyList({ entries, isLoading }: FilmographyListProps) {
  if (isLoading) {
    return (
      <div className="flex flex-col gap-2">
        {Array.from({ length: 10 }).map((_, i) => (
          <Skeleton key={i} className="h-8 w-full" />
        ))}
      </div>
    );
  }

  if (entries.length === 0) return <EmptyState title="No filmography" />;

  const grouped = entries.reduce<Record<string, FilmographyEntry[]>>((acc, entry) => {
    const year = entry.year ? String(entry.year) : "Unknown";
    if (!acc[year]) acc[year] = [];
    acc[year]!.push(entry);
    return acc;
  }, {});

  const sortedYears = Object.keys(grouped).sort((a, b) => {
    if (a === "Unknown") return 1;
    if (b === "Unknown") return -1;
    return Number(b) - Number(a);
  });

  return (
    <section>
      <h3 className="mb-4 text-lg font-semibold">Filmography</h3>
      <div className="flex flex-col gap-4">
        {sortedYears.map((year) => (
          <div key={year}>
            <h4 className="sticky top-14 mb-2 bg-canvas py-1 text-sm font-medium text-muted">
              {year}
            </h4>
            <div className="flex flex-col gap-1">
              {grouped[year]!.map((entry, i) => (
                <Link
                  key={`${entry.title.id}-${entry.category}-${i}`}
                  to={`/title/${entry.title.id}`}
                  className="flex items-center gap-3 rounded-lg px-3 py-2 text-sm hover:bg-muted"
                >
                  <span className="truncate flex-1">{entry.title.primaryTitle}</span>
                  <span className="shrink-0 text-muted">
                    {formatRole(entry.category, null, entry.character)}
                  </span>
                </Link>
              ))}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
