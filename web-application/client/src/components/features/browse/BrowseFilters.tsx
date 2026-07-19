import { FilterBar } from "@/components/composites/FilterBar";
import { GENRES } from "@/lib/constants";

interface BrowseFiltersProps {
  selectedGenres: string[];
  onGenresChange: (genres: string[]) => void;
  decade: number | null;
  onDecadeChange: (decade: number | null) => void;
  sortBy: string;
  onSortChange: (sort: string) => void;
}

const genreChips = GENRES.map((g) => ({ label: g, value: g }));

const decadeChips = [
  { label: "2020s", value: "2020" },
  { label: "2010s", value: "2010" },
  { label: "2000s", value: "2000" },
  { label: "1990s", value: "1990" },
  { label: "1980s", value: "1980" },
  { label: "1970s", value: "1970" },
  { label: "1960s", value: "1960" },
  { label: "1950s", value: "1950" },
  { label: "Older", value: "older" },
];

const sortChips = [
  { label: "Rating", value: "rating" },
  { label: "Votes", value: "votes" },
  { label: "Year", value: "year" },
  { label: "Title", value: "title" },
];

export function BrowseFilters({
  selectedGenres,
  onGenresChange,
  decade,
  onDecadeChange,
  sortBy,
  onSortChange,
}: BrowseFiltersProps) {
  return (
    <div className="flex flex-col gap-4">
      <div>
        <label className="mb-2 block text-sm font-medium text-muted">Genre</label>
        <FilterBar chips={genreChips} selected={selectedGenres} onChange={onGenresChange} />
      </div>
      <div>
        <label className="mb-2 block text-sm font-medium text-muted">Decade</label>
        <FilterBar
          chips={decadeChips}
          selected={decade ? [String(decade)] : []}
          onChange={(v) => onDecadeChange(v.length > 0 ? Number(v[0]) : null)}
        />
      </div>
      <div>
        <label className="mb-2 block text-sm font-medium text-muted">Sort by</label>
        <FilterBar chips={sortChips} selected={[sortBy]} onChange={(v) => onSortChange(v[0] ?? "rating")} />
      </div>
    </div>
  );
}
