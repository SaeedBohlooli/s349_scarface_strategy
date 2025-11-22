# Scarface Strategy UI Dashboard

A modern React dashboard built with TypeScript, Vite, and Material-UI for monitoring and analyzing trading portfolios.

## Features

- ⚡️ Fast development with Vite
- 🎨 Material-UI components for a beautiful, modern interface
- 🌓 Light/Dark theme support
- 📱 Responsive design
- 🔍 Advanced search functionality
- 📊 Data table with sorting, filtering, and column management
- 📄 JSON viewer for complex data structures
- 📋 PatternFly log viewer for large log files
- 🧭 Breadcrumb navigation
- 📁 Portfolio and directory browsing
- 🔄 Real-time data fetching from API

## Tech Stack

- **React 19** - UI library
- **TypeScript** - Type safety
- **Vite** - Build tool and dev server
- **Material-UI (MUI) v7** - Component library
- **MUI X DataGrid** - Advanced data table
- **PatternFly Log Viewer** - Professional log viewing
- **Axios** - HTTP client
- **Emotion** - CSS-in-JS styling

## Prerequisites

- **Node.js** 18 or higher
- **npm** or **yarn**
- **Running API backend** (see [API README](../../api/README.md))

## Installation

1. **Navigate to the UI dashboard directory**:

```bash
cd apps/ui-dashboard
```

2. **Install dependencies**:

```bash
npm install
```

## Configuration

### API Base URL

The UI connects to the API backend. Configure the API URL:

**Option 1: Environment Variable**

Create a `.env` file in `apps/ui-dashboard/`:

```env
VITE_API_BASE_URL=http://127.0.0.1:5000
```

**Option 2: Default**

If not set, defaults to `http://127.0.0.1:5000`

## Running the Application

### Development Mode

Start the development server:

```bash
npm run dev
```

The app will be available at `http://localhost:5173`

**Note**: Make sure the API backend is running on `http://127.0.0.1:5000` (or your configured URL).

### Production Build

Build for production:

```bash
npm run build
```

The production build will be in the `dist/` directory.

### Preview Production Build

Preview the production build locally:

```bash
npm run preview
```

## Usage

### 1. Portfolio Selection

- Select a portfolio from the dropdown
- The dashboard will load available directories

### 2. Browse Directories

- View directories in a 3-column layout
- Click on files to view their content
- Empty directories appear at the end

### 3. View File Content

- **CSV/JSON files**: Displayed in an interactive data table
- **Complex JSON**: Displayed in a JSON viewer with expand/collapse
- **Search**: Use the search bar to filter data

### 4. View Logs

- Click "View Logs" button after selecting a portfolio
- Select log directory and file from dropdowns
- Use pagination to navigate through large log files
- Search across all log lines (server-side search)

## Project Structure

```
ui-dashboard/
├── src/
│   ├── components/          # React components
│   │   ├── DataTable.tsx    # Data table with search
│   │   ├── JsonViewer.tsx   # JSON tree viewer
│   │   ├── LogViewer.tsx    # PatternFly log viewer
│   │   ├── LogsView.tsx     # Log viewer page
│   │   ├── FileContentView.tsx
│   │   ├── DirectoriesView.tsx
│   │   ├── PortfolioSelector.tsx
│   │   ├── Breadcrumbs.tsx
│   │   ├── ThemeToggle.tsx
│   │   ├── LoadingSpinner.tsx
│   │   ├── ApiErrorAlert.tsx
│   │   └── ErrorBoundary.tsx
│   ├── services/
│   │   └── api.ts           # API service layer
│   ├── types/
│   │   └── api.ts           # TypeScript interfaces
│   ├── utils/
│   │   ├── stringUtils.ts   # String transformation utilities
│   │   └── dataUtils.ts     # Data validation utilities
│   ├── config/
│   │   └── appConfig.ts     # App configuration
│   ├── App.tsx              # Main app component
│   ├── main.tsx             # Entry point
│   └── theme.ts             # Material-UI theme
├── public/                  # Static assets
└── package.json             # Dependencies and scripts
```

## Available Scripts

