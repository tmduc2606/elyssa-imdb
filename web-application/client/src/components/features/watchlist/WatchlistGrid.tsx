import { MediaCard } from "@/components/composites/MediaCard";
import { SkeletonGrid } from "@/components/composites/SkeletonGrid";
import { EmptyState } from "@/components/composites/EmptyState";
import type { WatchlistItem } from "@/lib/types";

interface WatchlistGridProps {
  items: WatchlistItem[];
  isLoading?: boolean;
}

export function WatchlistGrid({ items, isLoading }: WatchlistGridProps) {
  if (isLoading) return <SkeletonGrid count={12} />;

  if (items.length === 0) {
    return (
      <EmptyState
        title="Your watchlist is empty"
        description="Save titles while browsing to build your collection."
      />
    );
  }

  return (
    <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6">
      {items.map((item) => (
        <MediaCard
          key={item.id}
          id={item.title.id}
          title={item.title.primaryTitle}
          year={item.title.startYear}
          rating={item.title.averageRating}
          genres={item.title.genres}
          posterUrl={item.title.posterUrl}
        />
      ))}
    </div>
  );
}
