import { useMemo, useState } from "react";
import { DataGrid } from "@mui/x-data-grid";
import { Box, Typography, IconButton, Tooltip } from "@mui/material";
import ViewColumnIcon from "@mui/icons-material/ViewColumn";
import ViewComfyIcon from "@mui/icons-material/ViewComfy";
import { toCamelCase, formatColumnHeader } from "../utils/stringUtils";

interface DataTableProps {
  data: Record<string, unknown>[];
  fileName?: string;
  searchQuery?: string;
}

// Define column type inline
type GridColumn = {
  field: string;
  headerName: string;
  width: number;
  minWidth: number;
  resizable: boolean;
  sortable: boolean;
  filterable: boolean;
};

export default function DataTable({
  data,
  fileName,
  searchQuery = "",
}: DataTableProps) {
  const [isCompact, setIsCompact] = useState(true);
  const [paginationModel, setPaginationModel] = useState({ page: 0, pageSize: 100 });
  
  const { columns, filteredRows } = useMemo(() => {
    if (!data || data.length === 0) {
      return { columns: [], filteredRows: [] };
    }

    // Get all unique keys from the data in order they appear (preserve server order)
    const keyOrder: string[] = [];
    const seenKeys = new Set<string>();
    
    // First, collect keys in the order they appear in the first row
    if (data.length > 0) {
      Object.keys(data[0]).forEach((key) => {
        if (!seenKeys.has(key)) {
          keyOrder.push(key);
          seenKeys.add(key);
        }
      });
    }
    
    // Then, add any keys from other rows that weren't in the first row
    data.forEach((row) => {
      Object.keys(row).forEach((key) => {
        if (!seenKeys.has(key)) {
          keyOrder.push(key);
          seenKeys.add(key);
        }
      });
    });

    // Create columns with transformed headers in the order they appear
    // Compact mode: smaller widths, normal mode: larger widths
    const defaultWidth = isCompact ? 120 : 200;
    const minWidth = isCompact ? 80 : 150;
    
    const cols: GridColumn[] = keyOrder.map((key) => {
      const camelCaseKey = toCamelCase(key);
      const displayHeader = formatColumnHeader(key);

      return {
        field: camelCaseKey,
        headerName: displayHeader,
        width: defaultWidth,
        minWidth: minWidth,
        resizable: true,
        sortable: true,
        filterable: true,
      };
    });

    // Transform rows to use camelCase keys
    const transformedRows = data.map((row, index) => {
      const transformedRow: Record<string, unknown> = { id: index };
      Object.keys(row).forEach((key) => {
        const camelCaseKey = toCamelCase(key);
        transformedRow[camelCaseKey] = row[key];
      });
      return transformedRow;
    });

    // Filter rows based on search query
    let filtered = transformedRows;
    if (searchQuery.trim()) {
      const query = searchQuery.toLowerCase();
      filtered = transformedRows.filter((row) => {
        // Search across all column values
        return Object.values(row).some((value) => {
          if (value === null || value === undefined) return false;
          const stringValue = String(value).toLowerCase();
          return stringValue.includes(query);
        });
      });
    }

    return { columns: cols, filteredRows: filtered };
  }, [data, searchQuery, isCompact]);

  if (!data || data.length === 0) {
    return (
      <Box sx={{ p: 3, textAlign: "center" }}>
        <Typography variant="body1" color="text.secondary">
          No data available
        </Typography>
      </Box>
    );
  }

  const rowHeight = isCompact ? 36 : 52;
  const footerHeight = 56;

  return (
    <Box sx={{ width: "100%" }}>
      <Box
        sx={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          mb: 1,
        }}
      >
        <Typography variant="body2" color="text.secondary" sx={{ flexGrow: 1 }}>
          {searchQuery.trim()
            ? `Showing ${filteredRows.length} of ${data.length} rows`
            : `Total rows: ${data.length}`}
        </Typography>
        <Tooltip title={isCompact ? "Switch to normal column width" : "Switch to compact column width"}>
          <IconButton
            size="small"
            onClick={() => setIsCompact(!isCompact)}
            sx={{ ml: 1 }}
          >
            {isCompact ? <ViewComfyIcon fontSize="small" /> : <ViewColumnIcon fontSize="small" />}
          </IconButton>
        </Tooltip>
      </Box>
      <Box
        sx={{
          height: "min(500px, calc(100vh - 280px))",
          minHeight: 300,
          overflow: "hidden",
          width: "100%",
        }}
      >
        <DataGrid
          rows={filteredRows}
          columns={columns}
          pagination={true}
          pageSizeOptions={[25, 50, 100, 200]}
          paginationModel={paginationModel}
          onPaginationModelChange={setPaginationModel}
          disableRowSelectionOnClick
          getRowHeight={() => rowHeight}
          sx={{
            height: "100%",
            width: "100%",
            "& .MuiDataGrid-main": {
              overflow: "auto",
            },
            "& .MuiDataGrid-virtualScroller": {
              overflow: "auto",
            },
            "& .MuiDataGrid-virtualScrollerContent": {
              minWidth: "max-content",
            },
            "& .MuiDataGrid-cell": {
              fontSize: isCompact ? "0.75rem" : "0.875rem",
              padding: isCompact ? "6px 8px" : "8px 16px",
              lineHeight: isCompact ? "1.2" : "1.5",
              display: "flex",
              alignItems: "center",
              whiteSpace: "nowrap",
              overflow: "hidden",
              textOverflow: "ellipsis",
            },
            "& .MuiDataGrid-columnHeaders": {
              fontSize: isCompact ? "0.75rem" : "0.875rem",
              fontWeight: 600,
              padding: isCompact ? "6px 8px" : "8px 16px",
              lineHeight: isCompact ? "1.2" : "1.5",
              minWidth: "max-content",
            },
            "& .MuiDataGrid-columnHeader": {
              display: "flex",
              alignItems: "center",
              justifyContent: "flex-start",
            },
            "& .MuiDataGrid-columnHeaderTitle": {
              textAlign: "left",
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
            },
            "& .MuiDataGrid-footerContainer": {
              borderTop: "1px solid",
              borderColor: "divider",
              display: "flex !important",
              minHeight: `${footerHeight}px`,
              flexShrink: 0,
            },
            "& .MuiDataGrid-row": {
              maxHeight: `${rowHeight}px !important`,
              minHeight: `${rowHeight}px !important`,
            },
            "& .MuiDataGrid-cellContent": {
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
            },
          }}
        />
      </Box>
      {fileName && (
        <Box sx={{ mt: 1 }}>
          <Typography variant="body2" color="text.secondary">
            File: {fileName}
          </Typography>
        </Box>
      )}
    </Box>
  );
}
