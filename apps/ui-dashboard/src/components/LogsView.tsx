import { useState, useEffect } from 'react'
import {
  Box,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Typography,
  IconButton,
  Tooltip,
} from '@mui/material'
import RefreshIcon from '@mui/icons-material/Refresh'
import { getLogDirectories, getLogFiles, getLogContent } from '../services/api'
import type { ApiError } from '../types/api'
import LoadingSpinner from './LoadingSpinner'
import ApiErrorAlert from './ApiErrorAlert'
import LogViewer from './LogViewer'

interface LogsViewProps {
  portfolioId: string
}

export default function LogsView({ portfolioId }: LogsViewProps) {
  const [logDirectories, setLogDirectories] = useState<string[]>([])
  const [selectedDirectory, setSelectedDirectory] = useState<string>('')
  const [logFiles, setLogFiles] = useState<string[]>([])
  const [selectedFile, setSelectedFile] = useState<string>('')
  const [logData, setLogData] = useState<{
    lines: Array<{ lineNumber: number; content: string }>
    totalLines: number
    originalTotalLines: number
    page: number
    perPage: number
    totalPages: number
  } | null>(null)
  const [loading, setLoading] = useState(true)
  const [loadingFiles, setLoadingFiles] = useState(false)
  const [loadingContent, setLoadingContent] = useState(false)
  const [error, setError] = useState<ApiError | null>(null)
  const [searchQuery, setSearchQuery] = useState<string>('')

  // Load log directories on mount
  useEffect(() => {
    if (portfolioId) {
      loadLogDirectories()
    }
  }, [portfolioId])

  // Load files when directory changes
  useEffect(() => {
    if (selectedDirectory) {
      loadLogFiles()
      setSelectedFile('')
      setLogData(null)
    }
  }, [selectedDirectory])

  // Load content when file changes
  useEffect(() => {
    if (selectedFile && selectedDirectory) {
      loadLogContent(1, searchQuery)
    }
  }, [selectedFile])

  const loadLogDirectories = async () => {
    try {
      setLoading(true)
      setError(null)
      const response = await getLogDirectories(portfolioId)
      setLogDirectories(response.directories)
      
      // Auto-select if only one directory
      if (response.directories.length === 1) {
        setSelectedDirectory(response.directories[0])
      }
    } catch (err) {
      setError(err as ApiError)
    } finally {
      setLoading(false)
    }
  }

  const loadLogFiles = async () => {
    try {
      setLoadingFiles(true)
      setError(null)
      const response = await getLogFiles(portfolioId, selectedDirectory)
      setLogFiles(response.files)
      
      // Auto-select if only one file
      if (response.files.length === 1) {
        setSelectedFile(response.files[0])
      }
    } catch (err) {
      setError(err as ApiError)
    } finally {
      setLoadingFiles(false)
    }
  }

  const loadLogContent = async (page: number = 1, search: string = '') => {
    if (!selectedFile || !selectedDirectory) return

    try {
      setLoadingContent(true)
      setError(null)
      const response = await getLogContent(
        portfolioId,
        selectedDirectory,
        selectedFile,
        page,
        1000, // per_page
        search || undefined
      )
      setLogData({
        lines: response.lines,
        totalLines: response.totalLines,
        originalTotalLines: response.originalTotalLines,
        page: response.page,
        perPage: response.perPage,
        totalPages: response.totalPages,
      })
    } catch (err) {
      setError(err as ApiError)
    } finally {
      setLoadingContent(false)
    }
  }

  const handleDirectoryChange = (directory: string) => {
    setSelectedDirectory(directory)
    setSearchQuery('')
  }

  const handleFileClick = (file: string) => {
    setSelectedFile(file)
    setSearchQuery('')
  }

  const handlePageChange = async (newPage: number) => {
    await loadLogContent(newPage, searchQuery)
  }

  if (loading) {
    return <LoadingSpinner message="Loading log directories..." />
  }

  if (error && !logDirectories.length) {
    return (
      <ApiErrorAlert error={error} onRetry={loadLogDirectories} title="Failed to load log directories" />
    )
  }

  return (
    <Box>
      <Box sx={{ display: 'flex', gap: 2, alignItems: 'center', mb: 2, flexWrap: 'wrap' }}>
        <Typography variant="body2" color="text.secondary" sx={{ minWidth: 'fit-content' }}>
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
          <FormControl size="small" sx={{ minWidth: 200 }}>
            <InputLabel id="log-file-select-label">File</InputLabel>
            <Select
              labelId="log-file-select-label"
              id="log-file-select"
              value={selectedFile}
              label="File"
              onChange={(e) => handleFileClick(e.target.value)}
              disabled={loadingFiles || logFiles.length === 0}
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
        )}

        {error && (
          <ApiErrorAlert
            error={error}
            onRetry={selectedDirectory ? loadLogFiles : loadLogDirectories}
            title="Error loading data"
          />
        )}
      </Box>

      {selectedFile && logData && (
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
        />
      )}
    </Box>
  )
}

