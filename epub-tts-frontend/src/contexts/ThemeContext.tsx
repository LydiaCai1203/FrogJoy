import * as React from "react";
import { useAuth } from "@/contexts/AuthContext";
import { API_URL } from "@/config";

type Theme = "day" | "night" | "eye-care";

interface ThemeContextType {
  theme: Theme;
  setTheme: (theme: Theme) => void;
}

const ThemeContext = React.createContext<ThemeContextType | undefined>(undefined);

interface ThemeProviderProps {
  children: React.ReactNode;
}

function getLocalStorageTheme(userId: string | undefined): Theme | null {
  const key = userId ? `bookreader-theme-${userId}` : "bookreader-theme-anonymous";
  const stored = localStorage.getItem(key);
  if (stored === "day" || stored === "night" || stored === "eye-care") {
    return stored;
  }
  return null;
}

function setLocalStorageTheme(userId: string | undefined, theme: Theme) {
  const key = userId ? `bookreader-theme-${userId}` : "bookreader-theme-anonymous";
  localStorage.setItem(key, theme);
}

export function ThemeProvider({ children }: ThemeProviderProps) {
  const { user, token, isLoading } = useAuth();
  const userId = user?.id;

  const [theme, setThemeState] = React.useState<Theme>("eye-care");
  const isInitialMount = React.useRef(true);

  React.useEffect(() => {
    if (isLoading) return;

    if (!token || !userId) {
      const local = getLocalStorageTheme(userId);
      const initial = local || "eye-care";
      setThemeState(initial);
      document.documentElement.setAttribute("data-theme", initial);
      setLocalStorageTheme(userId, initial);
      isInitialMount.current = false;
      return;
    }

    const local = getLocalStorageTheme(userId);

    fetch(`${API_URL}/auth/theme`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((res) => res.json())
      .then((data) => {
        const remote = data.theme as Theme;
        const resolved = local || remote;
        setThemeState(resolved);
        document.documentElement.setAttribute("data-theme", resolved);
        setLocalStorageTheme(userId, resolved);
        isInitialMount.current = false;
      })
      .catch(() => {
        const fallback = local || "eye-care";
        setThemeState(fallback);
        document.documentElement.setAttribute("data-theme", fallback);
        setLocalStorageTheme(userId, fallback);
        isInitialMount.current = false;
      });
  }, [isLoading, token, userId]);

  const setTheme = React.useCallback(
    (newTheme: Theme) => {
      setThemeState(newTheme);
      document.documentElement.setAttribute("data-theme", newTheme);
      setLocalStorageTheme(userId, newTheme);

      if (token) {
        fetch(`${API_URL}/auth/theme`, {
          method: "PUT",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({ theme: newTheme }),
        }).catch(console.error);
      }
    },
    [token, userId]
  );

  return (
    <ThemeContext.Provider value={{ theme, setTheme }}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme() {
  const context = React.useContext(ThemeContext);
  if (!context) {
    throw new Error("useTheme must be used within a ThemeProvider");
  }
  return context;
}
