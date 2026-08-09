import {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  useMemo,
  type ReactNode,
} from "react";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { setAccessToken, getAccessToken } from "@/lib/urql";
import { AUTH_URL } from "@/lib/constants";
import type { User } from "@/lib/types";

interface AuthState {
  user: User | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, displayName: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthState | null>(null);

async function authFetch<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${AUTH_URL}${path}`, {
    method: body ? "POST" : "GET",
    credentials: "include",
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ message: "Request failed" }));
    throw new Error(err.message);
  }
  return res.json();
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const queryClient = useQueryClient();

  useEffect(() => {
    const tryRestore = async () => {
      const token = getAccessToken();
      if (token) {
        try {
          const u = await authFetch<User>("/me");
          setUser(u);
          return;
        } catch {
          // Token expired — try refresh below
        }
      }
      try {
        const res = await fetch(`${AUTH_URL}/refresh`, {
          method: "POST",
          credentials: "include",
        });
        if (!res.ok) throw new Error("No session");
        const { accessToken } = await res.json();
        setAccessToken(accessToken);
        const u = await authFetch<User>("/me");
        setUser(u);
      } catch {
        setAccessToken(null);
        setUser(null);
        toast.error("Session expired. Please log in again.");
      }
    };
    tryRestore().finally(() => setIsLoading(false));
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    setIsLoading(true);
    try {
      const { accessToken } = await authFetch<{ accessToken: string }>("/login", {
        email,
        password,
      });
      setAccessToken(accessToken);
      const me = await authFetch<User>("/me");
      setUser(me);
    } finally {
      setIsLoading(false);
    }
  }, []);

  const register = useCallback(
    async (email: string, password: string, displayName: string) => {
      setIsLoading(true);
      try {
        const { accessToken } = await authFetch<{ accessToken: string }>("/register", {
          email,
          password,
          displayName,
        });
        setAccessToken(accessToken);
        const me = await authFetch<User>("/me");
        setUser(me);
      } finally {
        setIsLoading(false);
      }
    },
    [],
  );

  const logout = useCallback(async () => {
    setIsLoading(true);
    try {
      await authFetch("/logout");
    } catch {
      /* ignore */
    }
    setAccessToken(null);
    setUser(null);
    queryClient.clear();
    setIsLoading(false);
  }, [queryClient]);

  const value = useMemo<AuthState>(
    () => ({ user, isLoading, isAuthenticated: user != null, login, register, logout }),
    [user, isLoading, login, register, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
