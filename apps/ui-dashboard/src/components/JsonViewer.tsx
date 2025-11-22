import { useState, useMemo } from "react";
import { Box, Paper, Typography, IconButton, Collapse } from "@mui/material";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import ExpandLessIcon from "@mui/icons-material/ExpandLess";
import { useTheme } from "@mui/material/styles";

interface JsonViewerProps {
  data: unknown;
  fileName?: string;
  searchQuery?: string;
}

function JsonNode({
  data,
  path = "",
  level = 0,
  searchQuery = "",
}: {
  data: unknown;
  path?: string;
  level?: number;
  searchQuery?: string;
}) {
  const [expanded, setExpanded] = useState(level < 2); // Auto-expand first 2 levels
  const theme = useTheme();
  const indent = level * 20;

  // Check if this node or its children match the search query
  const hasMatch = useMemo(() => {
    if (!searchQuery) return true;
    const query = searchQuery.toLowerCase();
    const jsonString = JSON.stringify(data).toLowerCase();
    return jsonString.includes(query);
  }, [data, searchQuery]);

  // Highlight matching text
  const highlightText = (text: string): React.ReactNode => {
    if (!searchQuery) return text;
    const query = searchQuery.toLowerCase();
    const lowerText = text.toLowerCase();
    const index = lowerText.indexOf(query);

    if (index === -1) return text;

    const before = text.substring(0, index);
    const match = text.substring(index, index + searchQuery.length);
    const after = text.substring(index + searchQuery.length);

    return (
      <>
        {before}
        <Box
          component="span"
          sx={{ backgroundColor: theme.palette.warning.light, fontWeight: 600 }}
        >
          {match}
        </Box>
        {after}
      </>
    );
  };

  const handleToggle = () => {
    setExpanded(!expanded);
  };

  if (data === null) {
    if (!hasMatch && searchQuery) return null;
    return (
      <Box
        component="span"
        sx={{ color: theme.palette.text.secondary, fontStyle: "italic" }}
      >
        null
      </Box>
    );
  }

  if (typeof data === "string") {
    if (!hasMatch && searchQuery) return null;
    const highlighted = highlightText(data);
    return (
      <Box component="span" sx={{ color: theme.palette.success.main }}>
        "{typeof highlighted === "string" ? highlighted : highlighted}"
      </Box>
    );
  }

  if (typeof data === "number" || typeof data === "boolean") {
    const strValue = String(data);
    if (!hasMatch && searchQuery) return null;
    return (
      <Box component="span" sx={{ color: theme.palette.info.main }}>
        {highlightText(strValue)}
      </Box>
    );
  }

  if (Array.isArray(data)) {
    if (data.length === 0) {
      if (!hasMatch && searchQuery) return null;
      return (
        <Box component="span" sx={{ color: theme.palette.text.secondary }}>
          []
        </Box>
      );
    }

    // Filter items that match search query
    const filteredItems = searchQuery
      ? (data
          .map((item, index) => {
            const itemJson = JSON.stringify(item).toLowerCase();
            return itemJson.includes(searchQuery.toLowerCase())
              ? { item, index }
              : null;
          })
          .filter(Boolean) as Array<{ item: unknown; index: number }>)
      : data.map((item, index) => ({ item, index }));

    if (filteredItems.length === 0 && searchQuery) return null;

    // Auto-expand if searching
    const shouldExpand =
      expanded || !!(searchQuery && filteredItems.length > 0);

    return (
      <Box>
        <Box sx={{ display: "flex", alignItems: "center", ml: `${indent}px` }}>
          <IconButton size="small" onClick={handleToggle} sx={{ p: 0.5 }}>
            {shouldExpand ? (
              <ExpandLessIcon fontSize="small" />
            ) : (
              <ExpandMoreIcon fontSize="small" />
            )}
          </IconButton>
          <Typography component="span" variant="body2" sx={{ fontWeight: 600 }}>
            [{data.length}]
            {searchQuery && filteredItems.length < data.length && (
              <Typography
                component="span"
                variant="body2"
                sx={{ color: theme.palette.text.secondary, ml: 1 }}
              >
                ({filteredItems.length} matches)
              </Typography>
            )}
          </Typography>
        </Box>
        <Collapse in={shouldExpand}>
          <Box sx={{ ml: `${indent + 24}px` }}>
            {filteredItems.map(({ item, index }) => (
              <Box key={index} sx={{ mb: 0.5 }}>
                <Typography
                  component="span"
                  variant="body2"
                  sx={{ color: theme.palette.text.secondary }}
                >
                  {index}:
                </Typography>{" "}
                <JsonNode
                  data={item}
                  path={`${path}[${index}]`}
                  level={level + 1}
                  searchQuery={searchQuery}
                />
              </Box>
            ))}
          </Box>
        </Collapse>
      </Box>
    );
  }

  if (typeof data === "object") {
    const keys = Object.keys(data);
    if (keys.length === 0) {
      if (!hasMatch && searchQuery) return null;
      return (
        <Box component="span" sx={{ color: theme.palette.text.secondary }}>
          {"{}"}
        </Box>
      );
    }

    // Filter keys that match search query
    const filteredKeys = searchQuery
      ? keys.filter((key) => {
          const keyMatches = key
            .toLowerCase()
            .includes(searchQuery.toLowerCase());
          const valueJson = JSON.stringify(
            (data as Record<string, unknown>)[key]
          ).toLowerCase();
          const valueMatches = valueJson.includes(searchQuery.toLowerCase());
          return keyMatches || valueMatches;
        })
      : keys;

    if (filteredKeys.length === 0 && searchQuery) return null;

    // Auto-expand if searching
    const shouldExpand = expanded || !!(searchQuery && filteredKeys.length > 0);

    return (
      <Box>
        <Box sx={{ display: "flex", alignItems: "center", ml: `${indent}px` }}>
          <IconButton size="small" onClick={handleToggle} sx={{ p: 0.5 }}>
            {shouldExpand ? (
              <ExpandLessIcon fontSize="small" />
            ) : (
              <ExpandMoreIcon fontSize="small" />
            )}
          </IconButton>
          <Typography component="span" variant="body2" sx={{ fontWeight: 600 }}>
            {"{"} {keys.length} {keys.length === 1 ? "key" : "keys"} {"}"}
            {searchQuery && filteredKeys.length < keys.length && (
              <Typography
                component="span"
                variant="body2"
                sx={{ color: theme.palette.text.secondary, ml: 1 }}
              >
                ({filteredKeys.length} matches)
              </Typography>
            )}
          </Typography>
        </Box>
        <Collapse in={shouldExpand}>
          <Box sx={{ ml: `${indent + 24}px` }}>
            {filteredKeys.map((key) => {
              const keyMatches =
                searchQuery &&
                key.toLowerCase().includes(searchQuery.toLowerCase());
              return (
                <Box key={key} sx={{ mb: 0.5 }}>
                  <Typography
                    component="span"
                    variant="body2"
                    sx={{ color: theme.palette.primary.main, fontWeight: 600 }}
                  >
                    "{keyMatches ? highlightText(key) : key}":
                  </Typography>{" "}
                  <JsonNode
                    data={(data as Record<string, unknown>)[key]}
                    path={`${path}.${key}`}
                    level={level + 1}
                    searchQuery={searchQuery}
                  />
                </Box>
              );
            })}
          </Box>
        </Collapse>
      </Box>
    );
  }

  return <Box component="span">{String(data)}</Box>;
}

export default function JsonViewer({
  data,
  searchQuery = "",
}: JsonViewerProps) {
  return (
    <Paper sx={{ p: 2, maxHeight: "70vh", overflow: "auto" }}>
      <JsonNode data={data} searchQuery={searchQuery} />
    </Paper>
  );
}
