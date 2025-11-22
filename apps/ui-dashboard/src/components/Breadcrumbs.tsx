import { Breadcrumbs as MuiBreadcrumbs, Link, Typography, Box } from '@mui/material'
import HomeIcon from '@mui/icons-material/Home'

interface BreadcrumbItem {
  label: string
  onClick?: () => void
}

interface BreadcrumbsProps {
  items: BreadcrumbItem[]
  onHomeClick?: () => void
}

export default function Breadcrumbs({ items, onHomeClick }: BreadcrumbsProps) {
  return (
    <Box sx={{ mb: 2 }}>
      <MuiBreadcrumbs aria-label="breadcrumb" separator="›">
        <Link
          component="button"
          variant="body1"
          onClick={onHomeClick}
          sx={{
            display: 'flex',
            alignItems: 'center',
            textDecoration: 'none',
            cursor: 'pointer',
            '&:hover': {
              textDecoration: 'underline',
            },
          }}
        >
          <HomeIcon sx={{ mr: 0.5, fontSize: 20 }} />
          Home
        </Link>
        {items.slice(0, -1).map((item, index) => (
          <Link
            key={index}
            component="button"
            variant="body1"
            onClick={item.onClick}
            sx={{
              textDecoration: 'none',
              cursor: 'pointer',
              '&:hover': {
                textDecoration: 'underline',
              },
            }}
          >
            {item.label}
          </Link>
        ))}
        {items.length > 0 && (
          <Typography color="text.primary" variant="body1">
            {items[items.length - 1].label}
          </Typography>
        )}
      </MuiBreadcrumbs>
    </Box>
  )
}
