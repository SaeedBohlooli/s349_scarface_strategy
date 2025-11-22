import { Alert, AlertTitle, Button, Box } from '@mui/material'
import type { ApiError } from '../types/api'

interface ApiErrorAlertProps {
  error: ApiError | null
  onRetry?: () => void
  title?: string
}

export default function ApiErrorAlert({ error, onRetry, title }: ApiErrorAlertProps) {
  if (!error) return null

  return (
    <Alert severity="error" sx={{ mb: 2 }}>
      {title && <AlertTitle>{title}</AlertTitle>}
      {error.error}
      {error.message && (
        <Box component="div" sx={{ mt: 1, fontSize: '0.875rem' }}>
          {error.message}
        </Box>
      )}
      {onRetry && (
        <Box sx={{ mt: 2 }}>
          <Button variant="outlined" color="inherit" onClick={onRetry} size="small">
            Retry
          </Button>
        </Box>
      )}
    </Alert>
  )
}

