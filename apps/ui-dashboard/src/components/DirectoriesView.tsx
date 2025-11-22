import { useState, useEffect } from 'react'
import { Grid, Card, CardContent, Typography, List, ListItem, ListItemButton, Box } from '@mui/material'
import { getDirectories, getFiles } from '../services/api'
import type { ApiError } from '../types/api'
import { IGNORED_DIRECTORIES } from '../config/appConfig'
import LoadingSpinner from './LoadingSpinner'
import ApiErrorAlert from './ApiErrorAlert'

interface DirectoriesViewProps {
  portfolioId: string
  onFileClick: (directory: string, file: string) => void
}

interface DirectoryFiles {
  [directory: string]: {
    files: string[]
    loading: boolean
    error: ApiError | null
  }
}

export default function DirectoriesView({ portfolioId, onFileClick }: DirectoriesViewProps) {
  const [directories, setDirectories] = useState<string[]>([])
  const [directoryFiles, setDirectoryFiles] = useState<DirectoryFiles>({})
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<ApiError | null>(null)

  useEffect(() => {
    if (portfolioId) {
      loadDirectories()
    }
  }, [portfolioId])

  const loadDirectories = async () => {
    try {
      setLoading(true)
      setError(null)
      const response = await getDirectories()
      // Filter out ignored directories
      const filteredDirectories = response.directories.filter(
        (dir) => !IGNORED_DIRECTORIES.includes(dir as typeof IGNORED_DIRECTORIES[number])
      )
      setDirectories(filteredDirectories)
      
      // Load files for each directory
      filteredDirectories.forEach((dir) => {
        loadFilesForDirectory(dir)
      })
    } catch (err) {
      setError(err as ApiError)
    } finally {
      setLoading(false)
    }
  }

  const loadFilesForDirectory = async (directory: string) => {
    setDirectoryFiles((prev) => ({
      ...prev,
      [directory]: { files: [], loading: true, error: null },
    }))

    try {
      const response = await getFiles(directory, portfolioId)
      setDirectoryFiles((prev) => ({
        ...prev,
        [directory]: { files: response.files, loading: false, error: null },
      }))
    } catch (err) {
      setDirectoryFiles((prev) => ({
        ...prev,
        [directory]: { files: [], loading: false, error: err as ApiError },
      }))
    }
  }

  // Sort directories whenever directoryFiles changes
  useEffect(() => {
    setDirectories((prevDirs) => {
      // Check if all directories have finished loading
      const allLoaded = prevDirs.every(
        (dir) => !directoryFiles[dir]?.loading
      )
      
      if (!allLoaded) {
        // Don't sort while still loading
        return prevDirs
      }
      
      // Sort: non-empty directories first, empty at the end
      return [...prevDirs].sort((a, b) => {
        const aFiles = directoryFiles[a]?.files?.length || 0
        const bFiles = directoryFiles[b]?.files?.length || 0
        
        // Non-empty directories first
        if (aFiles > 0 && bFiles === 0) return -1
        if (aFiles === 0 && bFiles > 0) return 1
        
        // If both empty or both non-empty, maintain alphabetical order
        return a.localeCompare(b)
      })
    })
  }, [directoryFiles])

  if (loading) {
    return <LoadingSpinner message="Loading directories..." />
  }

  if (error) {
    return <ApiErrorAlert error={error} onRetry={loadDirectories} title="Failed to load directories" />
  }

  return (
    <Grid container spacing={3}>
      {directories.map((directory) => {
        const dirData = directoryFiles[directory] || { files: [], loading: false, error: null }
        
        return (
          <Grid item xs={12} md={4} key={directory}>
            <Card sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  {directory}
                </Typography>
                {dirData.loading ? (
                  <LoadingSpinner message="Loading files..." size={24} />
                ) : dirData.error ? (
                  <ApiErrorAlert
                    error={dirData.error}
                    onRetry={() => loadFilesForDirectory(directory)}
                    title="Failed to load files"
                  />
                ) : dirData.files.length === 0 ? (
                  <Typography variant="body2" color="text.secondary">
                    No files available
                  </Typography>
                ) : (
                  <List dense>
                    {dirData.files.map((file) => (
                      <ListItem key={file} disablePadding>
                        <ListItemButton onClick={() => onFileClick(directory, file)}>
                          <Typography variant="body2" noWrap sx={{ width: '100%' }}>
                            {file}
                          </Typography>
                        </ListItemButton>
                      </ListItem>
                    ))}
                  </List>
                )}
              </CardContent>
            </Card>
          </Grid>
        )
      })}
    </Grid>
  )
}

