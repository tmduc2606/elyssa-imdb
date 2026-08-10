import { useState } from "react";
import { NotebookPen } from "lucide-react";
import { MediaCard } from "@/components/composites/MediaCard";
import { SkeletonGrid } from "@/components/composites/SkeletonGrid";
import { EmptyState } from "@/components/composites/EmptyState";
import { Textarea } from "@/components/ui/textarea";
import { useWatchlist } from "@/hooks/useWatchlist";
import type { WatchlistItem } from "@/lib/types";

interface WatchlistGridProps {
  items: WatchlistItem[];
  isLoading?: boolean;
}

function NotesEditor({ item }: { item: WatchlistItem }) {
  const { setNotes } = useWatchlist();
  const [value, setValue] = useState(item.notes ?? "");
  const [open, setOpen] = useState(false);

  return (
    <div className="flex flex-col gap-1">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1 text-xs text-muted hover:text-foreground"
        aria-expanded={open}
      >
        <NotebookPen className="size-3" />
        {open ? "Close notes" : item.notes ? "Edit notes" : "Add notes"}
      </button>
      {open && (
        <Textarea
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onBlur={() => {
            if (value !== (item.notes ?? "")) setNotes({ entryId: item.id, notes: value });
          }}
          placeholder="Private note about this title…"
          rows={3}
          className="text-xs"
          aria-label={`Notes for ${item.title.primaryTitle}`}
        />
      )}
    </div>
  );
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
    <div className="flex flex-col gap-4">
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6">
        {items.map((item) => (
          <div key={item.id} className="flex flex-col gap-2">
            <MediaCard
              id={item.title.id}
              title={item.title.primaryTitle}
              year={item.title.startYear}
              rating={item.title.averageRating}
              genres={item.title.genres}
              posterUrl={item.title.posterUrl}
            />
            <NotesEditor item={item} />
          </div>
        ))}
      </div>
    </div>
  );
}