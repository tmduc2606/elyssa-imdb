import { AUTH_URL } from "@/lib/constants";
import { getAccessToken, setAccessToken } from "@/lib/urql";

let refreshPromise: Promise<boolean> | null = null;

async function doRefresh(): Promise<boolean> {
  try {
    const res = await fetch(`${AUTH_URL}/refresh`, {
      method: "POST",
      credentials: "include",
    });
    if (!res.ok) {
      setAccessToken(null);
      return false;
    }
    const { accessToken } = await res.json();
    setAccessToken(accessToken);
    return true;
  } catch {
    setAccessToken(null);
    return false;
  }
}

/**
 * Single-flight refresh: concurrent callers share one in-flight POST so the
 * rotation race (each call rotating from the same spent token) never happens.
 */
export function refreshAccessToken(): Promise<boolean> {
  if (!refreshPromise) {
    refreshPromise = doRefresh().finally(() => {
      refreshPromise = null;
    });
  }
  return refreshPromise;
}

export async function authApiFetch<T>(
  path: string,
  options: RequestInit = {},
  retry = true,
): Promise<T> {
  const token = getAccessToken();
  const headers: Record<string, string> = {
    ...((options.headers as Record<string, string>) ?? {}),
  };
  if (options.body != null && !headers["Content-Type"]) {
    headers["Content-Type"] = "application/json";
  }
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(`${AUTH_URL}${path}`, {
    ...options,
    credentials: "include",
    headers,
  });

  if (res.status === 401 && retry && path !== "/refresh") {
    const refreshed = await refreshAccessToken();
    if (refreshed) return authApiFetch<T>(path, options, false);
  }

  if (!res.ok) {
    if (res.status === 204) return undefined as T;
    const err = await res.json().catch(() => ({ message: `Request failed: ${res.status}` }));
    throw new Error(err.message ?? `Request failed: ${res.status}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}