"# S349 Scarface Strategy API

A TypeScript Node.js API for reading and formatting financial data from CSV files in the portfolios directory.

## Features

- 📊 Read OHLC (Open, High, Low, Close) data from CSV files
- 🎨 Parse drawing objects data
- 📋 List available symbols and timeframes
- 🔍 Filter data by date range
- 📄 Paginated data retrieval
- 📈 Basic statistics calculation
- 🌐 RESTful API endpoints

## Installation

```bash
npm install
```

## Development

```bash
# Build TypeScript
npm run build

# Run in development mode
npm run dev

# Run production build
npm start

# Watch mode (auto-rebuild)
npm run watch
```

## API Endpoints

### Base URL
`http://localhost:3000`

### Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| GET | `/api/v1/files` | List available files, symbols, and timeframes |
| GET | `/api/v1/data/:symbol/:timeframe` | Get OHLC data for a symbol |
| POST | `/api/v1/data/multiple` | Get data for multiple symbols |
| GET | `/api/v1/drawing-objects` | Get drawing objects data |
| GET | `/api/v1/stats/:symbol/:timeframe` | Get basic statistics |

### Query Parameters

#### `/api/v1/data/:symbol/:timeframe`
- `page` - Page number for pagination
- `limit` - Number of records per page
- `startDate` - Filter by start date (YYYY-MM-DD format)
- `endDate` - Filter by end date (YYYY-MM-DD format)

### Examples

```bash
# Get available files
curl http://localhost:3000/api/v1/files

# Get AAPL 1min data
curl http://localhost:3000/api/v1/data/AAPL/1min

# Get paginated data (page 1, 100 records)
curl "http://localhost:3000/api/v1/data/AAPL/1min?page=1&limit=100"

# Get data by date range
curl "http://localhost:3000/api/v1/data/AAPL/1min?startDate=2025-09-22&endDate=2025-09-23"

# Get multiple symbols data
curl -X POST http://localhost:3000/api/v1/data/multiple \
  -H "Content-Type: application/json" \
  -d '{"symbols": ["AAPL", "TSLA", "QQQ"], "timeframe": "1min"}'

# Get statistics
curl http://localhost:3000/api/v1/stats/AAPL/1min

# Get drawing objects
curl http://localhost:3000/api/v1/drawing-objects
```

## Data Format

### OHLC Data Response
```json
{
  "success": true,
  "data": {
    "symbol": "AAPL",
    "timeframe": "1min",
    "data": [
      {
        "date": "2025-09-22 04:00:00-04:00",
        "open": 246.13,
        "close": 245.35,
        "high": 246.82,
        "low": 245.3,
        "volume": 8388.0
      }
    ],
    "metadata": {
      "totalRecords": 7681,
      "startDate": "2025-09-22 04:00:00-04:00",
      "endDate": "2025-09-30 19:59:00-04:00",
      "lastUpdated": "2025-10-01T12:00:00.000Z"
    }
  }
}
```

### File List Response
```json
{
  "success": true,
  "data": {
    "files": ["AAPL-1min.csv", "QQQ-1min.csv", "TSLA-1min.csv"],
    "symbols": ["AAPL", "QQQ", "TSLA"],
    "timeframes": ["1day", "1min"]
  }
}
```

## Project Structure

```
src/
├── index.ts              # Main server file
├── types/
│   └── index.ts          # TypeScript type definitions
├── services/
│   └── DataFormatter.ts  # Core data formatting logic
├── routes/
│   └── data.ts          # API route handlers
└── examples/
    └── testFormatter.ts  # Usage examples and tests
```

## Configuration

The API reads data from the portfolios directory structure:
```
portfolios/
└── charts/
    └── p250/
        ├── AAPL-1min.csv
        ├── QQQ-1min.csv
        ├── TSLA-1min.csv
        └── 10-drawing_objects_df.csv
```

## Testing

Run the test formatter:
```bash
npm run dev src/examples/testFormatter.ts
```" 
