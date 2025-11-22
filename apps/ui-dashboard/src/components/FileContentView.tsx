import { useState, useEffect, useMemo } from "react";
import {
  Typography,
  Box,
  Paper,
  TextField,
  InputAdornment,
} from "@mui/material";
import SearchIcon from "@mui/icons-material/Search";
import { getFileContent } from "../services/api";
import type { ApiError } from "../types/api";
import { isTableSuitable } from "../utils/dataUtils";
import LoadingSpinner from "./LoadingSpinner";
import ApiErrorAlert from "./ApiErrorAlert";
import DataTable from "./DataTable";
import JsonViewer from "./JsonViewer";

interface FileContentViewProps {
  directory: string;
  portfolioId: string;
  fileName: string;
}

export default function FileContentView({
  directory,
  portfolioId,
  fileName,
}: FileContentViewProps) {
  const [rawData, setRawData] = useState<unknown>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<ApiError | null>(null);
  const [searchQuery, setSearchQuery] = useState<string>("");

  useEffect(() => {
    loadFileContent();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [directory, portfolioId, fileName]);

  const loadFileContent = async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await getFileContent(directory, portfolioId, fileName);
      setRawData(response.data);
    } catch (err) {
      setError(err as ApiError);
    } finally {
      setLoading(false);
    }
  };

  // Check if data is suitable for table display
  const { isTable, tableData } = useMemo(() => {
    const suitable = isTableSuitable(rawData);
    return {
      isTable: suitable,
      tableData:
        suitable && Array.isArray(rawData)
          ? (rawData as Record<string, unknown>[])
          : [],
    };
  }, [rawData]);

  if (loading) {
    return <LoadingSpinner message={`Loading ${fileName}...`} />;
  }

  if (error) {
    return (
      <ApiErrorAlert
        error={error}
        onRetry={loadFileContent}
        title={`Failed to load ${fileName}`}
      />
    );
  }

  return (
    <Box>
      <Paper sx={{ p: 2, mb: 2 }}>
        <Box
          sx={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "flex-start",
            mb: 2,
          }}
        >
          <Box>
            <Typography variant="h5" component="h2" gutterBottom>
              {fileName}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              {isTable && Array.isArray(rawData)
                ? `${rawData.length} rows`
                : "Complex JSON data"}
            </Typography>
          </Box>
        </Box>
        <TextField
          fullWidth
          size="small"
          placeholder="Search..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          InputProps={{
            startAdornment: (
              <InputAdornment position="start">
                <SearchIcon />
              </InputAdornment>
            ),
          }}
          sx={{ mb: 1 }}
        />
      </Paper>
      {isTable ? (
        <DataTable
          data={tableData}
          fileName={fileName}
          searchQuery={searchQuery}
        />
      ) : (
        <JsonViewer
          data={rawData}
          fileName={fileName}
          searchQuery={searchQuery}
        />
      )}
    </Box>
  );
}
