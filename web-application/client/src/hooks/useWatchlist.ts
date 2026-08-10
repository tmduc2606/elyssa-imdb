import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { authApiFetch } from "@/lib/authApi";
import type { WatchlistItem } from "@/lib/types";

export function useWatchlist() {
  const queryClient = useQueryClient();

  const query = useQuery<WatchlistItem[]>({
    queryKey: ["watchlist"],
    queryFn: () => authApiFetch<WatchlistItem[]>("/watchlist"),
    staleTime: 30_000,
  });

  const addMutation = useMutation({
    mutationFn: (args: { tconst: string; title?: unknown }) =>
      authApiFetch("/watchlist", {
        method: "POST",
        body: JSON.stringify(args),
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["watchlist"] }),
  });

  const removeMutation = useMutation({
    mutationFn: (entryId: string) =>
      authApiFetch(`/watchlist/${entryId}`, { method: "DELETE" }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["watchlist"] }),
  });

  const notesMutation = useMutation({
    mutationFn: (args: { entryId: string; notes: string }) =>
      authApiFetch(`/watchlist/${args.entryId}`, {
        method: "PATCH",
        body: JSON.stringify({ notes: args.notes }),
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["watchlist"] }),
  });

  return {
    items: query.data ?? [],
    isLoading: query.isLoading,
    add: addMutation.mutate,
    remove: removeMutation.mutate,
    setNotes: notesMutation.mutate,
    isAdding: addMutation.isPending,
    isRemoving: removeMutation.isPending,
  };
}

export function useWatchlistState(tconst: string) {
  const { items, isLoading, add, remove, isAdding, isRemoving } = useWatchlist();
  const entry = items.find((i) => i.title.id === tconst);
  return {
    isSaved: Boolean(entry),
    entry,
    saveCount: items.length,
    isLoading,
    add,
    remove,
    isAdding,
    isRemoving,
  };
}