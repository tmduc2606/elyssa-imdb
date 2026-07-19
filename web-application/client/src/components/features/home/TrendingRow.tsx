import { MediaCard } from "@/components/composites/MediaCard";
import type { TitleSummary } from "@/lib/types";

interface TrendingRowProps {
  titles: TitleSummary[];
}

export function TrendingRow({ titles }: TrendingRowProps) {
  if (titles.length === 0) return null;

  return (
    <section>
      <h2 className="mb-4 text-2xl font-semibold tracking-tight">Trending</h2>
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6">
        {titles.map((title) => (
          <MediaCard
            key={title.id}
            id={title.id}
            title={title.primaryTitle}
            year={title.startYear}
            rating={title.averageRating}
            genres={title.genres}
            posterUrl={title.posterUrl}
          />
        ))}
      </div>
    </section>
  );
}
