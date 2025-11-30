import { useState, useEffect } from "react";
import {
  Box,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Typography,
  IconButton,
  Tooltip,
  TextField,
  InputAdornment,
  ToggleButton,
  ToggleButtonGroup,
  Chip,
  Button,
} from "@mui/material";
import RefreshIcon from "@mui/icons-material/Refresh";
import SearchIcon from "@mui/icons-material/Search";
import ClearIcon from "@mui/icons-material/Clear";
import ArrowBackIcon from "@mui/icons-material/ArrowBack";
import CircularProgress from "@mui/material/CircularProgress";
import {
  getLogDirectories,
  getLogFiles,
  getLogContent,
  searchLogDirectory,
} from "../services/api";
import type { ApiError, LogLine, DirectorySearchResponse } from "../types/api";
import LoadingSpinner from "./LoadingSpinner";
import ApiErrorAlert from "./ApiErrorAlert";
import LogViewer from "./LogViewer";
import DirectorySearchResults from "./DirectorySearchResults";

interface LogsViewProps {
  portfolioId: string;
}

export default function LogsView({ portfolioId }: LogsViewProps) {
  const [logDirectories, setLogDirectories] = useState<string[]>([]);
  const [selectedDirectory, setSelectedDirectory] = useState<string>("");
  const [logFiles, setLogFiles] = useState<string[]>([]);
  const [selectedFile, setSelectedFile] = useState<string>("");
  const [logData, setLogData] = useState<{
    lines: LogLine[];
    totalLines: number;
    originalTotalLines: number;
    page: number;
    perPage: number;
    totalPages: number;
  } | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadingFiles, setLoadingFiles] = useState(false);
  const [loadingContent, setLoadingContent] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [directorySearchQuery, setDirectorySearchQuery] = useState<string>("");
  const [searchMode, setSearchMode] = useState<"file" | "directory">("file");
  const [directorySearchData, setDirectorySearchData] =
    useState<DirectorySearchResponse | null>(null);
  const [loadingDirectorySearch, setLoadingDirectorySearch] = useState(false);
  const [cameFromSearch, setCameFromSearch] = useState(false);
  const [targetLineNumber, setTargetLineNumber] = useState<number | null>(null);
  const [targetPage, setTargetPage] = useState<number | null>(null);

  // Load log directories on mount
  useEffect(() => {
    if (portfolioId) {
      loadLogDirectories();
    }
  }, [portfolioId]);

  // Load files when directory changes
  useEffect(() => {
    if (selectedDirectory) {
      loadLogFiles();
      setSelectedFile("");
      setLogData(null);
    }
  }, [selectedDirectory]);

  // Load content when file changes
  useEffect(() => {
    if (selectedFile && selectedDirectory) {
      // If we have a target page (from search result), use it; otherwise start at page 1
      const pageToLoad = targetPage || 1;
      loadLogContent(pageToLoad, searchQuery);
      // Clear target page after using it
      if (targetPage) {
        setTargetPage(null);
      }
    }
  }, [selectedFile, selectedDirectory]);

  const loadLogDirectories = async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await getLogDirectories(portfolioId);
      setLogDirectories(response.directories);

      // Auto-select if only one directory
      if (response.directories.length === 1) {
        setSelectedDirectory(response.directories[0]);
      }
    } catch (err) {
      setError(err as ApiError);
    } finally {
      setLoading(false);
    }
  };

  const loadLogFiles = async () => {
    try {
      setLoadingFiles(true);
      setError(null);
      const response = await getLogFiles(portfolioId, selectedDirectory);
      setLogFiles(response.files);

      // Auto-select if only one file
      if (response.files.length === 1) {
        setSelectedFile(response.files[0]);
      }
    } catch (err) {
      setError(err as ApiError);
    } finally {
      setLoadingFiles(false);
    }
  };

  const loadLogContent = async (page: number = 1, search: string = "") => {
    if (!selectedFile || !selectedDirectory) return;

    try {
      setLoadingContent(true);
      setError(null);
      const response = await getLogContent(
        portfolioId,
        selectedDirectory,
        selectedFile,
        page,
        1000, // per_page
        search || undefined
      );
      setLogData({
        lines: response.lines,
        totalLines: response.totalLines,
        originalTotalLines: response.originalTotalLines,
        page: response.page,
        perPage: response.perPage,
        totalPages: response.totalPages,
      });
    } catch (err) {
      setError(err as ApiError);
    } finally {
      setLoadingContent(false);
    }
  };

  const handleDirectoryChange = (directory: string) => {
    setSelectedDirectory(directory);
    setSearchQuery("");
  };

  const handleFileClick = (file: string) => {
    setSelectedFile(file);
    setSearchQuery("");
  };

  const handlePageChange = async (newPage: number) => {
    await loadLogContent(newPage, searchQuery);
  };

  const handleDirectorySearch = async (query: string, page: number = 1) => {
    if (!selectedDirectory || !query.trim()) {
      setDirectorySearchData(null);
      return;
    }

    try {
      setLoadingDirectorySearch(true);
      setError(null);
      const response = await searchLogDirectory(
        portfolioId,
        selectedDirectory,
        query,
        page,
        50,
        5
      );
      setDirectorySearchData(response);
    } catch (err) {
      setError(err as ApiError);
    } finally {
      setLoadingDirectorySearch(false);
    }
  };

  const handleDirectorySearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (directorySearchQuery.trim()) {
      handleDirectorySearch(directorySearchQuery, 1);
    }
  };

  const handleResultClick = async (fileName: string, lineNumber: number) => {
    // Store that we came from search
    setCameFromSearch(true);
    setTargetLineNumber(lineNumber);
    // Calculate which page the line would be on (assuming 1000 lines per page)
    const pageForLine = Math.ceil(lineNumber / 1000);
    // Set the target page before changing the file
    setTargetPage(pageForLine);
    // Set the file and load it WITHOUT search filter to show the entire file
    setSelectedFile(fileName);
    setSearchMode("file");
    // Keep the search query for reference but don't use it for filtering
    setSearchQuery("");
    // The useEffect will handle loading the correct page
  };

  const handleBackToSearch = () => {
    setCameFromSearch(false);
    setTargetLineNumber(null);
    setTargetPage(null);
    setSearchMode("directory");
    // Keep the file selected but clear the log data view
    // Don't clear selectedFile so user can see which file they were viewing
    setLogData(null);
    setSearchQuery("");
    // Restore directory search view - the data should still be there
  };

  const handleSearchModeChange = (
    _event: React.MouseEvent<HTMLElement>,
    newMode: "file" | "directory" | null
  ) => {
    if (newMode !== null) {
      setSearchMode(newMode);
      setCameFromSearch(false);
      setTargetLineNumber(null);
      if (newMode === "file") {
        // Don't clear directory search data when manually switching - user might want to go back
        // Only clear if they're not coming from search
        if (!cameFromSearch) {
          setDirectorySearchData(null);
          setDirectorySearchQuery("");
        }
      } else {
        setSearchQuery("");
        if (selectedFile && !cameFromSearch) {
          setLogData(null);
        }
      }
    }
  };

  if (loading) {
    return <LoadingSpinner message="Loading log directories..." />;
  }

  if (error && !logDirectories.length) {
    return (
      <ApiErrorAlert
        error={error}
        onRetry={loadLogDirectories}
        title="Failed to load log directories"
      />
    );
  }

  return (
    <Box>
      <Box
        sx={{
          display: "flex",
          gap: 2,
          alignItems: "center",
          mb: 2,
          flexWrap: "wrap",
        }}
      >
        <Typography
          variant="body2"
          color="text.secondary"
          sx={{ minWidth: "fit-content" }}
        >
          Portfolio: {portfolioId}
        </Typography>

        <Tooltip title="Refresh log directories">
          <IconButton
            size="small"
            onClick={loadLogDirectories}
            disabled={loading}
          >
            <RefreshIcon />
          </IconButton>
        </Tooltip>

        <FormControl size="small" sx={{ minWidth: 200 }}>
          <InputLabel id="log-directory-select-label">Directory</InputLabel>
          <Select
            labelId="log-directory-select-label"
            id="log-directory-select"
            value={selectedDirectory}
            label="Directory"
            onChange={(e) => handleDirectoryChange(e.target.value)}
          >
            {logDirectories.map((dir) => (
              <MenuItem key={dir} value={dir}>
                {dir}
              </MenuItem>
            ))}
          </Select>
        </FormControl>

        {selectedDirectory && (
          <>
            <FormControl size="small" sx={{ minWidth: 200 }}>
              <InputLabel id="log-file-select-label">File</InputLabel>
              <Select
                labelId="log-file-select-label"
                id="log-file-select"
                value={selectedFile}
                label="File"
                onChange={(e) => handleFileClick(e.target.value)}
                disabled={
                  loadingFiles ||
                  logFiles.length === 0 ||
                  searchMode === "directory"
                }
              >
                {loadingFiles ? (
                  <MenuItem disabled>Loading...</MenuItem>
                ) : logFiles.length === 0 ? (
                  <MenuItem disabled>No files</MenuItem>
                ) : (
                  logFiles.map((file) => (
                    <MenuItem key={file} value={file}>
                      {file}
                    </MenuItem>
                  ))
                )}
              </Select>
            </FormControl>

            <ToggleButtonGroup
              value={searchMode}
              exclusive
              onChange={handleSearchModeChange}
              size="small"
              aria-label="search mode"
            >
              <ToggleButton value="file" aria-label="file search">
                File Search
              </ToggleButton>
              <ToggleButton value="directory" aria-label="directory search">
                Directory Search
              </ToggleButton>
            </ToggleButtonGroup>
          </>
        )}

        {error && (
          <ApiErrorAlert
            error={error}
            onRetry={selectedDirectory ? loadLogFiles : loadLogDirectories}
            title="Error loading data"
          />
        )}
      </Box>

      {selectedDirectory && searchMode === "directory" && (
        <Box sx={{ mb: 2 }}>
          <Box
            component="form"
            onSubmit={handleDirectorySearchSubmit}
            sx={{ mb: 2 }}
          >
            <TextField
              fullWidth
              size="small"
              placeholder='Search across all files (use ".." to search multiple terms on same line, e.g., "10:35 .. AMD")'
              value={directorySearchQuery}
              helperText='Tip: Use "..", "&", or "," to search for multiple terms that must appear on the same line'
              onChange={(e) => setDirectorySearchQuery(e.target.value)}
              disabled={loadingDirectorySearch}
              InputProps={{
                startAdornment: (
                  <InputAdornment position="start">
                    {loadingDirectorySearch ? (
                      <CircularProgress size={20} />
                    ) : (
                      <SearchIcon />
                    )}
                  </InputAdornment>
                ),
                endAdornment: directorySearchQuery &&
                  !loadingDirectorySearch && (
                    <InputAdornment position="end">
                      <IconButton
                        size="small"
                        onClick={() => {
                          setDirectorySearchQuery("");
                          setDirectorySearchData(null);
                        }}
                        edge="end"
                      >
                        <ClearIcon fontSize="small" />
                      </IconButton>
                    </InputAdornment>
                  ),
              }}
            />
          </Box>

          {loadingDirectorySearch && !directorySearchData && (
            <Box sx={{ p: 3, textAlign: "center" }}>
              <CircularProgress sx={{ mb: 2 }} />
              <Typography variant="body2" color="text.secondary">
                Searching across all files...
              </Typography>
            </Box>
          )}

          {directorySearchData && !loadingDirectorySearch && (
            <DirectorySearchResults
              results={directorySearchData.results}
              totalResults={directorySearchData.totalResults}
              page={directorySearchData.page}
              perPage={directorySearchData.perPage}
              totalPages={directorySearchData.totalPages}
              searchQuery={directorySearchData.searchQuery}
              filesSearched={directorySearchData.filesSearched}
              onPageChange={(page) =>
                handleDirectorySearch(directorySearchQuery, page)
              }
              onResultClick={handleResultClick}
              loading={loadingDirectorySearch}
            />
          )}

          {!directorySearchData &&
            !loadingDirectorySearch &&
            directorySearchQuery && (
              <Box sx={{ p: 2, textAlign: "center" }}>
                <Typography variant="body2" color="text.secondary">
                  Enter a search query and press Enter to search across all
                  files
                </Typography>
              </Box>
            )}
        </Box>
      )}

      {selectedFile && logData && searchMode === "file" && (
        <Box>
          {cameFromSearch && (
            <Box sx={{ mb: 2, display: "flex", alignItems: "center", gap: 1 }}>
              <Button
                variant="outlined"
                size="small"
                startIcon={<ArrowBackIcon />}
                onClick={handleBackToSearch}
              >
                Back to Search Results
              </Button>
              <Chip
                label={`Viewing from search: "${directorySearchQuery}"`}
                size="small"
                color="primary"
                variant="outlined"
                onDelete={handleBackToSearch}
              />
            </Box>
          )}
          <LogViewer
            lines={logData.lines}
            totalLines={logData.totalLines}
            originalTotalLines={logData.originalTotalLines}
            page={logData.page}
            perPage={logData.perPage}
            totalPages={logData.totalPages}
            fileName={selectedFile}
            searchQuery={searchQuery}
            onSearchChange={setSearchQuery}
            onPageChange={handlePageChange}
            onLoadPage={loadLogContent}
            loading={loadingContent}
            targetLineNumber={targetLineNumber}
          />
        </Box>
      )}
    </Box>
  );
}
