import * as React from "react";
import { useAuth } from "@/contexts/AuthContext";

type Theme = "day" | "night" | "eye-care";

interface ThemeContextType {
  theme: Theme;
  setTheme: (theme: Theme) => void;
}

const ThemeContext = React.createContext<ThemeContextType | undefined>(undefined);

interface ThemeProviderProps {
  children: React.ReactNode;
}

function getStorageKey(userId: string | undefined) {
  return userId ? `bookreader-theme-${userId}` : "bookreader-theme-anonymous";
}

function getInitialTheme(userId: string | undefined): Theme {
  const stored = localStorage.getItem(getStorageKey(userId));
  if (stored === "day" || stored === "night" || stored === "eye-care") {
    return stored;
  }
  return "day";
}

export function ThemeProvider({
  children,
}: ThemeProviderProps) {
  const { user } = useAuth();
  const userId = user?.id;
  const [theme, setTheme] = React.useState<Theme>(() => getInitialTheme(userId));

  React.useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem(getStorageKey(userId), theme);
  }, [theme, userId]);

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

