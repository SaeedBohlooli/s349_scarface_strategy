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
        default: mode === "light" ? "#f5f5f5" : "#0a0a0a",
        paper: mode === "light" ? "#ffffff" : "#1a1a1a",
      },
      text: {
        primary: mode === "light" ? "rgba(0, 0, 0, 0.87)" : "#e8e8e8",
        secondary: mode === "light" ? "rgba(0, 0, 0, 0.6)" : "#b8b8b8",
      },
      divider:
        mode === "light" ? "rgba(0, 0, 0, 0.12)" : "rgba(255, 255, 255, 0.3)",
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
      MuiTypography: {
        styleOverrides: {
          root: {
            color: mode === "light" ? undefined : "#e8e8e8",
          },
        },
      },
      MuiTableCell: {
        styleOverrides: {
          root: {
            color: mode === "light" ? undefined : "#e8e8e8",
          },
        },
      },
    },
  });
}
