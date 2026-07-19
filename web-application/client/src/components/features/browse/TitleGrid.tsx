import { MediaCard } from "@/components/composites/MediaCard";
import { SkeletonGrid } from "@/components/composites/SkeletonGrid";
import { EmptyState } from "@/components/composites/EmptyState";
import type { TitleSummary } from "@/lib/types";

interface TitleGridProps {
  titles: TitleSummary[];
  isLoading: boolean;
}

export function TitleGrid({ titles, isLoading }: TitleGridProps) {
  if (isLoading) return <SkeletonGrid count={24} />;

  if (titles.length === 0) {
    return (
      <EmptyState
        title="No titles found"
        description="Try adjusting your filters to see more results."
      />
    );
  }

  return (
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
  );
}
