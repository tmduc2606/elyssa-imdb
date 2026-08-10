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
import { authApiFetch, refreshAccessToken } from "@/lib/authApi";
import type { User } from "@/lib/types";

interface AuthState {
  user: User | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, displayName: string) => Promise<void>;
  logout: () => Promise<void>;
  refreshUser: () => Promise<User | null>;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const queryClient = useQueryClient();

  useEffect(() => {
    const tryRestore = async () => {
      const hadSession = !!getAccessToken();
      try {
        if (hadSession) {
          try {
            const u = await authApiFetch<User>("/me");
            setUser(u);
            return;
          } catch {
            // Token expired — try refresh below
          }
        }
        const ok = await refreshAccessToken();
        if (ok) {
          // Do not re-enter the 401-retry loop for the /me bootstrap call
          const u = await authApiFetch<User>("/me", {}, false);
          setUser(u);
          return;
        }
      } catch {
        // fall through to the session-expired handling below
      }
      // Only visitors who HAD a session and lost it get the toast; anonymous
      // page loads fail silently (no cookie is a perfectly normal state).
      if (hadSession) {
        toast.error("Session expired. Please log in again.");
      }
    };
    tryRestore().finally(() => setIsLoading(false));
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    setIsLoading(true);
    try {
      const { accessToken } = await authApiFetch<{ accessToken: string }>("/login", {
        method: "POST",
        body: JSON.stringify({ email, password }),
      });
      setAccessToken(accessToken);
      const me = await authApiFetch<User>("/me", {}, false);
      setUser(me);
    } finally {
      setIsLoading(false);
    }
  }, []);

  const register = useCallback(
    async (email: string, password: string, displayName: string) => {
      setIsLoading(true);
      try {
        const { accessToken } = await authApiFetch<{ accessToken: string }>("/register", {
          method: "POST",
          body: JSON.stringify({ email, password, displayName }),
        });
        setAccessToken(accessToken);
        const me = await authApiFetch<User>("/me", {}, false);
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
      await authApiFetch("/logout", { method: "POST" });
    } catch {
      /* ignore */
    }
    setAccessToken(null);
    setUser(null);
    queryClient.clear();
    setIsLoading(false);
  }, [queryClient]);

  const refreshUser = useCallback(async () => {
    try {
      const u = await authApiFetch<User>("/me", {}, false);
      setUser(u);
      return u;
    } catch {
      return null;
    }
  }, []);

  const value = useMemo<AuthState>(
    () => ({ user, isLoading, isAuthenticated: user != null, login, register, logout, refreshUser }),
    [user, isLoading, login, register, logout, refreshUser],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
