import { useMemo } from "react";
import { DataGrid } from "@mui/x-data-grid";
import { Box, Typography } from "@mui/material";
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
  const { columns, filteredRows } = useMemo(() => {
    if (!data || data.length === 0) {
      return { columns: [], filteredRows: [] };
    }

    // Get all unique keys from the data
    const allKeys = new Set<string>();
    data.forEach((row) => {
      Object.keys(row).forEach((key) => allKeys.add(key));
    });

    // Create columns with transformed headers
    const cols: GridColumn[] = Array.from(allKeys).map((key) => {
      const camelCaseKey = toCamelCase(key);
      const displayHeader = formatColumnHeader(key);

      return {
        field: camelCaseKey,
        headerName: displayHeader,
        width: 200,
        minWidth: 150,
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
  }, [data, searchQuery]);

  if (!data || data.length === 0) {
    return (
      <Box sx={{ p: 3, textAlign: "center" }}>
        <Typography variant="body1" color="text.secondary">
          No data available
        </Typography>
      </Box>
    );
  }

  return (
    <Box sx={{ height: "70vh", width: "100%", overflow: "auto" }}>
      <DataGrid
        rows={filteredRows}
        columns={columns}
        pageSizeOptions={[10, 25, 50, 100]}
        initialState={{
          pagination: {
            paginationModel: { pageSize: 25 },
          },
        }}
        disableRowSelectionOnClick
        sx={{
          "& .MuiDataGrid-cell": {
            fontSize: "0.875rem",
          },
          "& .MuiDataGrid-columnHeaders": {
            fontSize: "0.875rem",
            fontWeight: 600,
          },
          "& .MuiDataGrid-root": {
            minWidth: "fit-content",
          },
          "& .MuiDataGrid-virtualScroller": {
            overflowX: "auto",
          },
        }}
      />
      <Box
        sx={{
          mt: 1,
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
        }}
      >
        <Typography variant="body2" color="text.secondary">
          {searchQuery.trim()
            ? `Showing ${filteredRows.length} of ${data.length} rows`
            : `Total rows: ${data.length}`}
        </Typography>
        {fileName && (
          <Typography variant="body2" color="text.secondary">
            File: {fileName}
          </Typography>
        )}
      </Box>
    </Box>
  );
}
