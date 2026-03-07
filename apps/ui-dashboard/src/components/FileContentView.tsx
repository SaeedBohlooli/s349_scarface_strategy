import { useState, useEffect, useMemo } from "react";
import {
  Typography,
  Box,
  Paper,
  TextField,
  InputAdornment,
  IconButton,
  Tooltip,
} from "@mui/material";
import SearchIcon from "@mui/icons-material/Search";
import RefreshIcon from "@mui/icons-material/Refresh";
import { getContentByPath } from "../services/api";
import type { ApiError } from "../types/api";
import { isTableSuitable } from "../utils/dataUtils";
import LoadingSpinner from "./LoadingSpinner";
import ApiErrorAlert from "./ApiErrorAlert";
import DataTable from "./DataTable";
import JsonViewer from "./JsonViewer";

interface FileContentViewProps {
  portfolioId: string;
  /** Relative path to file under portfolio (e.g. intermediate/84-20260305-102912-2418-7-NVDA.json) */
  filePath: string;
}

export default function FileContentView({
  portfolioId,
  filePath,
}: FileContentViewProps) {
  const fileName = filePath.split("/").pop() || filePath;
  const [rawData, setRawData] = useState<unknown>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<ApiError | null>(null);
  const [searchQuery, setSearchQuery] = useState<string>("");

  useEffect(() => {
    loadFileContent();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [portfolioId, filePath]);

  const loadFileContent = async () => {
    try {
      setLoading(true);
      setError(null);
      const body = await getContentByPath(portfolioId, filePath);
      if (body == null) {
        setRawData(null);
        return;
      }
      // API returns { data, count } for JSON/CSV and { content } for raw (e.g. .log)
      if (typeof body === "object" && "content" in body && typeof (body as { content: string }).content === "string") {
        setRawData(body);
        return;
      }
      if (typeof body === "object" && "data" in body && Array.isArray((body as { data: unknown }).data)) {
        setRawData((body as { data: unknown }).data);
        return;
      }
      setRawData(body);
    } catch (err) {
      setError(err as ApiError);
    } finally {
      setLoading(false);
    }
  };

  // Normalize: rawData can be array (table), { content: string } (raw text), or object (JSON)
  const { isTable, tableData, isRawText, rawTextContent } = useMemo(() => {
    if (rawData == null) {
      return { isTable: false, tableData: [], isRawText: false, rawTextContent: "" };
    }
    const isRaw = typeof rawData === "object" && "content" in rawData && typeof (rawData as { content: string }).content === "string";
    if (isRaw) {
      return { isTable: false, tableData: [], isRawText: true, rawTextContent: (rawData as { content: string }).content };
    }
    const suitable = isTableSuitable(rawData);
    return {
      isTable: suitable,
      tableData: suitable && Array.isArray(rawData) ? (rawData as Record<string, unknown>[]) : [],
      isRawText: false,
      rawTextContent: "",
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
              {isTable ? `${tableData.length} rows` : isRawText ? "Log / text file" : "JSON data"}
            </Typography>
          </Box>
          <Tooltip title="Refresh data">
            <IconButton
              size="small"
              onClick={loadFileContent}
              disabled={loading}
              sx={{ ml: 2 }}
            >
              <RefreshIcon />
            </IconButton>
          </Tooltip>
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
      {rawData == null && !loading && !error ? (
        <Typography color="text.secondary">No content</Typography>
      ) : isTable ? (
        <DataTable
          data={tableData}
          fileName={fileName}
          searchQuery={searchQuery}
        />
      ) : isRawText ? (
        <Paper component="pre" sx={{ p: 2, maxHeight: "70vh", overflow: "auto", fontFamily: "monospace", fontSize: "0.8125rem", whiteSpace: "pre-wrap", wordBreak: "break-all" }}>
          {rawTextContent}
        </Paper>
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
