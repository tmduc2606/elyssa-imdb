import { MediaCard } from "@/components/composites/MediaCard";
import { SkeletonGrid } from "@/components/composites/SkeletonGrid";
import { EmptyState } from "@/components/composites/EmptyState";
import type { TitleSummary } from "@/lib/types";

interface SearchResultsGridProps {
  results: TitleSummary[];
  isLoading: boolean;
  query: string;
}

export function SearchResultsGrid({ results, isLoading, query }: SearchResultsGridProps) {
  if (isLoading) return <SkeletonGrid count={12} />;

  if (results.length === 0) {
    return (
      <EmptyState
        title="No results found"
        description={`We couldn't find anything for "${query}". Try a different search term.`}
      />
    );
  }

  return (
    <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6">
      {results.map((title) => (
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
