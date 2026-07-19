import { useState } from "react";
import { useParams } from "react-router";
import { PageHeader } from "@/components/composites/PageHeader";
import { BrowseFilters } from "@/components/features/browse/BrowseFilters";
import { TitleGrid } from "@/components/features/browse/TitleGrid";
import type { TitleSummary } from "@/lib/types";

export function Browse() {
  const { slug, year } = useParams();
  const [selectedGenres, setSelectedGenres] = useState<string[]>(
    slug ? [slug] : [],
  );
  const [decade, setDecade] = useState<number | null>(year ? Number(year) : null);
  const [sortBy, setSortBy] = useState("rating");

  const titles: TitleSummary[] = [];
  const isLoading = false;

  const title = year
    ? `${year}s`
    : slug
      ? slug.charAt(0).toUpperCase() + slug.slice(1)
      : "Browse";

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
        </div>
      </div>
    </div>
  );
}
