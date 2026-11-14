import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { api, getStoredUser, getToken, setStoredUser, setToken } from "./api";
import type { Role, User } from "./types";

interface AuthResponse {
  access_token: string;
  token_type: string;
  expires_at: string;
  user: User;
}

interface RegisterPayload {
  username: string;
  email?: string;
  password: string;
  full_name: string;
  phone?: string;
  address?: string;
}

interface AuthValue {
  user: User | null;
  token: string | null;
  ready: boolean;
  login: (username: string, password: string) => Promise<User>;
  loginPin: (username: string, pin: string) => Promise<User>;
  register: (payload: RegisterPayload) => Promise<User>;
  logout: () => Promise<void>;
  refresh: () => Promise<void>;
  setUser: (user: User | null) => void;
}

const AuthContext = createContext<AuthValue | null>(null);

export function homeForRole(role: Role | undefined): string {
  switch (role) {
    case "manager":
      return "/manager/dashboard";
    case "cashier":
    case "chef":
      return "/staff/board";
    case "customer":
    default:
      return "/menu";
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUserState] = useState<User | null>(() => getStoredUser<User>());
  const [token, setTokenState] = useState<string | null>(() => getToken());
  const [ready, setReady] = useState(false);

  const setUser = useCallback((next: User | null) => {
    setUserState(next);
    setStoredUser(next);
  }, []);

  const refresh = useCallback(async () => {
    const current = getToken();
    if (!current) {
      setUser(null);
      return;
    }
    const data = await api<{ user: User }>("/auth/me");
    setUser(data.user);
  }, [setUser]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      if (getToken()) {
        try {
          await refresh();
        } catch {
          if (!cancelled) {
            setToken(null);
            setTokenState(null);
            setUser(null);
          }
        }
      }
      if (!cancelled) setReady(true);
    })();
    const onUnauthorized = () => {
      setTokenState(null);
      setUser(null);
    };
    window.addEventListener("rm:unauthorized", onUnauthorized);
    return () => {
      cancelled = true;
      window.removeEventListener("rm:unauthorized", onUnauthorized);
    };
  }, [refresh, setUser]);

  const finish = useCallback(
    (data: AuthResponse) => {
      setToken(data.access_token);
      setTokenState(data.access_token);
      setUser(data.user);
      return data.user;
    },
    [setUser]
  );

  const login = useCallback(
    async (username: string, password: string) => {
      const data = await api<AuthResponse>("/auth/login", {
        method: "POST",
        body: { username, password }
      });
      return finish(data);
    },
    [finish]
  );

  const loginPin = useCallback(
    async (username: string, pin: string) => {
      const data = await api<AuthResponse>("/auth/pin", { method: "POST", body: { username, pin } });
      return finish(data);
    },
    [finish]
  );

  const register = useCallback(
    async (payload: RegisterPayload) => {
      const data = await api<AuthResponse>("/auth/register", { method: "POST", body: payload });
      return finish(data);
    },
    [finish]
  );

  const logout = useCallback(async () => {
    try {
      await api("/auth/logout", { method: "POST" });
    } catch {
      /* ignore network errors on sign-out */
    }
    setToken(null);
    setTokenState(null);
    setUser(null);
  }, [setUser]);

  const value = useMemo(
    () => ({ user, token, ready, login, loginPin, register, logout, refresh, setUser }),
    [user, token, ready, login, loginPin, register, logout, refresh, setUser]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}
