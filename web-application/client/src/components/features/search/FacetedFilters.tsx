import { FilterBar } from "@/components/composites/FilterBar";
import { GENRE_CHIPS, TYPE_CHIPS } from "@/lib/constants";

interface FacetedFiltersProps {
  selectedGenres: string[];
  onGenresChange: (genres: string[]) => void;
  selectedType: string | null;
  onTypeChange: (type: string | null) => void;
}

export function FacetedFilters({
  selectedGenres,
  onGenresChange,
  selectedType,
  onTypeChange,
}: FacetedFiltersProps) {
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
          selected={selectedType ? [selectedType] : []}
          onChange={(v) => onTypeChange(v.length > 0 ? v[0] ?? null : null)}
        />
      </div>
    </div>
  );
}
