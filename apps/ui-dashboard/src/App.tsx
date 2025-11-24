import { useState, useEffect } from "react";
import { useNavigate, useParams, useLocation } from "react-router-dom";
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
import RefreshIcon from "@mui/icons-material/Refresh";
import { ErrorBoundary } from "./components/ErrorBoundary";
import ThemeToggle from "./components/ThemeToggle";
import Breadcrumbs from "./components/Breadcrumbs";
import PortfolioSelector from "./components/PortfolioSelector";
import DirectoriesView from "./components/DirectoriesView";
import FileContentView from "./components/FileContentView";
import LogsView from "./components/LogsView";
import RiskRewardCalculator from "./features/riskReward/RiskRewardCalculator";
import "./App.css";

interface AppProps {
  themeMode: "light" | "dark";
  onThemeToggle: () => void;
}

type ViewState = "portfolios" | "directories" | "file" | "logs" | "calculator";

function App({ themeMode, onThemeToggle }: AppProps) {
  const navigate = useNavigate();
  const location = useLocation();
  const params = useParams<{
    portfolioId?: string;
    directory?: string;
    file?: string;
    view?: string;
  }>();

  // Initialize state from URL params
  const [selectedPortfolio, setSelectedPortfolio] = useState<string>(params.portfolioId || "");
  const [selectedDirectory, setSelectedDirectory] = useState<string>(params.directory || "");
  const [selectedFile, setSelectedFile] = useState<string>(params.file || "");
  const [currentView, setCurrentView] = useState<ViewState>(
    (params.view as ViewState) || "portfolios"
  );

  // Sync state with URL params on mount and route changes
  useEffect(() => {
    const pathParts = location.pathname.split("/").filter(Boolean);
    if (pathParts[0] === "portfolio" && pathParts[1]) {
      const portfolio = pathParts[1];
      setSelectedPortfolio(portfolio);
      
      if (pathParts[2] === "directory" && pathParts[3]) {
        const directory = pathParts[3];
        setSelectedDirectory(directory);
        setCurrentView("directories");
        
        if (pathParts[4] === "file" && pathParts[5]) {
          const file = decodeURIComponent(pathParts[5]);
          setSelectedFile(file);
          setCurrentView("file");
        } else {
          setSelectedFile("");
        }
      } else if (pathParts[2] === "logs") {
        setSelectedDirectory("");
        setSelectedFile("");
        setCurrentView("logs");
      } else {
        setSelectedDirectory("");
        setSelectedFile("");
        setCurrentView("portfolios");
      }
    } else if (pathParts[0] === "calculator") {
      setSelectedPortfolio("");
      setSelectedDirectory("");
      setSelectedFile("");
      setCurrentView("calculator");
    } else {
      setSelectedPortfolio("");
      setSelectedDirectory("");
      setSelectedFile("");
      setCurrentView("portfolios");
    }
  }, [location.pathname]);

  const handlePortfolioChange = (portfolioId: string) => {
    // Only navigate if portfolio actually changed
    if (selectedPortfolio !== portfolioId) {
      setSelectedPortfolio(portfolioId);
      setSelectedDirectory("");
      setSelectedFile("");
      navigate(`/portfolio/${portfolioId}`);
      setCurrentView("portfolios");
    }
  };

  const handleLogsClick = () => {
    if (selectedPortfolio) {
      navigate(`/portfolio/${selectedPortfolio}/logs`);
      setCurrentView("logs");
    }
  };

  const handleFileClick = (directory: string, file: string) => {
    if (selectedPortfolio) {
      setSelectedDirectory(directory);
      setSelectedFile(file);
      navigate(`/portfolio/${selectedPortfolio}/directory/${directory}/file/${encodeURIComponent(file)}`);
      setCurrentView("file");
    }
  };

  const handleHomeClick = () => {
    setSelectedPortfolio("");
    setSelectedDirectory("");
    setSelectedFile("");
    navigate("/");
    setCurrentView("portfolios");
  };

  const handleDirectoryClick = () => {
    if (selectedPortfolio && selectedDirectory) {
      setSelectedFile("");
      navigate(`/portfolio/${selectedPortfolio}/directory/${selectedDirectory}`);
      setCurrentView("directories");
    }
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
          <Container maxWidth={false} sx={{ px: 2 }}>
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
                        onClick={() => {
                          navigate(`/portfolio/${selectedPortfolio}/directory`);
                          setCurrentView("directories");
                        }}
                      >
                        View Directories
                      </Button>
                      <Button variant="outlined" onClick={handleLogsClick}>
                        View Logs
                      </Button>
                    </Box>
                  </Box>
                )}
                <Box sx={{ mt: 3 }}>
                  <Typography variant="h6" gutterBottom>
                    Tools
                  </Typography>
                  <Box sx={{ display: "flex", gap: 2, flexWrap: "wrap" }}>
                    <Button
                      variant="outlined"
                      onClick={() => {
                        navigate("/calculator");
                        setCurrentView("calculator");
                      }}
                    >
                      Risk & Reward Calculator
                    </Button>
                  </Box>
                </Box>
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

            {currentView === "calculator" && <RiskRewardCalculator />}
          </Container>
        </Box>
      </Box>
    </ErrorBoundary>
  );
}

export default App;
