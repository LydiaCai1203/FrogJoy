import * as React from "react";
import { useAuth } from "@/contexts/AuthContext";
import { API_URL } from "@/config";

export type Theme = "day" | "night" | "eye-care" | "fresh-green";

interface ThemeContextType {
  theme: Theme;
  setTheme: (theme: Theme) => void;
  fontSize: number;
  setFontSize: (size: number) => void;
}

const ThemeContext = React.createContext<ThemeContextType | undefined>(undefined);

const DEFAULT_FONT_SIZE = 18;
const MIN_FONT_SIZE = 12;
const MAX_FONT_SIZE = 32;

interface ThemeProviderProps {
  children: React.ReactNode;
}

function getLocalStorageTheme(userId: string | undefined): Theme | null {
  const key = userId ? `bookreader-theme-${userId}` : "bookreader-theme-anonymous";
  const stored = localStorage.getItem(key);
  if (stored === "day" || stored === "night" || stored === "eye-care" || stored === "fresh-green") {
    return stored;
  }
  return null;
}

function setLocalStorageTheme(userId: string | undefined, theme: Theme) {
  const key = userId ? `bookreader-theme-${userId}` : "bookreader-theme-anonymous";
  localStorage.setItem(key, theme);
}

function getLocalStorageFontSize(): number | null {
  const key = "bookreader-fontsize";
  const stored = localStorage.getItem(key);
  if (stored) {
    const num = parseInt(stored, 10);
    if (!isNaN(num) && num >= MIN_FONT_SIZE && num <= MAX_FONT_SIZE) {
      return num;
    }
  }
  return null;
}

function setLocalStorageFontSize(fontSize: number) {
  const key = "bookreader-fontsize";
  localStorage.setItem(key, String(fontSize));
}

export function getFontSizeConfig(fontSize: number) {
  const isMd = typeof window !== 'undefined' ? window.innerWidth >= 768 : false;
  return {
    mobile: fontSize,
    desktop: fontSize,
  };
}

function clampFontSize(size: number): number {
  return Math.min(MAX_FONT_SIZE, Math.max(MIN_FONT_SIZE, size));
}

export function ThemeProvider({ children }: ThemeProviderProps) {
  const { user, token, isLoading } = useAuth();
  const userId = user?.id;

  const [theme, setThemeState] = React.useState<Theme>("fresh-green");
  const [fontSize, setFontSizeState] = React.useState<number>(DEFAULT_FONT_SIZE);
  const isInitialMount = React.useRef(true);

  React.useEffect(() => {
    if (isLoading) return;

    if (!token || !userId) {
      const localTheme = getLocalStorageTheme(userId);
      const localFontSize = getLocalStorageFontSize();
      const initialTheme = localTheme || "fresh-green";
      const initialFontSize = localFontSize || DEFAULT_FONT_SIZE;
      setThemeState(initialTheme);
      setFontSizeState(initialFontSize);
      document.documentElement.setAttribute("data-theme", initialTheme);
      document.documentElement.style.setProperty("--font-size-mobile", `${initialFontSize}px`);
      document.documentElement.style.setProperty("--font-size-desktop", `${initialFontSize}px`);
      setLocalStorageTheme(userId, initialTheme);
      setLocalStorageFontSize(initialFontSize);
      isInitialMount.current = false;
      return;
    }

    const localTheme = getLocalStorageTheme(userId);
    const localFontSize = getLocalStorageFontSize();

    Promise.all([
      fetch(`${API_URL}/auth/theme`, {
        headers: { Authorization: `Bearer ${token}` },
      }).then(res => res.json()),
      fetch(`${API_URL}/auth/font-size`, {
        headers: { Authorization: `Bearer ${token}` },
      }).then(res => res.json()).catch(() => ({ font_size: null })),
    ]).then(([themeData, fontSizeData]) => {
      const remoteTheme = themeData.theme as Theme;
      const remoteFontSize = fontSizeData.font_size as number | null;
      const resolvedTheme = localTheme || remoteTheme || "fresh-green";
      const resolvedFontSize = localFontSize || remoteFontSize || DEFAULT_FONT_SIZE;
      setThemeState(resolvedTheme);
      setFontSizeState(resolvedFontSize);
      document.documentElement.setAttribute("data-theme", resolvedTheme);
      document.documentElement.style.setProperty("--font-size-mobile", `${resolvedFontSize}px`);
      document.documentElement.style.setProperty("--font-size-desktop", `${resolvedFontSize}px`);
      setLocalStorageTheme(userId, resolvedTheme);
      setLocalStorageFontSize(resolvedFontSize);
      isInitialMount.current = false;
    }).catch(() => {
      const fallbackTheme = localTheme || "fresh-green";
      const fallbackFontSize = localFontSize || DEFAULT_FONT_SIZE;
      setThemeState(fallbackTheme);
      setFontSizeState(fallbackFontSize);
      document.documentElement.setAttribute("data-theme", fallbackTheme);
      document.documentElement.style.setProperty("--font-size-mobile", `${fallbackFontSize}px`);
      document.documentElement.style.setProperty("--font-size-desktop", `${fallbackFontSize}px`);
      setLocalStorageTheme(userId, fallbackTheme);
      setLocalStorageFontSize(fallbackFontSize);
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

  const setFontSize = React.useCallback(
    (newFontSize: number) => {
      const clampedSize = clampFontSize(newFontSize);
      setFontSizeState(clampedSize);
      document.documentElement.style.setProperty("--font-size-mobile", `${clampedSize}px`);
      document.documentElement.style.setProperty("--font-size-desktop", `${clampedSize}px`);
      setLocalStorageFontSize(clampedSize);
      window.dispatchEvent(new CustomEvent('font-size-change', { detail: { fontSize: clampedSize } }));

      if (token) {
        fetch(`${API_URL}/auth/font-size`, {
          method: "PUT",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({ font_size: clampedSize }),
        }).catch(console.error);
      }
    },
    [token]
  );

  return (
    <ThemeContext.Provider value={{ theme, setTheme, fontSize, setFontSize }}>
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
