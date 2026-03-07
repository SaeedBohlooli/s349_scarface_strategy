import { useState, useEffect } from 'react'
import {
  Grid,
  Card,
  CardContent,
  Typography,
  List,
  ListItem,
  ListItemButton,
  Box,
  IconButton,
  Tooltip,
  Breadcrumbs,
  Link,
} from '@mui/material'
import RefreshIcon from '@mui/icons-material/Refresh'
import FolderIcon from '@mui/icons-material/Folder'
import InsertDriveFileIcon from '@mui/icons-material/InsertDriveFile'
import { getBrowse } from '../services/api'
import type { ApiError } from '../types/api'
import LoadingSpinner from './LoadingSpinner'
import ApiErrorAlert from './ApiErrorAlert'

interface DirectoriesViewProps {
  portfolioId: string
  /** Current path under portfolio (e.g. '' or 'logs' or 'logs/2024') */
  currentPath: string
  /** Called when user selects a directory (navigate into it) */
  onPathChange: (newPath: string) => void
  /** Called when user selects a file (open file view) */
  onFileClick: (filePath: string) => void
}

export default function DirectoriesView({
  portfolioId,
  currentPath,
  onPathChange,
  onFileClick,
}: DirectoriesViewProps) {
  const [data, setData] = useState<{ directories: string[]; files: string[] } | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<ApiError | null>(null)

  useEffect(() => {
    if (portfolioId) {
      loadBrowse()
    }
  }, [portfolioId, currentPath])

  const loadBrowse = async () => {
    try {
      setLoading(true)
      setError(null)
      const response = await getBrowse(portfolioId, currentPath)
      setData({
        directories: response.directories,
        files: response.files,
      })
    } catch (err) {
      setError(err as ApiError)
      setData(null)
    } finally {
      setLoading(false)
    }
  }

  const pathSegments = currentPath ? currentPath.split('/').filter(Boolean) : []

  const handleDirectoryClick = (name: string) => {
    const newPath = currentPath ? `${currentPath}/${name}` : name
    onPathChange(newPath)
  }

  const handleFileClick = (name: string) => {
    const filePath = currentPath ? `${currentPath}/${name}` : name
    onFileClick(filePath)
  }

  if (loading) {
    return <LoadingSpinner message="Loading..." />
  }

  if (error) {
    return (
      <ApiErrorAlert
        error={error}
        onRetry={loadBrowse}
        title="Failed to load directory"
      />
    )
  }

  if (!data) {
    return null
  }

  const { directories, files } = data
  const hasItems = directories.length > 0 || files.length > 0

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2, flexWrap: 'wrap', gap: 1 }}>
        <Breadcrumbs aria-label="breadcrumb" sx={{ flexWrap: 'wrap' }}>
          <Link
            component="button"
            variant="body2"
            underline="hover"
            onClick={() => onPathChange('')}
            sx={{ cursor: 'pointer' }}
          >
            {portfolioId}
          </Link>
          {pathSegments.map((segment, i) => {
            const pathUpToHere = pathSegments.slice(0, i + 1).join('/')
            const isLast = i === pathSegments.length - 1
            return isLast ? (
              <Typography key={pathUpToHere} variant="body2" color="text.primary">
                {segment}
              </Typography>
            ) : (
              <Link
                key={pathUpToHere}
                component="button"
                variant="body2"
                underline="hover"
                onClick={() => onPathChange(pathUpToHere)}
                sx={{ cursor: 'pointer' }}
              >
                {segment}
              </Link>
            )
          })}
        </Breadcrumbs>
        <Tooltip title="Refresh">
          <IconButton size="small" onClick={loadBrowse} disabled={loading}>
            <RefreshIcon />
          </IconButton>
        </Tooltip>
      </Box>

      {!hasItems ? (
        <Typography color="text.secondary">No directories or files here.</Typography>
      ) : (
        <Grid container spacing={2}>
          {directories.length > 0 && (
            <Grid item xs={12} md={files.length > 0 ? 6 : 12}>
              <Card sx={{ height: '100%' }}>
                <CardContent>
                  <Typography variant="subtitle2" color="text.secondary" gutterBottom>
                    Directories
                  </Typography>
                  <List dense>
                    {directories.map((name) => (
                      <ListItem key={name} disablePadding>
                        <ListItemButton onClick={() => handleDirectoryClick(name)}>
                          <FolderIcon sx={{ mr: 1, color: 'action.active', fontSize: 20 }} />
                          <Typography variant="body2" noWrap sx={{ flex: 1 }}>
                            {name}
                          </Typography>
                        </ListItemButton>
                      </ListItem>
                    ))}
                  </List>
                </CardContent>
              </Card>
            </Grid>
          )}
          {files.length > 0 && (
            <Grid item xs={12} md={directories.length > 0 ? 6 : 12}>
              <Card sx={{ height: '100%' }}>
                <CardContent>
                  <Typography variant="subtitle2" color="text.secondary" gutterBottom>
                    Files
                  </Typography>
                  <List dense>
                    {files.map((name) => (
                      <ListItem key={name} disablePadding>
                        <ListItemButton onClick={() => handleFileClick(name)}>
                          <InsertDriveFileIcon sx={{ mr: 1, color: 'action.active', fontSize: 20 }} />
                          <Typography variant="body2" noWrap sx={{ flex: 1 }}>
                            {name}
                          </Typography>
                        </ListItemButton>
                      </ListItem>
                    ))}
                  </List>
                </CardContent>
              </Card>
            </Grid>
          )}
        </Grid>
      )}
    </Box>
  )
}
