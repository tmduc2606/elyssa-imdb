import { useState, useCallback } from "react";
import { useSearchParams, useNavigate } from "react-router";
import { SearchAutocomplete } from "@/components/features/search/SearchAutocomplete";
import { SearchResultsGrid } from "@/components/features/search/SearchResultsGrid";
import { FacetedFilters } from "@/components/features/search/FacetedFilters";
import { useSearch } from "@/api/gold";

export function Search() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const query = searchParams.get("q") ?? "";
  const [selectedGenres, setSelectedGenres] = useState<string[]>([]);
  const [selectedType, setSelectedType] = useState<string | null>(null);

  const { data, isLoading } = useSearch(query);
  const results = data?.search?.items ?? [];

  const handleSearch = useCallback(
    (q: string) => {
      navigate(`/search?q=${encodeURIComponent(q)}`);
    },
    [navigate],
  );

  return (
    <div className="mx-auto max-w-7xl px-4 py-8">
      <SearchAutocomplete onSearch={handleSearch} className="mb-8" />
      <div className="flex flex-col gap-8 lg:flex-row">
        <aside className="w-full shrink-0 lg:w-64">
          <FacetedFilters
            selectedGenres={selectedGenres}
            onGenresChange={setSelectedGenres}
            selectedType={selectedType}
            onTypeChange={setSelectedType}
          />
        </aside>
        <div className="flex-1">
          {query && (
            <p className="mb-4 text-sm text-muted">
              Results for <span className="text-foreground">&ldquo;{query}&rdquo;</span>
            </p>
          )}
          <SearchResultsGrid results={results} isLoading={isLoading} query={query} />
        </div>
      </div>
    </div>
  );
}
