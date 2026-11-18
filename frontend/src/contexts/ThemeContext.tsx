import React, { createContext, useContext, useState, useEffect } from "react";
import { ThemeProvider, createTheme } from "@mui/material/styles";
import { redDarkTheme, solarizedDarkTheme, greenForestTheme, oceanBlueTheme, purpleNightTheme } from "../themes";

const themeMap: Record<string, any> = {
  "red-dark": redDarkTheme,
  "solarized-dark": solarizedDarkTheme,
  "green-forest": greenForestTheme,
  "ocean-blue": oceanBlueTheme,
  "purple-night": purpleNightTheme,
  "dark": { palette: { mode: "dark" } },
  "light": {
    palette: {
      mode: "light",
      text: {
        primary: "#222",
        secondary: "#555",
      },
      background: {
        default: "#fff",
        paper: "#f6f6f6",
      },
    },
  },
};

const ThemeContext = createContext({
  theme: "system",
  setTheme: (theme: string) => {},
});

export const useThemeContext = () => useContext(ThemeContext);

export const CustomThemeProvider: React.FC<{children: React.ReactNode}> = ({ children }) => {
  // 1. Restaurar o tema do localStorage ao iniciar
  const [theme, setTheme] = useState(() => {
    return localStorage.getItem("theme") || "system";
  });

  // 2. Salvar tema no localStorage sempre que mudar
  useEffect(() => {
    localStorage.setItem("theme", theme);
  }, [theme]);

  let muiTheme;
  if (theme === "system") {
    const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
    muiTheme = createTheme(prefersDark ? themeMap["dark"] : themeMap["light"]);
  } else {
    muiTheme = createTheme(themeMap[theme] || themeMap["light"]);
  }

  return (
    <ThemeContext.Provider value={{ theme, setTheme }}>
      <ThemeProvider theme={muiTheme}>
        {children}
      </ThemeProvider>
    </ThemeContext.Provider>
  );
};