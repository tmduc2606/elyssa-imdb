import { useEffect, useRef, useState } from "react";
import { useLocation, useParams, useSearchParams } from "react-router";
import { SlidersHorizontal } from "lucide-react";
import { PageHeader } from "@/components/composites/PageHeader";
import { BrowseFilters } from "@/components/features/browse/BrowseFilters";
import { TitleGrid } from "@/components/features/browse/TitleGrid";
import { Button } from "@/components/ui/button";
import {
  Sheet,
  SheetTrigger,
  SheetContent,
  SheetTitle,
  SheetHeader,
} from "@/components/ui/sheet";
import { useBrowse } from "@/api/gold";

export function Browse() {
  const { slug, year } = useParams();
  const [searchParams] = useSearchParams();
  const { pathname } = useLocation();
  const isTopRated = pathname === "/browse/top-rated";
  const [selectedGenres, setSelectedGenres] = useState<string[]>(
    slug ? [slug] : [],
  );
  const [decade, setDecade] = useState<number | null>(year ? Number(year) : null);
  const [titleType, setTitleType] = useState<string | null>(
    searchParams.get("type"),
  );
  const [minRating, setMinRating] = useState<number | null>(
    isTopRated ? 8 : null,
  );
  const [sortBy, setSortBy] = useState("rating");
  const [filterOpen, setFilterOpen] = useState(false);
  const loadMoreRef = useRef<HTMLDivElement>(null);

  const { data, isLoading, hasNextPage, fetchNextPage, isFetchingNextPage } = useBrowse({
    genres: selectedGenres,
    decade,
    titleType,
    minRating,
    sortBy,
  });
  const titles = data?.pages.flatMap((p) => p.browse.items) ?? [];

  const title = isTopRated
    ? "Top rated"
    : year
      ? `${year}s`
      : slug
        ? slug.charAt(0).toUpperCase() + slug.slice(1)
        : "Browse";

  // Keep state in sync with route links (e.g. Footer ?type= / top-rated)
  useEffect(() => {
    setSelectedGenres(slug ? [slug] : []);
    setDecade(year ? Number(year) : null);
  }, [slug, year]);

  useEffect(() => {
    setTitleType(searchParams.get("type"));
  }, [searchParams]);

  useEffect(() => {
    if (isTopRated) setMinRating(8);
  }, [isTopRated]);

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

  const filters = (
    <BrowseFilters
      selectedGenres={selectedGenres}
      onGenresChange={setSelectedGenres}
      decade={decade}
      onDecadeChange={setDecade}
      titleType={titleType}
      onTitleTypeChange={setTitleType}
      minRating={minRating}
      onMinRatingChange={setMinRating}
      sortBy={sortBy}
      onSortChange={setSortBy}
    />
  );

  return (
    <div className="mx-auto max-w-7xl px-4 py-8">
      <PageHeader title={title} description="Discover titles by genre, type, decade, and rating." />
      <div className="mt-8 flex flex-col gap-8 lg:flex-row">
        <aside className="hidden w-full shrink-0 lg:block lg:w-72">{filters}</aside>
        <div className="flex-1">
          <div className="mb-4 flex items-center justify-between lg:hidden">
            <Sheet open={filterOpen} onOpenChange={setFilterOpen}>
              <SheetTrigger
                render={
                  <Button variant="outline" size="sm" aria-label="Open filters">
                    <SlidersHorizontal className="size-4" />
                    Filters
                  </Button>
                }
              />
              <SheetContent side="left" className="overflow-y-auto">
                <SheetHeader>
                  <SheetTitle className="sr-only">Filters</SheetTitle>
                </SheetHeader>
                <div className="mt-6">{filters}</div>
              </SheetContent>
            </Sheet>
          </div>
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
