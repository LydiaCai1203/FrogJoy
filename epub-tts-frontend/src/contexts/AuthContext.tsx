import { createContext, useContext, useState, useEffect } from "react";
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

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [guestToken, setGuestToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const savedToken = localStorage.getItem("auth_token");
    if (savedToken) {
      setToken(savedToken);
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
        setGuestToken(data.access_token);
        localStorage.setItem("guest_token", data.access_token);
      }
    } catch {
      // Guest token not available, features will be limited
    } finally {
      setIsLoading(false);
    }
  };

  const fetchUser = async (authToken: string) => {
    try {
      const res = await fetch(`${API_URL}/auth/me`, {
        headers: {
          Authorization: `Bearer ${authToken}`,
        },
      });
      if (res.ok) {
        const userData = await res.json();
        setUser(userData);
      } else {
        localStorage.removeItem("auth_token");
        setToken(null);
        await fetchGuestToken();
        return;
      }
    } catch (error) {
      console.error("Failed to fetch user:", error);
      localStorage.removeItem("auth_token");
      setToken(null);
      await fetchGuestToken();
      return;
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
      throw new Error(error.detail || "Login failed");
    }

    const data = await res.json();
    setToken(data.access_token);
    setGuestToken(null);
    localStorage.setItem("auth_token", data.access_token);
    localStorage.removeItem("guest_token");
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

    // If server returned a token, email verification was skipped — auto login
    if (data.access_token) {
      setToken(data.access_token);
      setGuestToken(null);
      localStorage.setItem("auth_token", data.access_token);
      localStorage.removeItem("guest_token");
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

    setToken(data.access_token);
    setGuestToken(null);
    localStorage.setItem("auth_token", data.access_token);
    localStorage.removeItem("guest_token");
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

  const logout = () => {
    setUser(null);
    setToken(null);
    localStorage.removeItem("auth_token");
    fetchGuestToken();
  };

  // Effective token: prefer user token, fallback to guest token
  const effectiveToken = token || guestToken;
  const isGuest = !token && !!guestToken;

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
