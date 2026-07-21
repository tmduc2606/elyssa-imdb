import { PageHeader } from "@/components/composites/PageHeader";
import { WatchlistGrid } from "@/components/features/watchlist/WatchlistGrid";
import { useWatchlist } from "@/hooks/useWatchlist";

export function Watchlist() {
  const { items, isLoading } = useWatchlist();

  return (
    <div className="mx-auto max-w-7xl px-4 py-8">
      <PageHeader title="Watchlist" />
      <div className="mt-8">
        <WatchlistGrid items={items} isLoading={isLoading} />
      </div>
    </div>
  );
}
