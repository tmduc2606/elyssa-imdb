import { MediaCard } from "@/components/composites/MediaCard";
import type { TitleSummary } from "@/lib/types";

interface SimilarTitlesRowProps {
  titles: TitleSummary[];
}

export function SimilarTitlesRow({ titles }: SimilarTitlesRowProps) {
  if (titles.length === 0) return null;

  return (
    <section>
      <h3 className="mb-4 text-lg font-semibold">Similar titles</h3>
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
