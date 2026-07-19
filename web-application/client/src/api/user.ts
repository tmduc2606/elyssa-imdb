import { useQuery, useMutation, type DefaultError } from "@tanstack/react-query";
import { AUTH_URL, QUERY_STALE_TIME } from "@/lib/constants";
import type { User, WatchlistItem } from "@/lib/types";

async function fetchApi<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${AUTH_URL}${path}`, {
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.message ?? `Request failed: ${res.status}`);
  }
  return res.json();
}

export function useCurrentUser() {
  return useQuery<User, DefaultError>({
    queryKey: ["currentUser"],
    queryFn: () => fetchApi<User>("/me"),
    staleTime: QUERY_STALE_TIME.watchlist,
    retry: false,
  });
}

export function useWatchlist() {
  return useQuery<WatchlistItem[], DefaultError>({
    queryKey: ["watchlist"],
    queryFn: () => fetchApi<WatchlistItem[]>("/watchlist"),
    staleTime: QUERY_STALE_TIME.watchlist,
  });
}

export function useAddToWatchlist() {
  return useMutation<WatchlistItem, DefaultError, string>({
    mutationFn: (tconst) =>
      fetchApi<WatchlistItem>("/watchlist", {
        method: "POST",
        body: JSON.stringify({ tconst }),
      }),
  });
}

export function useRemoveFromWatchlist() {
  return useMutation<void, DefaultError, string>({
    mutationFn: (id) =>
      fetchApi<void>(`/watchlist/${id}`, { method: "DELETE" }),
  });
}

export function useLogin() {
  return useMutation<
    { accessToken: string },
    DefaultError,
    { email: string; password: string }
  >({
    mutationFn: (body) => fetchApi("/login", { method: "POST", body: JSON.stringify(body) }),
  });
}

export function useRegister() {
  return useMutation<
    { accessToken: string },
    DefaultError,
    { email: string; password: string; displayName: string }
  >({
    mutationFn: (body) => fetchApi("/register", { method: "POST", body: JSON.stringify(body) }),
  });
}

export function useLogout() {
  return useMutation<void, DefaultError, void>({
    mutationFn: () => fetchApi("/logout", { method: "POST" }),
  });
}
