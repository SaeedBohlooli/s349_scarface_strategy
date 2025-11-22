import { useState } from "react";
import {
  AppBar,
  Box,
  Container,
  Toolbar,
  Typography,
  IconButton,
  Button,
} from "@mui/material";
import MenuIcon from "@mui/icons-material/Menu";
import { ErrorBoundary } from "./components/ErrorBoundary";
import ThemeToggle from "./components/ThemeToggle";
import Breadcrumbs from "./components/Breadcrumbs";
import PortfolioSelector from "./components/PortfolioSelector";
import DirectoriesView from "./components/DirectoriesView";
import FileContentView from "./components/FileContentView";
import LogsView from "./components/LogsView";
import "./App.css";

interface AppProps {
  themeMode: "light" | "dark";
  onThemeToggle: () => void;
}

type ViewState = "portfolios" | "directories" | "file" | "logs";

function App({ themeMode, onThemeToggle }: AppProps) {
  const [selectedPortfolio, setSelectedPortfolio] = useState<string>("");
  const [selectedDirectory, setSelectedDirectory] = useState<string>("");
  const [selectedFile, setSelectedFile] = useState<string>("");
  const [currentView, setCurrentView] = useState<ViewState>("portfolios");

  const handlePortfolioChange = (portfolioId: string) => {
    setSelectedPortfolio(portfolioId);
    setSelectedDirectory("");
    setSelectedFile("");
    // Don't automatically navigate - let user choose between directories or logs
    setCurrentView("portfolios");
  };

  const handleLogsClick = () => {
    setCurrentView("logs");
  };

  const handleFileClick = (directory: string, file: string) => {
    setSelectedDirectory(directory);
    setSelectedFile(file);
    setCurrentView("file");
  };

  const handleHomeClick = () => {
    setSelectedPortfolio("");
    setSelectedDirectory("");
    setSelectedFile("");
    setCurrentView("portfolios");
  };

  const handleDirectoryClick = () => {
    setSelectedFile("");
    setCurrentView("directories");
  };

  const getBreadcrumbItems = () => {
    const items: Array<{ label: string; onClick?: () => void }> = [];

    if (selectedPortfolio) {
      items.push({
        label: selectedPortfolio,
        onClick: currentView === "file" ? handleDirectoryClick : undefined,
      });
    }

    if (selectedDirectory && currentView === "file") {
      items.push({
        label: selectedDirectory,
      });
    }

    if (selectedFile) {
      items.push({
        label: selectedFile,
      });
    }

    return items;
  };

  return (
    <ErrorBoundary>
      <Box
        sx={{ display: "flex", flexDirection: "column", minHeight: "100vh" }}
      >
        <AppBar position="static">
          <Toolbar>
            <IconButton
              color="inherit"
              aria-label="menu"
              edge="start"
              sx={{ mr: 2 }}
            >
              <MenuIcon />
            </IconButton>
            <Typography variant="h6" component="div" sx={{ flexGrow: 1 }}>
              Scarface Strategy Dashboard
            </Typography>
            <ThemeToggle mode={themeMode} onToggle={onThemeToggle} />
          </Toolbar>
        </AppBar>

        <Box
          component="main"
          sx={{
            flexGrow: 1,
            p: 1,
          }}
        >
          <Container maxWidth="xl" sx={{ px: 2 }}>
            <Breadcrumbs
              items={getBreadcrumbItems()}
              onHomeClick={handleHomeClick}
            />

            {currentView === "portfolios" && (
              <Box>
                <Typography variant="h4" component="h1" gutterBottom>
                  Select Portfolio
                </Typography>
                <PortfolioSelector
                  onPortfolioChange={handlePortfolioChange}
                  selectedPortfolio={selectedPortfolio}
                />
                {selectedPortfolio && (
                  <Box sx={{ mt: 3 }}>
                    <Typography variant="h6" gutterBottom>
                      Quick Actions
                    </Typography>
                    <Box sx={{ display: "flex", gap: 2, flexWrap: "wrap" }}>
                      <Button
                        variant="outlined"
                        onClick={() => setCurrentView("directories")}
                      >
                        View Directories
                      </Button>
                      <Button variant="outlined" onClick={handleLogsClick}>
                        View Logs
                      </Button>
                    </Box>
                  </Box>
                )}
              </Box>
            )}

            {currentView === "directories" && selectedPortfolio && (
              <Box>
                <Box
                  sx={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    mb: 2,
                  }}
                >
                  <Box>
                    <Typography variant="h4" component="h1" gutterBottom>
                      Directories
                    </Typography>
                    <Typography
                      variant="body1"
                      color="text.secondary"
                      paragraph
                    >
                      Portfolio: {selectedPortfolio}
                    </Typography>
                  </Box>
                  <Button variant="outlined" onClick={handleLogsClick}>
                    View Logs
                  </Button>
                </Box>
                <DirectoriesView
                  portfolioId={selectedPortfolio}
                  onFileClick={handleFileClick}
                />
              </Box>
            )}

            {currentView === "file" &&
              selectedPortfolio &&
              selectedDirectory &&
              selectedFile && (
                <FileContentView
                  directory={selectedDirectory}
                  portfolioId={selectedPortfolio}
                  fileName={selectedFile}
                />
              )}

            {currentView === "logs" && selectedPortfolio && (
              <Box>
                <Box
                  sx={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    mb: 2,
                  }}
                >
                  <Typography variant="h4" component="h1">
                    Log Viewer
                  </Typography>
                  <Button
                    variant="outlined"
                    onClick={() => setCurrentView("directories")}
                  >
                    View Directories
                  </Button>
                </Box>
                <LogsView portfolioId={selectedPortfolio} />
              </Box>
            )}
          </Container>
        </Box>
      </Box>
    </ErrorBoundary>
  );
}

export default App;
