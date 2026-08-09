import { useState, useEffect, useRef } from "react";
import { useParams } from "react-router";
import { PageHeader } from "@/components/composites/PageHeader";
import { BrowseFilters } from "@/components/features/browse/BrowseFilters";
import { TitleGrid } from "@/components/features/browse/TitleGrid";
import { useBrowse } from "@/api/gold";

export function Browse() {
  const { slug, year } = useParams();
  const [selectedGenres, setSelectedGenres] = useState<string[]>(
    slug ? [slug] : [],
  );
  const [decade, setDecade] = useState<number | null>(year ? Number(year) : null);
  const [sortBy, setSortBy] = useState("rating");
  const loadMoreRef = useRef<HTMLDivElement>(null);

  const { data, isLoading, hasNextPage, fetchNextPage, isFetchingNextPage } = useBrowse({
    genres: selectedGenres,
    decade,
    sortBy,
  });
  const titles = data?.pages.flatMap((p) => p.browse.items) ?? [];

  const title = year
    ? `${year}s`
    : slug
      ? slug.charAt(0).toUpperCase() + slug.slice(1)
      : "Browse";

  useEffect(() => {
    const el = loadMoreRef.current;
    if (!el || !hasNextPage) return;
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0]?.isIntersecting && !isFetchingNextPage) {
          fetchNextPage();
        }
      },
      { rootMargin: "200px" },
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, [hasNextPage, fetchNextPage, isFetchingNextPage]);

  return (
    <div className="mx-auto max-w-7xl px-4 py-8">
      <PageHeader title={title} description="Discover titles by genre, decade, and rating." />
      <div className="mt-8 flex flex-col gap-8 lg:flex-row">
        <aside className="w-full shrink-0 lg:w-72">
          <BrowseFilters
            selectedGenres={selectedGenres}
            onGenresChange={setSelectedGenres}
            decade={decade}
            onDecadeChange={setDecade}
            sortBy={sortBy}
            onSortChange={setSortBy}
          />
        </aside>
        <div className="flex-1">
          <TitleGrid titles={titles} isLoading={isLoading} />
          <div ref={loadMoreRef} className="mt-6 flex justify-center">
            {hasNextPage && (
              <button
                type="button"
                onClick={() => fetchNextPage()}
                disabled={isFetchingNextPage}
                className="rounded-lg border border-border px-4 py-2 text-sm"
              >
                {isFetchingNextPage ? "Loading…" : "Load more"}
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
