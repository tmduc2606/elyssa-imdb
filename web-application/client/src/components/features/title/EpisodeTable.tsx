import { Link } from "react-router";
import { Skeleton } from "@/components/ui/skeleton";
import type { EpisodeContent } from "@/lib/types";

interface EpisodeTableProps {
  episodes: EpisodeContent[];
  isLoading?: boolean;
  title?: string;
  isEpisodic?: boolean;
}

export function EpisodeTable({
  episodes,
  isLoading,
  title = "Episodes",
  isEpisodic = true,
}: EpisodeTableProps) {
  if (isLoading) {
    return (
      <div className="flex flex-col gap-2">
        {Array.from({ length: 5 }).map((_, i) => (
          <Skeleton key={i} className="h-10 w-full" />
        ))}
      </div>
    );
  }

  // Movies, shorts, and other non-episodic types never show this section,
  // even if a stray episode row exists in the data.
  if (!isEpisodic || episodes.length === 0) return null;

  const grouped = episodes.reduce<Record<number, EpisodeContent[]>>((acc, ep) => {
    const season = ep.seasonNumber ?? 0;
    if (!acc[season]) acc[season] = [];
    acc[season]!.push(ep);
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
            {eps.map((ep, i) =>
              ep.title ? (
                <Link
                  key={`${season}-${ep.episodeNumber ?? i}-${ep.title.id}`}
                  to={`/title/${ep.title.id}`}
                  className="flex items-center gap-3 rounded-lg px-3 py-2 text-sm hover:bg-muted"
                >
                  {ep.episodeNumber != null && (
                    <span className="w-6 text-right text-muted">{ep.episodeNumber}.</span>
                  )}
                  <span>{ep.title.primaryTitle}</span>
                </Link>
              ) : (
                <div
                  key={`${season}-${ep.episodeNumber ?? i}`}
                  className="flex items-center gap-3 rounded-lg px-3 py-2 text-sm text-muted"
                >
                  {ep.episodeNumber != null && (
                    <span className="w-6 text-right text-muted">{ep.episodeNumber}.</span>
                  )}
                  <span>
                    Episode {ep.episodeNumber ?? "—"} · S{ep.seasonNumber ?? "—"} E
                    {ep.episodeNumber ?? "—"}
                  </span>
                </div>
              ),
            )}
          </div>
        </div>
      ))}
    </div>
  );
}