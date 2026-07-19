import { Link } from "react-router";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/composites/EmptyState";
import type { EpisodeContent } from "@/lib/types";

interface EpisodeTableProps {
  episodes: EpisodeContent[];
  isLoading?: boolean;
  title?: string;
}

export function EpisodeTable({ episodes, isLoading, title = "Episodes" }: EpisodeTableProps) {
  if (isLoading) {
    return (
      <div className="flex flex-col gap-2">
        {Array.from({ length: 5 }).map((_, i) => (
          <Skeleton key={i} className="h-10 w-full" />
        ))}
      </div>
    );
  }

  if (episodes.length === 0) return <EmptyState title="No episodes" />;

  const grouped = episodes.reduce<
    Record<number, { episodeNumber: number | null; title: { id: string; primaryTitle: string } }[]>
  >((acc, ep) => {
    const season = ep.seasonNumber ?? 0;
    if (!acc[season]) acc[season] = [];
    acc[season]!.push({ episodeNumber: ep.episodeNumber, title: ep.title });
    return acc;
  }, {});

  return (
    <div className="flex flex-col gap-6">
      <h3 className="text-lg font-semibold">{title}</h3>
      {Object.entries(grouped).map(([season, eps]) => (
        <div key={season}>
          <h4 className="mb-2 text-sm font-medium text-muted">
            Season {season === "0" ? "Unknown" : season}
          </h4>
          <div className="flex flex-col gap-1">
            {eps.map((ep) => (
              <Link
                key={`${season}-${ep.episodeNumber}`}
                to={`/title/${ep.title.id}`}
                className="flex items-center gap-3 rounded-lg px-3 py-2 text-sm hover:bg-muted"
              >
                {ep.episodeNumber != null && (
                  <span className="w-6 text-right text-muted">{ep.episodeNumber}.</span>
                )}
                <span>{ep.title.primaryTitle}</span>
              </Link>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
