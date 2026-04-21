import { createContext, useContext, useState, useEffect, useRef, useCallback } from "react";
import type { ReactNode } from "react";
import { API_URL } from "@/config";

interface User {
  id: string;
  email: string;
  is_admin?: boolean;
}

interface AuthContextType {
  user: User | null;
  token: string | null;
  isGuest: boolean;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string) => Promise<string>;
  verifyEmail: (token: string) => Promise<void>;
  resendVerification: (email: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

function saveTokens(access: string, refresh: string, prefix: "auth" | "guest") {
  localStorage.setItem(`${prefix}_access_token`, access);
  localStorage.setItem(`${prefix}_refresh_token`, refresh);
}

function clearTokens(prefix: "auth" | "guest") {
  localStorage.removeItem(`${prefix}_access_token`);
  localStorage.removeItem(`${prefix}_refresh_token`);
}

function getTokens(prefix: "auth" | "guest") {
  return {
    access: localStorage.getItem(`${prefix}_access_token`),
    refresh: localStorage.getItem(`${prefix}_refresh_token`),
  };
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [accessToken, setAccessToken] = useState<string | null>(null);
  const [guestAccessToken, setGuestAccessToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // Refresh deduplication
  const refreshPromiseRef = useRef<Promise<string | null> | null>(null);

  const refreshAccessToken = useCallback(async (prefix: "auth" | "guest"): Promise<string | null> => {
    // Deduplicate concurrent refresh calls
    if (refreshPromiseRef.current) {
      return refreshPromiseRef.current;
    }

    const promise = (async () => {
      const { refresh } = getTokens(prefix);
      if (!refresh) return null;

      try {
        const res = await fetch(`${API_URL}/auth/refresh`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ refresh_token: refresh }),
        });

        if (!res.ok) {
          clearTokens(prefix);
          return null;
        }

        const data = await res.json();
        saveTokens(data.access_token, data.refresh_token, prefix);

        if (prefix === "auth") {
          setAccessToken(data.access_token);
        } else {
          setGuestAccessToken(data.access_token);
        }

        return data.access_token as string;
      } catch {
        clearTokens(prefix);
        return null;
      } finally {
        refreshPromiseRef.current = null;
      }
    })();

    refreshPromiseRef.current = promise;
    return promise;
  }, []);

  useEffect(() => {
    const { access: savedToken } = getTokens("auth");
    if (savedToken) {
      setAccessToken(savedToken);
      fetchUser(savedToken);
    } else {
      fetchGuestToken();
    }
  }, []);

  const fetchGuestToken = async () => {
    try {
      const res = await fetch(`${API_URL}/auth/guest-token`);
      if (res.ok) {
        const data = await res.json();
        setGuestAccessToken(data.access_token);
        saveTokens(data.access_token, data.refresh_token, "guest");
      }
    } catch {
      // Guest token not available
    } finally {
      setIsLoading(false);
    }
  };

  const fetchUser = async (authToken: string) => {
    try {
      const res = await fetch(`${API_URL}/auth/me`, {
        headers: { Authorization: `Bearer ${authToken}` },
      });
      if (res.ok) {
        const userData = await res.json();
        setUser(userData);
      } else if (res.status === 401) {
        // Try refresh
        const newToken = await refreshAccessToken("auth");
        if (newToken) {
          const retryRes = await fetch(`${API_URL}/auth/me`, {
            headers: { Authorization: `Bearer ${newToken}` },
          });
          if (retryRes.ok) {
            setUser(await retryRes.json());
            return;
          }
        }
        clearTokens("auth");
        setAccessToken(null);
        await fetchGuestToken();
      } else {
        clearTokens("auth");
        setAccessToken(null);
        await fetchGuestToken();
      }
    } catch {
      clearTokens("auth");
      setAccessToken(null);
      await fetchGuestToken();
    } finally {
      setIsLoading(false);
    }
  };

  const login = async (email: string, password: string) => {
    const res = await fetch(`${API_URL}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });

    if (!res.ok) {
      const error = await res.json();
      // Handle 409 (max devices) — error.detail is an object
      if (res.status === 409 && typeof error.detail === "object") {
        throw new Error(error.detail.message || "已达最大设备数");
      }
      throw new Error(typeof error.detail === "string" ? error.detail : "Login failed");
    }

    const data = await res.json();
    setAccessToken(data.access_token);
    setGuestAccessToken(null);
    saveTokens(data.access_token, data.refresh_token, "auth");
    clearTokens("guest");
    setUser({ id: "", email });
    await fetchUser(data.access_token);

    const themeRes = await fetch(`${API_URL}/auth/theme`, {
      headers: { Authorization: `Bearer ${data.access_token}` },
    });
    if (themeRes.ok) {
      const themeData = await themeRes.json();
      localStorage.setItem("bookreader-theme-logged-in", themeData.theme);
    }
  };

  const register = async (email: string, password: string): Promise<string> => {
    const res = await fetch(`${API_URL}/auth/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });

    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.detail || "Registration failed");
    }

    if (data.access_token) {
      setAccessToken(data.access_token);
      setGuestAccessToken(null);
      saveTokens(data.access_token, data.refresh_token, "auth");
      clearTokens("guest");
      await fetchUser(data.access_token);
      return "__auto_login__";
    }

    return data.message;
  };

  const verifyEmail = async (verifyToken: string) => {
    const res = await fetch(`${API_URL}/auth/verify`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ token: verifyToken }),
    });

    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.detail || "Verification failed");
    }

    setAccessToken(data.access_token);
    setGuestAccessToken(null);
    saveTokens(data.access_token, data.refresh_token, "auth");
    clearTokens("guest");
    await fetchUser(data.access_token);
  };

  const resendVerification = async (email: string) => {
    const res = await fetch(`${API_URL}/auth/resend-verification`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email }),
    });

    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.detail || "Failed to resend");
    }
  };

  const logout = async () => {
    // Call backend to invalidate session
    const currentToken = accessToken;
    if (currentToken) {
      try {
        await fetch(`${API_URL}/auth/logout`, {
          method: "POST",
          headers: { Authorization: `Bearer ${currentToken}` },
        });
      } catch {
        // Best-effort
      }
    }
    setUser(null);
    setAccessToken(null);
    clearTokens("auth");
    fetchGuestToken();
  };

  // Effective token: prefer user token, fallback to guest token
  const effectiveToken = accessToken || guestAccessToken;
  const isGuest = !accessToken && !!guestAccessToken;

  return (
    <AuthContext.Provider value={{ user, token: effectiveToken, isGuest, isLoading, login, register, verifyEmail, resendVerification, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
