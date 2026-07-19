import { MediaCard } from "@/components/composites/MediaCard";
import { SkeletonGrid } from "@/components/composites/SkeletonGrid";
import { EmptyState } from "@/components/composites/EmptyState";
import type { TitleSummary } from "@/lib/types";

interface KnownForGridProps {
  titles: TitleSummary[];
  isLoading?: boolean;
}

export function KnownForGrid({ titles, isLoading }: KnownForGridProps) {
  if (isLoading) return <SkeletonGrid count={6} />;
  if (titles.length === 0) return <EmptyState title="No known titles" />;

  return (
    <section>
      <h3 className="mb-4 text-lg font-semibold">Known for</h3>
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5">
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
