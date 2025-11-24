import { StrictMode, useState } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { ThemeProvider } from "@mui/material/styles";
import CssBaseline from "@mui/material/CssBaseline";
import { createAppTheme } from "./theme";
import "./index.css";
import App from "./App.tsx";

export function Main() {
  // Load theme from localStorage or default to "light"
  const getStoredTheme = (): "light" | "dark" => {
    const stored = localStorage.getItem("themeMode");
    if (stored === "light" || stored === "dark") {
      return stored;
    }
    return "light";
  };

  const [themeMode, setThemeMode] = useState<"light" | "dark">(getStoredTheme);
  const theme = createAppTheme(themeMode);

  const toggleTheme = () => {
    setThemeMode((prev) => {
      const newMode = prev === "light" ? "dark" : "light";
      // Save to localStorage
      localStorage.setItem("themeMode", newMode);
      return newMode;
    });
  };

  return (
    <BrowserRouter>
      <ThemeProvider theme={theme}>
        <CssBaseline />
        <App themeMode={themeMode} onThemeToggle={toggleTheme} />
      </ThemeProvider>
    </BrowserRouter>
  );
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <Main />
  </StrictMode>
);
