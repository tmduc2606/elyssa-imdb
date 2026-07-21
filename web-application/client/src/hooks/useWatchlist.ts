import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { AUTH_URL } from "@/lib/constants";
import { getAccessToken } from "@/lib/urql";
import type { WatchlistItem } from "@/lib/types";

async function authFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const token = getAccessToken();
  const res = await fetch(`${AUTH_URL}${path}`, {
    ...options,
    credentials: "include",
    headers: {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      "Content-Type": "application/json",
      ...(options?.headers ?? {}),
    },
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ message: "Request failed" }));
    throw new Error(err.message);
  }
  return res.json();
}

export function useWatchlist() {
  const queryClient = useQueryClient();

  const query = useQuery<WatchlistItem[]>({
    queryKey: ["watchlist"],
    queryFn: () => authFetch<WatchlistItem[]>("/watchlist"),
    staleTime: 30_000,
  });

  const addMutation = useMutation({
    mutationFn: (args: { tconst: string; title?: unknown }) =>
      authFetch("/watchlist", {
        method: "POST",
        body: JSON.stringify(args),
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["watchlist"] }),
  });

  const removeMutation = useMutation({
    mutationFn: (entryId: string) =>
      authFetch(`/watchlist/${entryId}`, { method: "DELETE" }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["watchlist"] }),
  });

  return {
    items: query.data ?? [],
    isLoading: query.isLoading,
    add: addMutation.mutate,
    remove: removeMutation.mutate,
    isAdding: addMutation.isPending,
    isRemoving: removeMutation.isPending,
  };
}
