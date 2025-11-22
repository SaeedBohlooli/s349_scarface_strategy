# Scarface Strategy Dashboard

A comprehensive dashboard system for monitoring and analyzing trading portfolios, with a Flask API backend and React frontend.

## Project Structure

```
s349_scarface_strategy/
├── api/                    # Flask API backend
│   ├── api.py             # Main API application
│   ├── config.yaml        # API configuration
│   └── README.md          # API documentation
├── apps/
│   └── ui-dashboard/      # React frontend
│       ├── src/           # Source code
│       ├── package.json   # Dependencies
│       └── README.md      # UI documentation
└── portfolios/            # Data folder (portfolio files)
```

## Quick Start

### Prerequisites

- **Python 3.8+** (for API)
- **Node.js 18+** (for UI Dashboard)
- **npm** or **yarn**

### 1. Setup API Backend

```bash
# Navigate to API directory
cd api

# Create virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r ../requirements.txt

# Configure API (edit config.yaml if needed)
# Default port: 5000
# Default data folder: ../../portfolios

# Run API
python api.py
```

The API will be available at `http://127.0.0.1:5000`

### 2. Setup UI Dashboard

```bash
# Navigate to UI dashboard directory
cd apps/ui-dashboard

# Install dependencies
npm install

# Start development server
npm run dev
```

The UI will be available at `http://localhost:5173`

### 3. Access the Dashboard

1. Open your browser to `http://localhost:5173`
2. Select a portfolio from the dropdown
3. Browse directories and files
4. View logs using the "View Logs" option

## Features

### API Backend

- RESTful API with Flask
- File system access to portfolio data
- CSV to JSON conversion
- Log file pagination and search
- Comprehensive caching system
- CORS enabled for frontend integration

### UI Dashboard

- Modern React interface with Material-UI
- Light/Dark theme support
- Portfolio and directory navigation
- Data table with sorting, filtering, and search
- JSON viewer for complex data structures
- PatternFly log viewer for large log files
- Responsive design

## API Endpoints

- `GET /api/v1/health` - Health check
- `GET /api/v1/portfolios` - List all portfolios
- `GET /api/v1/directories` - List all directories
- `GET /api/v1/files/<directory>/<portfolio_id>` - List files in directory
- `GET /api/v1/files/<directory>/<portfolio_id>/<file>` - Get file content
- `GET /api/v1/logs/directories/<portfolio_id>` - List log directories
- `GET /api/v1/logs/files/<portfolio_id>/<log_directory>` - List log files
- `GET /api/v1/logs/content/<portfolio_id>/<log_directory>/<file>` - Get log content (with pagination)

## Configuration

### API Configuration (`api/config.yaml`)

```yaml
app:
  port: 5000 # API server port
  api_version: v1 # API version
data_folder: ../../portfolios # Path to portfolio data
cache_timer: 10 # Cache TTL in seconds
```

### UI Configuration

The UI connects to the API at `http://127.0.0.1:5000` by default. To change this, set the environment variable:

```bash
export VITE_API_BASE_URL=http://your-api-url:5000
```

Or create a `.env` file in `apps/ui-dashboard/`:

```
VITE_API_BASE_URL=http://127.0.0.1:5000
```

## Development

### Running Both Services

**Terminal 1 - API:**

```bash
cd api
python api.py
```

**Terminal 2 - UI:**

```bash
cd apps/ui-dashboard
npm run dev
```

### Building for Production

**API:**

- No build step required, just run `python api.py`

**UI:**

```bash
cd apps/ui-dashboard
npm run build
npm run preview  # Preview production build
```

## Caching

The API implements a comprehensive caching system:

- **Directory listings**: Cached with TTL (default: 10 seconds)
- **File content**: Cached based on file modification time
- **Log files**: Cached for efficient pagination
- **Automatic invalidation**: Cache invalidates when files change
- **Memory management**: LRU eviction when cache exceeds 200 entries

## Troubleshooting

### API Issues

- **Port already in use**: Change port in `api/config.yaml`
- **File not found**: Check `data_folder` path in `api/config.yaml`
- **CORS errors**: Ensure `flask-cors` is installed

### UI Issues

- **API connection failed**: Check API is running and `VITE_API_BASE_URL` is correct
- **Build errors**: Run `npm install` to ensure all dependencies are installed

## Additional Resources

- [API Documentation](api/README.md) - Detailed API setup and usage
- [UI Dashboard Documentation](apps/ui-dashboard/README.md) - UI development guide

## Volume Ratio Calculation

```python
df['volume_sma10'] = df['volume'].rolling(window=10).mean()
df['VR'] = df['volume'] / df['volume_sma10']
cap = df['VR'].quantile(0.95)  # 95th percentile
df['VR'] = df['VR'].clip(upper=cap)
df['VR_sma10'] = df['VR'].rolling(window=10).mean()
```

## RS Relative Calculation

```python
merged['stock_pct'] = merged['close_stock'] / stock_open - 1
merged['qqq_pct'] = merged['close_qqq'] / qqq_open - 1
merged['qqq_930'] = qqq_open
merged['stock_930'] = stock_open

# Relative performance
merged['rs_rel'] = np.where(
    merged['qqq_pct'].abs() > 0.0005,
    merged['stock_pct'] / merged['qqq_pct'],
    np.nan
).clip(-10, 10)
```

## RS Delta Calculation

```python
merged['rs_delta'] = merged['stock_pct'] - merged['qqq_pct']
```
