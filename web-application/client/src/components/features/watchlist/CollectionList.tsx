import { EmptyState } from "@/components/composites/EmptyState";
import { Skeleton } from "@/components/ui/skeleton";
import type { WatchlistItem } from "@/lib/types";

interface CollectionListProps {
  items: WatchlistItem[];
  isLoading?: boolean;
}

export function CollectionList({ items, isLoading }: CollectionListProps) {
  if (isLoading) {
    return (
      <div className="flex flex-col gap-2">
        {Array.from({ length: 5 }).map((_, i) => (
          <Skeleton key={i} className="h-12 w-full" />
        ))}
      </div>
    );
  }

  if (items.length === 0) return <EmptyState title="No collections yet" />;

  return (
    <div className="flex flex-col gap-2">
      {items.map((item) => (
        <div
          key={item.id}
          className="flex items-center justify-between rounded-lg border border-border p-3"
        >
          <div>
            <p className="text-sm font-medium">{item.title.primaryTitle}</p>
            {item.notes && (
              <p className="text-xs text-muted">{item.notes}</p>
            )}
          </div>
          <span className="text-xs text-muted">
            {new Date(item.addedAt).toLocaleDateString()}
          </span>
        </div>
      ))}
    </div>
  );
}
