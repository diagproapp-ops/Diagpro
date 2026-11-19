import React, { createContext, useContext, useState, useEffect } from "react";
import { ThemeProvider, createTheme } from "@mui/material/styles";
import {
  operanDarkTheme,
  redDarkTheme,
  solarizedDarkTheme,
  greenForestTheme,
  oceanBlueTheme,
  purpleNightTheme,
} from "../themes";

const themeMap: Record<string, any> = {
  "operan-dark": operanDarkTheme,
  "dark": operanDarkTheme,
  "red-dark": redDarkTheme,
  "solarized-dark": solarizedDarkTheme,
  "green-forest": greenForestTheme,
  "ocean-blue": oceanBlueTheme,
  "purple-night": purpleNightTheme,
  "light": {
    palette: {
      mode: "light",
      primary: { main: "#0284C7" },
      text: { primary: "#0F172A", secondary: "#475569" },
      background: { default: "#F8FAFC", paper: "#FFFFFF" },
    },
    shape: { borderRadius: 12 },
  },
};

const ThemeContext = createContext({
  theme: "operan-dark",
  setTheme: (theme: string) => {},
});

export const useThemeContext = () => useContext(ThemeContext);

export const CustomThemeProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [theme, setTheme] = useState(() => {
    return localStorage.getItem("diagpro_theme") || "operan-dark";
  });

  useEffect(() => {
    localStorage.setItem("diagpro_theme", theme);
  }, [theme]);

  let muiTheme;
  if (theme === "system") {
    const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
    muiTheme = createTheme(prefersDark ? themeMap["operan-dark"] : themeMap["light"]);
  } else {
    muiTheme = createTheme(themeMap[theme] || themeMap["operan-dark"]);
  }

  return (
    <ThemeContext.Provider value={{ theme, setTheme }}>
      <ThemeProvider theme={muiTheme}>{children}</ThemeProvider>
    </ThemeContext.Provider>
  );
};
