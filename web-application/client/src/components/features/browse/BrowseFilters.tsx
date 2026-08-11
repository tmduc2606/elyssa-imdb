import { FilterBar } from "@/components/composites/FilterBar";
import { DECADE_CHIPS, GENRE_CHIPS, MIN_RATING_CHIPS, SORT_CHIPS, TYPE_CHIPS } from "@/lib/constants";

interface BrowseFiltersProps {
  selectedGenres: string[];
  onGenresChange: (genres: string[]) => void;
  decade: number | null;
  onDecadeChange: (decade: number | null) => void;
  titleType: string | null;
  onTitleTypeChange: (titleType: string | null) => void;
  minRating: number | null;
  onMinRatingChange: (minRating: number | null) => void;
  sortBy: string;
  onSortChange: (sort: string) => void;
}

export function BrowseFilters({
  selectedGenres,
  onGenresChange,
  decade,
  onDecadeChange,
  titleType,
  onTitleTypeChange,
  minRating,
  onMinRatingChange,
  sortBy,
  onSortChange,
}: BrowseFiltersProps) {
  return (
    <div className="flex flex-col gap-4">
      <div>
        <label className="mb-2 block text-sm font-medium text-muted">Genre</label>
        <FilterBar chips={GENRE_CHIPS} selected={selectedGenres} onChange={onGenresChange} />
      </div>
      <div>
        <label className="mb-2 block text-sm font-medium text-muted">Type</label>
        <FilterBar
          chips={TYPE_CHIPS}
          selected={titleType ? [titleType] : []}
          onChange={(v) => onTitleTypeChange(v.length > 0 ? v[0] ?? null : null)}
        />
      </div>
      <div>
        <label className="mb-2 block text-sm font-medium text-muted">Decade</label>
        <FilterBar
          chips={DECADE_CHIPS}
          selected={decade ? [String(decade)] : []}
          onChange={(v) => onDecadeChange(v.length > 0 ? Number(v[0]) : null)}
        />
      </div>
      <div>
        <label className="mb-2 block text-sm font-medium text-muted">Min rating</label>
        <FilterBar
          chips={MIN_RATING_CHIPS}
          selected={minRating != null ? [String(minRating)] : []}
          onChange={(v) =>
            onMinRatingChange(v.length > 0 && v[0] ? Number(v[0]) : null)
          }
        />
      </div>
      <div>
        <label className="mb-2 block text-sm font-medium text-muted">Sort by</label>
        <FilterBar chips={SORT_CHIPS} selected={[sortBy]} onChange={(v) => onSortChange(v[0] ?? "rating")} />
      </div>
    </div>
  );
}
