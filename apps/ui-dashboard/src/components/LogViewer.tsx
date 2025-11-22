import { useMemo } from 'react'
import { LogViewer } from '@patternfly/react-log-viewer'
import '@patternfly/react-log-viewer/dist/css/log-viewer.css'
import {
  Box,
  Typography,
  Button,
  Pagination,
  Chip,
  TextField,
  InputAdornment,
} from '@mui/material'
import NavigateNextIcon from '@mui/icons-material/NavigateNext'
import NavigateBeforeIcon from '@mui/icons-material/NavigateBefore'
import SearchIcon from '@mui/icons-material/Search'
import ClearIcon from '@mui/icons-material/Clear'
import IconButton from '@mui/material/IconButton'
import { useTheme } from '@mui/material/styles'
import type { LogLine } from '../types/api'

interface LogViewerProps {
  lines: LogLine[]
  totalLines: number
  originalTotalLines: number
  page: number
  perPage: number
  totalPages: number
  fileName?: string
  searchQuery: string
  onSearchChange: (query: string) => void
  onPageChange: (page: number) => void
  onLoadPage: (page: number, search?: string) => Promise<void>
  loading?: boolean
}

export default function PatternFlyLogViewer({
  lines,
  totalLines,
  originalTotalLines,
  page,
  perPage,
  totalPages,
  fileName,
  searchQuery,
  onSearchChange,
  onLoadPage,
  loading = false,
}: LogViewerProps) {
  const theme = useTheme()

  // Convert lines to string format for PatternFly LogViewer
  const logData = useMemo(() => {
    return lines.map((line) => line.content).join('\n')
  }, [lines])

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    const form = e.target as HTMLFormElement
    const input = form.querySelector('input') as HTMLInputElement
    if (input) {
      onSearchChange(input.value)
      onLoadPage(1, input.value)
    }
  }

  const handleClearSearch = () => {
    onSearchChange('')
    onLoadPage(1, '')
  }

  return (
    <Box>
      <Box
        sx={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          mb: 1,
          flexWrap: 'wrap',
          gap: 1,
        }}
      >
        <Box sx={{ display: 'flex', gap: 1, alignItems: 'center', flexWrap: 'wrap' }}>
          {searchQuery && (
            <Chip
              label={`${totalLines} match${totalLines !== 1 ? 'es' : ''} of ${originalTotalLines}`}
              onDelete={handleClearSearch}
              color="primary"
              size="small"
            />
          )}
          <Typography variant="body2" color="text.secondary">
            Lines {((page - 1) * perPage) + 1}-{Math.min(page * perPage, totalLines)} of {totalLines}
          </Typography>
        </Box>
        <Box sx={{ display: 'flex', gap: 1, alignItems: 'center', flexWrap: 'wrap' }}>
          <Button
            size="small"
            disabled={page === 1 || loading}
            onClick={() => onLoadPage(page - 1, searchQuery)}
            startIcon={<NavigateBeforeIcon />}
          >
            Prev
          </Button>
          <Pagination
            count={totalPages}
            page={page}
            onChange={(_, newPage) => onLoadPage(newPage, searchQuery)}
            size="small"
            color="primary"
            disabled={loading}
            sx={{ '& .MuiPagination-ul': { flexWrap: 'nowrap' } }}
          />
          <Button
            size="small"
            disabled={page >= totalPages || loading}
            onClick={() => onLoadPage(page + 1, searchQuery)}
            endIcon={<NavigateNextIcon />}
          >
            Next
          </Button>
        </Box>
      </Box>

      {/* Server-side search input */}
      <Box component="form" onSubmit={handleSearchSubmit} sx={{ mb: 1 }}>
        <TextField
          fullWidth
          size="small"
          placeholder="Search in log file (server-side)..."
          defaultValue={searchQuery}
          InputProps={{
            startAdornment: (
              <InputAdornment position="start">
                <SearchIcon />
              </InputAdornment>
            ),
            endAdornment: searchQuery && (
              <InputAdornment position="end">
                <IconButton size="small" onClick={handleClearSearch} edge="end">
                  <ClearIcon fontSize="small" />
                </IconButton>
              </InputAdornment>
            ),
          }}
          sx={{ mb: 1 }}
        />
      </Box>

      <Box
        sx={{
          height: '75vh',
          border: '1px solid',
          borderColor: 'divider',
          borderRadius: 1,
          overflow: 'hidden',
          '& .pf-v5-c-log-viewer': {
            height: '100%',
          },
          '& .pf-v5-c-log-viewer__header': {
            display: 'none',
          },
          '& .pf-v5-c-toolbar': {
            display: 'none',
          },
          '& .pf-v6-c-log-viewer__main': {
            padding: '6px',
          },
        }}
      >
        {loading ? (
          <Box
            sx={{
              display: 'flex',
              justifyContent: 'center',
              alignItems: 'center',
              height: '100%',
            }}
          >
            <Typography variant="body2" color="text.secondary">
              Loading...
            </Typography>
          </Box>
        ) : (
          <LogViewer
            data={logData}
            height="100%"
            theme={theme.palette.mode === 'dark' ? 'dark' : 'light'}
            isTextWrapped={false}
          />
        )}
      </Box>
    </Box>
  )
}
