import { useState, useEffect } from 'react'
import {
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Box,
  IconButton,
  Tooltip,
} from '@mui/material'
import RefreshIcon from '@mui/icons-material/Refresh'
import { getPortfolios } from '../services/api'
import type { ApiError } from '../types/api'
import LoadingSpinner from './LoadingSpinner'
import ApiErrorAlert from './ApiErrorAlert'

interface PortfolioSelectorProps {
  onPortfolioChange: (portfolioId: string) => void
  selectedPortfolio?: string
}

export default function PortfolioSelector({
  onPortfolioChange,
  selectedPortfolio,
}: PortfolioSelectorProps) {
  const [portfolios, setPortfolios] = useState<string[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<ApiError | null>(null)

  useEffect(() => {
    loadPortfolios()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])
  
  // Update selectedPortfolio when prop changes (from URL)
  useEffect(() => {
    // This effect ensures the selector reflects the URL state
  }, [selectedPortfolio])

  const loadPortfolios = async () => {
    try {
      setLoading(true)
      setError(null)
      const response = await getPortfolios()
      setPortfolios(response.portfolios)
      
      // Auto-select if only one portfolio AND no portfolio is already selected from URL
      // Only auto-select if we're on the home page (no portfolio in URL)
      if (response.portfolios.length === 1 && !selectedPortfolio) {
        const currentPath = window.location.pathname
        // Only auto-navigate if we're on root or empty path (not calculator or other routes)
        if (
          (currentPath === '/' || currentPath === '') &&
          !currentPath.includes('/portfolio/') &&
          !currentPath.includes('/calculator')
        ) {
          onPortfolioChange(response.portfolios[0])
        }
      }
    } catch (err) {
      setError(err as ApiError)
    } finally {
      setLoading(false)
    }
  }

  const handleChange = (event: { target: { value: string } }) => {
    onPortfolioChange(event.target.value)
  }

  if (loading) {
    return <LoadingSpinner message="Loading portfolios..." />
  }

  if (error) {
    return <ApiErrorAlert error={error} onRetry={loadPortfolios} title="Failed to load portfolios" />
  }

  return (
    <Box sx={{ mb: 3, display: 'flex', gap: 2, alignItems: 'center' }}>
      <FormControl fullWidth>
        <InputLabel id="portfolio-select-label">Select Portfolio</InputLabel>
        <Select
          labelId="portfolio-select-label"
          id="portfolio-select"
          value={selectedPortfolio || ''}
          label="Select Portfolio"
          onChange={handleChange}
        >
          {portfolios.map((portfolio) => (
            <MenuItem key={portfolio} value={portfolio}>
              {portfolio}
            </MenuItem>
          ))}
        </Select>
      </FormControl>
      <Tooltip title="Refresh portfolios">
        <IconButton
          size="small"
          onClick={loadPortfolios}
          disabled={loading}
        >
          <RefreshIcon />
        </IconButton>
      </Tooltip>
    </Box>
  )
}

