import { IconButton, Tooltip } from '@mui/material'
import LightModeIcon from '@mui/icons-material/LightMode'
import DarkModeIcon from '@mui/icons-material/DarkMode'

interface ThemeToggleProps {
  mode: 'light' | 'dark'
  onToggle: () => void
}

export default function ThemeToggle({ mode, onToggle }: ThemeToggleProps) {
  return (
    <Tooltip title={`Switch to ${mode === 'light' ? 'dark' : 'light'} mode`}>
      <IconButton color="inherit" onClick={onToggle} aria-label="toggle theme">
        {mode === 'light' ? <DarkModeIcon /> : <LightModeIcon />}
      </IconButton>
    </Tooltip>
  )
}

