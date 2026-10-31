import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import api, { setSessionExpiredHandler, tokens } from "../api/client";
import type { User } from "../api/types";

interface AuthContextType {
  user: User | null;
  authenticated: boolean;
  /** True while we have tokens but haven't confirmed who the user is yet. */
  loading: boolean;
  login: (username: string, password: string, remember: boolean) => Promise<void>;
  /** Start a session from tokens obtained another way (e.g. Google sign-in). */
  acceptTokens: (access: string, refresh: string) => void;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | null>(null);

export const AuthProvider = ({ children }: { children: React.ReactNode }) => {
  const queryClient = useQueryClient();
  const [hasTokens, setHasTokens] = useState(() => !!tokens.refresh());

  const { data: user, isLoading } = useQuery({
    queryKey: ["current_user"],
    queryFn: async () => (await api.get<User>("current_user/")).data,
    enabled: hasTokens,
    staleTime: 5 * 60_000,
    retry: false,
  });

  const clearSession = useCallback(() => {
    tokens.clear();
    setHasTokens(false);
    queryClient.clear();
  }, [queryClient]);

  useEffect(() => {
    setSessionExpiredHandler(clearSession);
  }, [clearSession]);

  // Keep tabs in sync when another tab logs in or out
  useEffect(() => {
    const onStorage = () => setHasTokens(!!tokens.refresh());
    window.addEventListener("storage", onStorage);
    return () => window.removeEventListener("storage", onStorage);
  }, []);

  const login = useCallback(
    async (username: string, password: string, remember: boolean) => {
      const res = await api.post<{ access: string; refresh: string }>("token/", { username, password });
      tokens.set(res.data.access, res.data.refresh, remember);
      queryClient.removeQueries({ queryKey: ["current_user"] });
      setHasTokens(true);
    },
    [queryClient],
  );

  const acceptTokens = useCallback(
    (access: string, refresh: string) => {
      tokens.set(access, refresh, true);
      queryClient.removeQueries({ queryKey: ["current_user"] });
      setHasTokens(true);
    },
    [queryClient],
  );

  const logout = useCallback(async () => {
    const refresh = tokens.refresh();
    if (refresh) {
      // Best effort: revoke the refresh token server-side
      api.post("token/logout/", { refresh }).catch(() => {});
    }
    clearSession();
  }, [clearSession]);

  const value = useMemo<AuthContextType>(
    () => ({
      user: user ?? null,
      authenticated: hasTokens,
      loading: hasTokens && isLoading,
      login,
      acceptTokens,
      logout,
    }),
    [user, hasTokens, isLoading, login, acceptTokens, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

// eslint-disable-next-line react-refresh/only-export-components
export const useAuth = () => {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
};
