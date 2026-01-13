# Scarface Strategy API

Flask REST API for serving portfolio data, files, and logs to the UI dashboard.

## Features

- RESTful API endpoints for portfolio data access
- CSV to JSON conversion
- Log file pagination and search
- Comprehensive caching system with automatic invalidation
- CORS enabled for frontend integration
- File modification time-based cache invalidation

## Prerequisites

- Python 3.8 or higher
- pip (Python package manager)

## Installation

1. **Create a virtual environment** (recommended):

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. **Install dependencies**:

```bash
pip install -r ../requirements.txt
```

Or install Flask and dependencies directly:

```bash
pip install flask flask-cors pyyaml
```

## Configuration

Edit `config.yaml` to configure the API:

```yaml
app:
  port: 5000 # API server port
  api_version: v1 # API version prefix
data_folder: ../../portfolios # Path to portfolio data folder
cache_timer: 10 # Cache TTL in seconds for directory listings
```

### Configuration Options

- **port**: The port number the API will run on (default: 5000)
- **api_version**: API version used in URL paths (default: v1)
- **data_folder**: Relative path to the portfolios data folder
- **cache_timer**: Time-to-live for directory listing cache in seconds

## Running the API

### Development Mode

```bash
python api.py
```

The API will start on `http://127.0.0.1:5000` (or the port specified in config.yaml)

### Production Mode

For production, use a WSGI server like Gunicorn:

```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 api:app
```

## API Endpoints

### Health Check

```
GET /api/v1/health
```

Returns API health status.

**Response:**

```json
{
  "status": "ok"
}
```

### Portfolios

```
GET /api/v1/portfolios
```

Returns list of all portfolios.

**Response:**

```json
{
  "path": "/absolute/path/to/results",
  "portfolios": ["p250", "p700", ...]
}
```

### Directories

```
GET /api/v1/directories
```

Returns list of all directories under the portfolios folder.

**Response:**

```json
{
  "path": "/absolute/path/to/portfolios",
  "directories": ["directory1", "directory2", ...]
}
```

### Files

```
GET /api/v1/files/<directory>/<portfolio_id>
```

Returns list of files in a specific directory and portfolio.

**Response:**

```json
{
  "path": "/absolute/path/to/directory/portfolio",
  "files": ["file1.csv", "file2.json", ...]
}
```

### File Content

```
GET /api/v1/files/<directory>/<portfolio_id>/<file>
```

Returns file content as JSON.

- **CSV files**: Converted to JSON format
- **JSON files**: Parsed and returned
- **Other files**: Returned as raw content

**Response (CSV/JSON):**

```json
{
  "data": [...],
  "count": 100
}
```

**Response (Raw):**

```json
{
  "content": "file content as string"
}
```

### Log Directories

```
GET /api/v1/logs/directories/<portfolio_id>
```

Returns list of log directories for a portfolio.

**Response:**

```json
{
  "path": "/absolute/path/to/logs/portfolio",
  "directories": ["log_dir1", "log_dir2", ...]
}
```

### Log Files

```
GET /api/v1/logs/files/<portfolio_id>/<log_directory>
```

Returns list of log files in a specific log directory.

**Response:**

```json
{
  "path": "/absolute/path/to/logs/portfolio/directory",
  "files": ["log1.log", "log2.txt", ...]
}
```

### Log Content

```
GET /api/v1/logs/content/<portfolio_id>/<log_directory>/<file>?page=1&per_page=1000&search=query
```

Returns paginated log file content.

**Query Parameters:**

- `page`: Page number (default: 1)
- `per_page`: Lines per page (default: 1000, max: 10000)
- `search`: Optional search query to filter lines

**Response:**

```json
{
  "type": "log",
  "lines": [
    {"lineNumber": 1, "content": "log line 1"},
    {"lineNumber": 2, "content": "log line 2"},
    ...
  ],
  "totalLines": 5000,
  "originalTotalLines": 5000,
  "page": 1,
  "perPage": 1000,
  "totalPages": 5,
  "hasSearch": false
}
```

## Caching System

The API implements intelligent caching:

### Directory Listings

- **Cache Type**: TTL-based (default: 10 seconds)
- **Invalidation**: Directory modification time check
- **Storage**: In-memory cache

### File Content

- **Cache Type**: Modification time + file size based
- **Invalidation**: Automatic when file changes
- **Storage**: In-memory cache with LRU eviction

### Log Files

- **Cache Type**: Modification time + file size based
- **Invalidation**: Automatic when file changes
- **Storage**: In-memory cache
- **Benefit**: Avoids re-reading entire file on pagination

### Cache Management

- **Max Cache Size**: 200 entries
- **Eviction Policy**: LRU (Least Recently Used)
- **Memory Efficient**: Designed for files up to 5MB

## Error Handling

The API returns appropriate HTTP status codes:

- **200**: Success
- **400**: Bad Request (invalid parameters)
- **403**: Forbidden (permission denied)
- **404**: Not Found (file/directory doesn't exist)
- **500**: Internal Server Error

Error responses include a descriptive message:

```json
{
  "error": "File not found: /path/to/file"
}
```

## Development

### Running in Debug Mode

The API runs in debug mode by default when executed directly:

```bash
python api.py
```

This enables:

- Auto-reload on code changes
- Detailed error messages
- Debug logging

### Testing Endpoints

Use `curl` or any HTTP client:

```bash
# Health check
curl http://127.0.0.1:5000/api/v1/health

# Get portfolios
curl http://127.0.0.1:5000/api/v1/portfolios

# Get file content
curl http://127.0.0.1:5000/api/v1/files/directory/p107/file.csv
```

## Troubleshooting

### Port Already in Use

Change the port in `config.yaml`:

```yaml
app:
  port: 5001 # Use a different port
```

### File Not Found Errors

1. Check `data_folder` path in `config.yaml`
2. Ensure the path is relative to `api.py` location
3. Verify the portfolios folder exists

### CORS Issues

Ensure `flask-cors` is installed:

```bash
pip install flask-cors
```

CORS is enabled for all `/api/*` routes by default.

### Cache Issues

To clear cache, restart the API server. The cache is in-memory and doesn't persist between restarts.

## Performance Considerations

- **File Size**: Optimized for files up to 5MB
- **Caching**: Reduces I/O operations significantly
- **Pagination**: Log files are paginated to avoid loading entire files
- **Memory**: LRU eviction prevents memory bloat

## Security Notes

- The API serves files from the configured `data_folder` only
- No authentication is implemented (add if needed for production)
- CORS is enabled for all origins (restrict in production)
- File paths are validated to prevent directory traversal
