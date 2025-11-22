import { createTheme } from "@mui/material/styles";

/**
 * Create app theme with light or dark mode
 */
export function createAppTheme(
  mode: "light" | "dark"
): ReturnType<typeof createTheme> {
  return createTheme({
    palette: {
      mode,
      primary: {
        main: mode === "light" ? "#1976d2" : "#90caf9",
      },
      secondary: {
        main: mode === "light" ? "#dc004e" : "#f48fb1",
      },
      background: {
        default: mode === "light" ? "#f5f5f5" : "#121212",
        paper: mode === "light" ? "#ffffff" : "#1e1e1e",
      },
    },
    components: {
      MuiAppBar: {
        styleOverrides: {
          root: {
            boxShadow:
              mode === "light"
                ? "0px 2px 4px rgba(0,0,0,0.1)"
                : "0px 2px 4px rgba(0,0,0,0.3)",
          },
        },
      },
    },
  });
}
