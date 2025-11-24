import { useMemo, useState } from "react";
import { Paper, Box, Button, ButtonGroup } from "@mui/material";
import { useTheme } from "@mui/material/styles";
import JsonView from "@uiw/react-json-view";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import ExpandLessIcon from "@mui/icons-material/ExpandLess";

interface JsonViewerProps {
  data: unknown;
  fileName?: string;
  searchQuery?: string;
}

export default function JsonViewer({
  data,
  searchQuery = "",
}: JsonViewerProps) {
  const theme = useTheme();
  const isDark = theme.palette.mode === "dark";
  const [collapsed, setCollapsed] = useState<number | boolean>(2);

  // Filter data based on search query if provided
  const filteredData = useMemo(() => {
    if (!searchQuery) return data;

    const query = searchQuery.toLowerCase();
    const jsonString = JSON.stringify(data).toLowerCase();

    // If search query doesn't match, return null to show nothing
    if (!jsonString.includes(query)) {
      return null;
    }

    // For now, return the full data and let the browser's find feature handle search
    // The library doesn't have built-in search, but we can highlight matches
    return data;
  }, [data, searchQuery]);

  const handleExpandAll = () => {
    setCollapsed(false);
  };

  const handleCollapseAll = () => {
    setCollapsed(true);
  };

  // Custom theme colors based on Material-UI theme
  const customTheme = useMemo(() => {
    if (isDark) {
      return {
        "--w-rjv-font-family": "monospace",
        "--w-rjv-font-size": "14px",
        "--w-rjv-line-height": "1.5",
        "--w-rjv-curlybraces-color": theme.palette.text.primary,
        "--w-rjv-colon-color": theme.palette.text.secondary,
        "--w-rjv-brackets-color": theme.palette.text.primary,
        "--w-rjv-ellipsis-color": theme.palette.text.secondary,
        "--w-rjv-quotes-color": theme.palette.success.main,
        "--w-rjv-quotes-string-color": theme.palette.success.light,
        "--w-rjv-type-string-color": theme.palette.success.main,
        "--w-rjv-type-int-color": theme.palette.info.main,
        "--w-rjv-type-float-color": theme.palette.info.main,
        "--w-rjv-type-bigint-color": theme.palette.info.main,
        "--w-rjv-type-boolean-color": theme.palette.warning.main,
        "--w-rjv-type-date-color": theme.palette.text.secondary,
        "--w-rjv-type-null-color": theme.palette.text.secondary,
        "--w-rjv-type-nan-color": theme.palette.error.main,
        "--w-rjv-type-undefined-color": theme.palette.text.secondary,
        "--w-rjv-background-color": theme.palette.background.paper,
        "--w-rjv-border-color": theme.palette.divider,
        "--w-rjv-key-string": theme.palette.primary.main,
        "--w-rjv-arrow-color": theme.palette.text.secondary,
        "--w-rjv-edit-color": theme.palette.primary.main,
        "--w-rjv-info-color": theme.palette.text.secondary,
        "--w-rjv-update-color": theme.palette.success.main,
        "--w-rjv-copied-color": theme.palette.success.main,
        "--w-rjv-copy-color": theme.palette.text.secondary,
        "--w-rjv-edit-bg-color": theme.palette.action.hover,
        "--w-rjv-edit-tag-color": theme.palette.primary.main,
        "--w-rjv-edit-tag-edit-color": theme.palette.primary.main,
        "--w-rjv-edit-tag-input-bg-color": theme.palette.background.paper,
        "--w-rjv-edit-tag-input-border-color": theme.palette.divider,
        "--w-rjv-edit-tag-input-color": theme.palette.text.primary,
      };
    } else {
      return {
        "--w-rjv-font-family": "monospace",
        "--w-rjv-font-size": "14px",
        "--w-rjv-line-height": "1.5",
        "--w-rjv-curlybraces-color": theme.palette.text.primary,
        "--w-rjv-colon-color": theme.palette.text.secondary,
        "--w-rjv-brackets-color": theme.palette.text.primary,
        "--w-rjv-ellipsis-color": theme.palette.text.secondary,
        "--w-rjv-quotes-color": theme.palette.success.main,
        "--w-rjv-quotes-string-color": theme.palette.success.dark,
        "--w-rjv-type-string-color": theme.palette.success.dark,
        "--w-rjv-type-int-color": theme.palette.info.main,
        "--w-rjv-type-float-color": theme.palette.info.main,
        "--w-rjv-type-bigint-color": theme.palette.info.main,
        "--w-rjv-type-boolean-color": theme.palette.warning.main,
        "--w-rjv-type-date-color": theme.palette.text.secondary,
        "--w-rjv-type-null-color": theme.palette.text.secondary,
        "--w-rjv-type-nan-color": theme.palette.error.main,
        "--w-rjv-type-undefined-color": theme.palette.text.secondary,
        "--w-rjv-background-color": theme.palette.background.paper,
        "--w-rjv-border-color": theme.palette.divider,
        "--w-rjv-key-string": theme.palette.primary.main,
        "--w-rjv-arrow-color": theme.palette.text.secondary,
        "--w-rjv-edit-color": theme.palette.primary.main,
        "--w-rjv-info-color": theme.palette.text.secondary,
        "--w-rjv-update-color": theme.palette.success.main,
        "--w-rjv-copied-color": theme.palette.success.main,
        "--w-rjv-copy-color": theme.palette.text.secondary,
        "--w-rjv-edit-bg-color": theme.palette.action.hover,
        "--w-rjv-edit-tag-color": theme.palette.primary.main,
        "--w-rjv-edit-tag-edit-color": theme.palette.primary.main,
        "--w-rjv-edit-tag-input-bg-color": theme.palette.background.paper,
        "--w-rjv-edit-tag-input-border-color": theme.palette.divider,
        "--w-rjv-edit-tag-input-color": theme.palette.text.primary,
      };
    }
  }, [theme, isDark]);

  return (
    <Paper sx={{ p: 2, maxHeight: "70vh", overflow: "auto" }}>
      <Box
        sx={{
          mb: 1,
          display: "flex",
          justifyContent: "flex-end",
        }}
      >
        <ButtonGroup size="small" variant="outlined">
          <Button
            startIcon={<ExpandMoreIcon />}
            onClick={handleExpandAll}
            disabled={filteredData === null}
          >
            Expand All
          </Button>
          <Button
            startIcon={<ExpandLessIcon />}
            onClick={handleCollapseAll}
            disabled={filteredData === null}
          >
            Collapse All
          </Button>
        </ButtonGroup>
      </Box>
      <Box
        sx={{
          ...customTheme,
          "& .w-rjv": {
            fontFamily: "monospace",
          },
        }}
      >
        {filteredData === null && searchQuery ? (
          <Box sx={{ p: 2, textAlign: "center", color: "text.secondary" }}>
            No results found for "{searchQuery}"
          </Box>
        ) : (
          <JsonView
            value={filteredData as object}
            style={{
              ...customTheme,
              backgroundColor: "transparent",
            }}
            displayDataTypes={false}
            displayObjectSize={true}
            enableClipboard={true}
            collapsed={collapsed}
          />
        )}
      </Box>
    </Paper>
  );
}
