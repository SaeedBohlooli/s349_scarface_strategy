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

  const [selectedPortfolio, setSelectedPortfolio] = useState<string>(params.portfolioId || "");
  const [browsePath, setBrowsePath] = useState<string>("");
  const [selectedFilePath, setSelectedFilePath] = useState<string>("");
  const [currentView, setCurrentView] = useState<ViewState>(
    (params.view as ViewState) || "portfolios"
  );

  // Sync state from URL: /portfolio/id | /portfolio/id/browse[/path] | /portfolio/id/file/path | /portfolio/id/logs
  useEffect(() => {
    const pathParts = location.pathname.split("/").filter(Boolean);
    if (pathParts[0] === "portfolio" && pathParts[1]) {
      const portfolio = pathParts[1];
      setSelectedPortfolio(portfolio);

      if (pathParts[2] === "browse") {
        setSelectedFilePath("");
        setCurrentView("directories");
        setBrowsePath(pathParts.slice(3).map((p) => decodeURIComponent(p)).join("/"));
      } else if (pathParts[2] === "file") {
        setCurrentView("file");
        setSelectedFilePath(pathParts.slice(3).map((p) => decodeURIComponent(p)).join("/"));
        setBrowsePath("");
      } else if (pathParts[2] === "logs") {
        setSelectedFilePath("");
        setBrowsePath("");
        setCurrentView("logs");
      } else {
        setBrowsePath("");
        setSelectedFilePath("");
        setCurrentView("portfolios");
      }
    } else if (pathParts[0] === "calculator") {
      setSelectedPortfolio("");
      setBrowsePath("");
      setSelectedFilePath("");
      setCurrentView("calculator");
    } else {
      setSelectedPortfolio("");
      setBrowsePath("");
      setSelectedFilePath("");
      setCurrentView("portfolios");
    }
  }, [location.pathname]);

  const handlePortfolioChange = (portfolioId: string) => {
    if (selectedPortfolio !== portfolioId) {
      setSelectedPortfolio(portfolioId);
      setBrowsePath("");
      setSelectedFilePath("");
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

  const handleBrowsePathChange = (newPath: string) => {
    setBrowsePath(newPath);
    const encoded = newPath ? newPath.split("/").map(encodeURIComponent).join("/") : "";
    navigate(encoded ? `/portfolio/${selectedPortfolio}/browse/${encoded}` : `/portfolio/${selectedPortfolio}/browse`);
    setCurrentView("directories");
  };

  const handleFileClick = (filePath: string) => {
    if (selectedPortfolio) {
      setSelectedFilePath(filePath);
      const encoded = filePath.split("/").map(encodeURIComponent).join("/");
      navigate(`/portfolio/${selectedPortfolio}/file/${encoded}`);
      setCurrentView("file");
    }
  };

  const handleHomeClick = () => {
    if (selectedPortfolio) {
      setBrowsePath("");
      setSelectedFilePath("");
      navigate(`/portfolio/${selectedPortfolio}`);
      setCurrentView("portfolios");
    } else {
      setSelectedPortfolio("");
      setBrowsePath("");
      setSelectedFilePath("");
      navigate("/");
      setCurrentView("portfolios");
    }
  };

  const getBreadcrumbItems = () => {
    const items: Array<{ label: string; onClick?: () => void }> = [];

    if (currentView === "calculator") {
      items.push({ label: "Risk & Reward Calculator" });
      return items;
    }

    if (selectedPortfolio) {
      items.push({
        label: selectedPortfolio,
        onClick: () => {
          setBrowsePath("");
          setSelectedFilePath("");
          navigate(`/portfolio/${selectedPortfolio}`);
          setCurrentView("portfolios");
        },
      });
    }

    if (currentView === "file" && selectedFilePath) {
      const segments = selectedFilePath.split("/");
      const fileName = segments.pop() || selectedFilePath;
      const dirPath = segments.join("/");
      if (dirPath) {
        items.push({
          label: dirPath,
          onClick: () => {
            setSelectedFilePath("");
            const enc = dirPath.split("/").map(encodeURIComponent).join("/");
            navigate(enc ? `/portfolio/${selectedPortfolio}/browse/${enc}` : `/portfolio/${selectedPortfolio}/browse`);
            setCurrentView("directories");
          },
        });
      }
      items.push({ label: fileName });
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
                          setBrowsePath("");
                          navigate(`/portfolio/${selectedPortfolio}/browse`);
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
                <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "center", mb: 2 }}>
                  <Typography variant="h4" component="h1" gutterBottom>
                    Browse
                  </Typography>
                  <Button variant="outlined" onClick={handleLogsClick}>
                    View Logs
                  </Button>
                </Box>
                <DirectoriesView
                  portfolioId={selectedPortfolio}
                  currentPath={browsePath}
                  onPathChange={handleBrowsePathChange}
                  onFileClick={handleFileClick}
                />
              </Box>
            )}

            {currentView === "file" && selectedPortfolio && selectedFilePath && (
              <FileContentView
                portfolioId={selectedPortfolio}
                filePath={selectedFilePath}
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
                    onClick={() => {
                      setBrowsePath("");
                      navigate(`/portfolio/${selectedPortfolio}/browse`);
                      setCurrentView("directories");
                    }}
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
