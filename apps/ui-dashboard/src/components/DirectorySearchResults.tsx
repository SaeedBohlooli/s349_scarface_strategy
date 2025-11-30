import { useMemo } from "react";
import {
  Box,
  Typography,
  Paper,
  List,
  ListItem,
  ListItemText,
  Chip,
  Pagination,
  Button,
  Divider,
  IconButton,
  CircularProgress,
} from "@mui/material";
import NavigateNextIcon from "@mui/icons-material/NavigateNext";
import NavigateBeforeIcon from "@mui/icons-material/NavigateBefore";
import OpenInNewIcon from "@mui/icons-material/OpenInNew";
import { useTheme } from "@mui/material/styles";
import type { DirectorySearchResult } from "../types/api";

interface DirectorySearchResultsProps {
  results: DirectorySearchResult[];
  totalResults: number;
  page: number;
  perPage: number;
  totalPages: number;
  searchQuery: string;
  filesSearched: number;
  onPageChange: (page: number) => void;
  onResultClick: (fileName: string, lineNumber: number) => void;
  loading?: boolean;
}

export default function DirectorySearchResults({
  results,
  totalResults,
  page,
  perPage,
  totalPages,
  searchQuery,
  filesSearched,
  onPageChange,
  onResultClick,
  loading = false,
}: DirectorySearchResultsProps) {
  const theme = useTheme();

  // Group results by file
  const resultsByFile = useMemo(() => {
    const grouped: Record<string, DirectorySearchResult[]> = {};
    results.forEach((result) => {
      if (!grouped[result.fileName]) {
        grouped[result.fileName] = [];
      }
      grouped[result.fileName].push(result);
    });
    return grouped;
  }, [results]);

  const matchCount = useMemo(() => {
    return results.filter((r) => r.isMatch).length;
  }, [results]);

  return (
    <Box>
      <Box
        sx={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          mb: 2,
          flexWrap: "wrap",
          gap: 1,
        }}
      >
        <Box
          sx={{
            display: "flex",
            gap: 1,
            alignItems: "center",
            flexWrap: "wrap",
          }}
        >
          <Chip
            label={`${matchCount} match${matchCount !== 1 ? "es" : ""} found`}
            color="primary"
            size="small"
          />
          <Chip
            label={`${totalResults} total lines with context`}
            color="secondary"
            size="small"
            variant="outlined"
          />
          <Typography variant="body2" color="text.secondary">
            Across {filesSearched} file{filesSearched !== 1 ? "s" : ""}
          </Typography>
        </Box>
        <Box
          sx={{
            display: "flex",
            gap: 1,
            alignItems: "center",
            flexWrap: "wrap",
          }}
        >
          <Button
            size="small"
            disabled={page === 1 || loading}
            onClick={() => onPageChange(page - 1)}
            startIcon={<NavigateBeforeIcon />}
          >
            Prev
          </Button>
          <Pagination
            count={totalPages}
            page={page}
            onChange={(_, newPage) => onPageChange(newPage)}
            size="small"
            color="primary"
            disabled={loading}
            sx={{ "& .MuiPagination-ul": { flexWrap: "nowrap" } }}
          />
          <Button
            size="small"
            disabled={page >= totalPages || loading}
            onClick={() => onPageChange(page + 1)}
            endIcon={<NavigateNextIcon />}
          >
            Next
          </Button>
        </Box>
      </Box>

      {loading ? (
        <Box sx={{ p: 3, textAlign: "center" }}>
          <CircularProgress sx={{ mb: 2 }} />
          <Typography variant="body2" color="text.secondary">
            Loading search results...
          </Typography>
        </Box>
      ) : results.length === 0 ? (
        <Paper sx={{ p: 3, textAlign: "center" }}>
          <Typography variant="body2" color="text.secondary">
            No results found for "{searchQuery}"
          </Typography>
        </Paper>
      ) : (
        <Box sx={{ maxHeight: "75vh", overflow: "auto" }}>
          {Object.entries(resultsByFile).map(
            ([fileName, fileResults], fileIndex) => (
              <Paper key={fileName} sx={{ mb: 2, p: 2 }}>
                <Box
                  sx={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    mb: 1,
                  }}
                >
                  <Typography
                    variant="h6"
                    sx={{ fontSize: "1rem", fontWeight: 600 }}
                  >
                    {fileName}
                  </Typography>
                  <Chip
                    label={`${
                      fileResults.filter((r) => r.isMatch).length
                    } match${
                      fileResults.filter((r) => r.isMatch).length !== 1
                        ? "es"
                        : ""
                    }`}
                    size="small"
                    color="primary"
                    variant="outlined"
                  />
                </Box>
                <Divider sx={{ mb: 1 }} />
                <List dense>
                  {fileResults.map((result, index) => (
                    <ListItem
                      key={`${result.lineNumber}-${index}`}
                      sx={{
                        py: 0.5,
                        px: 1,
                        backgroundColor: result.isMatch
                          ? theme.palette.mode === "dark"
                            ? "rgba(144, 202, 249, 0.1)"
                            : "rgba(25, 118, 210, 0.08)"
                          : "transparent",
                        borderLeft: result.isMatch
                          ? `3px solid ${theme.palette.primary.main}`
                          : "3px solid transparent",
                        "&:hover": {
                          backgroundColor:
                            theme.palette.mode === "dark"
                              ? "rgba(255, 255, 255, 0.05)"
                              : "rgba(0, 0, 0, 0.04)",
                          cursor: "pointer",
                        },
                      }}
                      onClick={() =>
                        onResultClick(fileName, result.originalLineNumber)
                      }
                    >
                      <ListItemText
                        primary={
                          <Box
                            component="span"
                            sx={{
                              display: "flex",
                              alignItems: "center",
                              gap: 1,
                            }}
                          >
                            <Typography
                              variant="body2"
                              component="span"
                              sx={{
                                fontFamily: "monospace",
                                fontSize: "0.875rem",
                                color: result.isMatch
                                  ? theme.palette.primary.main
                                  : "text.secondary",
                                fontWeight: result.isMatch ? 600 : 400,
                              }}
                            >
                              {result.content}
                            </Typography>
                          </Box>
                        }
                        secondary={
                          <Box
                            component="span"
                            sx={{
                              display: "flex",
                              gap: 1,
                              alignItems: "center",
                              mt: 0.5,
                            }}
                          >
                            <Typography
                              variant="caption"
                              color="text.secondary"
                              component="span"
                            >
                              Line {result.originalLineNumber}
                            </Typography>
                            <Typography
                              variant="caption"
                              color="text.secondary"
                              component="span"
                            >
                              •
                            </Typography>
                            <Typography
                              variant="caption"
                              color="text.secondary"
                              component="span"
                            >
                              Page {result.page}
                            </Typography>
                            {result.isMatch && (
                              <>
                                <Typography
                                  variant="caption"
                                  color="text.secondary"
                                  component="span"
                                >
                                  •
                                </Typography>
                                <Chip
                                  label="Match"
                                  size="small"
                                  color="primary"
                                  sx={{ height: 18, fontSize: "0.65rem" }}
                                  component="span"
                                />
                              </>
                            )}
                            <IconButton
                              size="small"
                              sx={{ ml: "auto", p: 0.5 }}
                              onClick={(e) => {
                                e.stopPropagation();
                                onResultClick(
                                  fileName,
                                  result.originalLineNumber
                                );
                              }}
                              component="span"
                            >
                              <OpenInNewIcon fontSize="small" />
                            </IconButton>
                          </Box>
                        }
                      />
                    </ListItem>
                  ))}
                </List>
              </Paper>
            )
          )}
        </Box>
      )}
    </Box>
  );
}