- `npm run dev` - Start development server
- `npm run build` - Build for production
- `npm run preview` - Preview production build
- `npm run lint` - Run ESLint

## Features in Detail

### Data Table

- **Sorting**: Click column headers to sort
- **Filtering**: Use the search bar to filter across all columns
- **Column Resizing**: Drag column borders to resize
- **Column Visibility**: Toggle columns on/off
- **Pagination**: Navigate through large datasets
- **Camel Case Headers**: Snake_case keys automatically converted to camelCase

### JSON Viewer

- **Tree Structure**: Expandable/collapsible nodes
- **Search**: Highlight matching text
- **Color Coding**: Different colors for objects, arrays, strings, numbers
- **Auto-expand**: First 2 levels expanded by default

### Log Viewer

- **PatternFly Integration**: Professional log viewing component
- **Pagination**: Navigate through large log files (1000 lines per page)
- **Server-side Search**: Search across entire log file
- **Line Numbers**: Each line shows its number
- **Compact UI**: Developer-friendly interface

### Theme Support

- **Light Mode**: Clean, bright interface
- **Dark Mode**: Easy on the eyes
- **Toggle**: Switch between themes using the toggle in the app bar

## API Integration

The UI communicates with the Flask API backend. See [API README](../../api/README.md) for API documentation.

### API Endpoints Used

- `GET /api/v1/portfolios` - Get portfolio list
- `GET /api/v1/directories` - Get directory list
- `GET /api/v1/files/<directory>/<portfolio_id>` - Get file list
- `GET /api/v1/files/<directory>/<portfolio_id>/<file>` - Get file content
- `GET /api/v1/logs/directories/<portfolio_id>` - Get log directories
- `GET /api/v1/logs/files/<portfolio_id>/<log_directory>` - Get log files
- `GET /api/v1/logs/content/<portfolio_id>/<log_directory>/<file>` - Get log content

## Configuration

### Ignored Directories

Edit `src/config/appConfig.ts` to ignore specific directories:

```typescript
export const IGNORED_DIRECTORIES = [
  'backtest-charts',
  'backtest-charts-mechanics',
  'blocked-trades',
  'charts-backtest',
  'detailed-logs',
  'ohlc',
  'logs',
  'passed-trades',
]
```

## Troubleshooting

### API Connection Failed

1. Ensure the API backend is running
2. Check `VITE_API_BASE_URL` in `.env` file
3. Verify CORS is enabled on the API

### Build Errors

1. Clear node_modules and reinstall:
   ```bash
   rm -rf node_modules package-lock.json
   npm install
   ```

2. Check Node.js version (requires 18+):
   ```bash
   node --version
   ```

### PatternFly Log Viewer Not Loading

1. Ensure PatternFly packages are installed:
   ```bash
   npm install @patternfly/react-log-viewer @patternfly/react-core @patternfly/react-styles
   ```

2. Check browser console for errors

## Development Tips

### Hot Module Replacement

Vite provides instant HMR. Changes to components will update immediately without full page reload.

### TypeScript

The project uses strict TypeScript. Check types with:

```bash
npm run build  # TypeScript compilation is part of build
```

### Component Structure

- **Container Components**: `App.tsx`, `LogsView.tsx`, `DirectoriesView.tsx`
- **Presentational Components**: `DataTable.tsx`, `JsonViewer.tsx`, `LogViewer.tsx`
- **Utility Components**: `LoadingSpinner.tsx`, `ApiErrorAlert.tsx`, `ErrorBoundary.tsx`

## Production Deployment

1. **Build the application**:

```bash
npm run build
```

2. **Serve the `dist/` directory** using a web server:

```bash
# Using Python
cd dist
python -m http.server 8000

# Using Node.js serve
npx serve dist

# Using nginx (configure nginx.conf)
```

3. **Configure API URL** for production in `.env.production`:

```env
VITE_API_BASE_URL=https://your-api-domain.com
```

## Browser Support

- Chrome (latest)
- Firefox (latest)
- Safari (latest)
- Edge (latest)

## License

Part of the Scarface Strategy project.
