import { FilterBar } from "@/components/composites/FilterBar";
import { GENRES, TITLE_TYPES } from "@/lib/constants";

interface FacetedFiltersProps {
  selectedGenres: string[];
  onGenresChange: (genres: string[]) => void;
  selectedType: string | null;
  onTypeChange: (type: string | null) => void;
}

const genreChips = GENRES.map((g) => ({ label: g, value: g }));
const typeChips = TITLE_TYPES.map((t) => ({
  label: t.replace(/([A-Z])/g, " $1").trim(),
  value: t,
}));

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
        <FilterBar chips={genreChips} selected={selectedGenres} onChange={onGenresChange} />
      </div>
      <div>
        <label className="mb-2 block text-sm font-medium text-muted">Type</label>
        <FilterBar
          chips={typeChips}
          selected={selectedType ? [selectedType] : []}
          onChange={(v) => onTypeChange(v.length > 0 ? v[0] ?? null : null)}
        />
      </div>
    </div>
  );
}
