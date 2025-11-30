import { useEffect, useRef } from 'react'
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
  targetLineNumber?: number | null
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
  targetLineNumber = null,
}: LogViewerProps) {
  const theme = useTheme()
  const logViewerRef = useRef<HTMLDivElement>(null)
  const targetLineRef = useRef<HTMLDivElement>(null)

  // Scroll to target line when it's available
  useEffect(() => {
    if (targetLineNumber !== null && !loading && targetLineRef.current) {
      setTimeout(() => {
        targetLineRef.current?.scrollIntoView({
          behavior: 'smooth',
          block: 'center',
        })
      }, 100)
    }
  }, [targetLineNumber, lines, loading])

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
          {targetLineNumber !== null && (
            <Chip
              label={`📍 Target: Line ${targetLineNumber}`}
              color="warning"
              size="small"
              sx={{
                fontWeight: 600,
                animation: 'pulse 2s infinite',
                '@keyframes pulse': {
                  '0%, 100%': {
                    opacity: 1,
                  },
                  '50%': {
                    opacity: 0.7,
                  },
                },
              }}
            />
          )}
          {searchQuery && (
            <>
              <Chip
                label={`${lines.filter(l => l.isMatch).length} match${lines.filter(l => l.isMatch).length !== 1 ? 'es' : ''} shown`}
                color="primary"
                size="small"
                variant="outlined"
              />
              <Chip
                label={`${totalLines} total lines with context`}
                onDelete={handleClearSearch}
                color="secondary"
                size="small"
              />
            </>
          )}
          <Typography variant="body2" color="text.secondary">
            {searchQuery 
              ? `Showing ${lines.length} line${lines.length !== 1 ? 's' : ''} (${originalTotalLines} total in file)`
              : `Lines ${((page - 1) * perPage) + 1}-${Math.min(page * perPage, totalLines)} of ${totalLines}`
            }
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
          placeholder='Search in log file (use ".." for multiple terms on same line, e.g., "10:35 .. AMD")'
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
        ref={logViewerRef}
        sx={{
          height: '75vh',
          border: '1px solid',
          borderColor: 'divider',
          borderRadius: 1,
          overflow: 'auto',
          position: 'relative',
          backgroundColor: theme.palette.mode === 'dark' ? '#1e1e1e' : '#ffffff',
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
          <Box
            component="pre"
            sx={{
              margin: 0,
              padding: '12px',
              fontFamily: 'monospace',
              fontSize: '0.875rem',
              lineHeight: '1.6',
              whiteSpace: 'pre-wrap',
              wordBreak: 'break-word',
              color: theme.palette.text.primary,
            }}
          >
            {lines.map((line, index) => {
              const isTargetLine = targetLineNumber !== null && line.originalLineNumber === targetLineNumber
              
              return (
                <Box
                  key={`${line.originalLineNumber}-${index}`}
                  ref={isTargetLine ? targetLineRef : null}
                  component="div"
                  sx={{
                    padding: '2px 4px',
                    margin: '1px 0',
                    backgroundColor: isTargetLine
                      ? theme.palette.mode === 'dark'
                        ? 'rgba(255, 193, 7, 0.3)'
                        : 'rgba(255, 193, 7, 0.25)'
                      : line.isMatch && searchQuery
                      ? theme.palette.mode === 'dark'
                        ? 'rgba(144, 202, 249, 0.15)'
                        : 'rgba(25, 118, 210, 0.1)'
                      : 'transparent',
                    borderLeft: isTargetLine
                      ? `4px solid ${theme.palette.warning.main}`
                      : line.isMatch && searchQuery
                      ? `3px solid ${theme.palette.primary.main}`
                      : 'none',
                    borderRadius: '2px',
                    fontWeight: isTargetLine ? 600 : line.isMatch && searchQuery ? 500 : 400,
                    color: isTargetLine
                      ? theme.palette.warning.main
                      : line.isMatch && searchQuery
                      ? theme.palette.primary.main
                      : theme.palette.text.primary,
                    transition: 'all 0.2s ease-in-out',
                    '&:hover': {
                      backgroundColor: theme.palette.mode === 'dark'
                        ? 'rgba(255, 255, 255, 0.05)'
                        : 'rgba(0, 0, 0, 0.03)',
                    },
                  }}
                >
                  {line.content}
                </Box>
              )
            })}
          </Box>
        )}
      </Box>
    </Box>
  )
}
