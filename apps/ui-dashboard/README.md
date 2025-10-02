# # S349 Scarface Strategy - UI Dashboard

A React TypeScript dashboard for visualizing financial data from the S349 Scarface Strategy API.

## Features

- 📊 Real-time OHLC data visualization
- 🎯 Support/Resistance levels display
- 📈 Portfolio statistics and analytics
- 🔄 Real-time data updates
- 📱 Responsive design
- 🎨 Modern UI with Material-UI components

## Prerequisites

Make sure the API server is running:

```bash
cd ../api
npm run dev
```

The API should be available at `http://localhost:3000`

## Installation

```bash
npm install
```

## Development

```bash
# Start development server
npm run dev

# Build for production
npm run build

# Preview production build
npm run preview
```

## Available Scripts

- `npm run dev` - Start development server on port 5173
- `npm run build` - Build for production
- `npm run preview` - Preview production build
- `npm run lint` - Run ESLint

## Project Structure

```
src/
├── components/
│   └── ApiDemo.tsx          # Main demo component
├── hooks/
│   └── useApi.ts           # Custom React hooks for API calls
├── services/
│   └── ApiService.ts       # API service layer
├── types/
│   └── api.ts             # TypeScript type definitions
├── App.tsx                # Main App component
└── main.tsx              # Entry point
```

## API Integration

The dashboard connects to the Node.js API through:

1. **Proxy Configuration** (vite.config.ts) - Routes `/api/*` to `http://localhost:3000`
2. **API Service** (ApiService.ts) - Centralized API calls with axios
3. **React Hooks** (useApi.ts) - Custom hooks for data fetching with loading/error states

## Available API Endpoints

The dashboard consumes these API endpoints:

| Endpoint                           | Description                     |
| ---------------------------------- | ------------------------------- |
| `/api/v1/files`                    | Get available files and symbols |
| `/api/v1/data/:symbol/:timeframe`  | Get OHLC data                   |
| `/api/v1/levels`                   | Get support/resistance levels   |
| `/api/v1/stats/:symbol/:timeframe` | Get statistics                  |

## Features Showcase

### 📁 File Management

- Lists available symbols (AAPL, QQQ, TSLA)
- Shows available timeframes (1min, 1day)
- File count and metadata

### 📈 OHLC Data Display

- Interactive symbol and timeframe selection
- Configurable data limits
- Tabular data display with latest prices
- Date range information

### 📊 Statistics Dashboard

- Price statistics (min, max, average, latest)
- Volume analytics
- Real-time calculations

### 🎯 Levels Visualization

- Support and resistance levels
- Previous Day High/Low (PDH/PDL)
- 5-minute high/low levels
- Color-coded level indicators

### 📋 Portfolio Overview

- Multi-symbol dashboard
- Cross-symbol statistics
- Portfolio-wide analytics

## Development Notes

### Proxy Setup

The Vite proxy configuration automatically forwards API requests:

```typescript
server: {
  proxy: {
    '/api': {
      target: 'http://localhost:3000',
      changeOrigin: true,
    },
  },
}
```

### Type Safety

Full TypeScript integration with:

- API response types
- OHLC data structures
- Drawing objects and levels
- Error handling types

### Error Handling

Comprehensive error handling with:

- Loading states
- Error messages
- Retry mechanisms
- Graceful degradation

## Environment Variables

Create a `.env` file with:

```
VITE_API_BASE_URL=http://localhost:3000
```

## Browser Support

- Chrome (latest)
- Firefox (latest)
- Safari (latest)
- Edge (latest)

## Next Steps

- Add charting with Recharts
- Implement real-time WebSocket updates
- Add data export functionality
- Create custom dashboard layouts
- Add user authentication

This template provides a minimal setup to get React working in Vite with HMR and some ESLint rules.

Currently, two official plugins are available:

- [@vitejs/plugin-react](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react) uses [Babel](https://babeljs.io/) for Fast Refresh
- [@vitejs/plugin-react-swc](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react-swc) uses [SWC](https://swc.rs/) for Fast Refresh

## React Compiler

The React Compiler is not enabled on this template because of its impact on dev & build performances. To add it, see [this documentation](https://react.dev/learn/react-compiler/installation).

## Expanding the ESLint configuration

If you are developing a production application, we recommend updating the configuration to enable type-aware lint rules:

```js
export default defineConfig([
  globalIgnores(["dist"]),
  {
    files: ["**/*.{ts,tsx}"],
    extends: [
      // Other configs...

      // Remove tseslint.configs.recommended and replace with this
      tseslint.configs.recommendedTypeChecked,
      // Alternatively, use this for stricter rules
      tseslint.configs.strictTypeChecked,
      // Optionally, add this for stylistic rules
      tseslint.configs.stylisticTypeChecked,

      // Other configs...
    ],
    languageOptions: {
      parserOptions: {
        project: ["./tsconfig.node.json", "./tsconfig.app.json"],
        tsconfigRootDir: import.meta.dirname,
      },
      // other options...
    },
  },
]);
```

You can also install [eslint-plugin-react-x](https://github.com/Rel1cx/eslint-react/tree/main/packages/plugins/eslint-plugin-react-x) and [eslint-plugin-react-dom](https://github.com/Rel1cx/eslint-react/tree/main/packages/plugins/eslint-plugin-react-dom) for React-specific lint rules:

```js
// eslint.config.js
import reactX from "eslint-plugin-react-x";
import reactDom from "eslint-plugin-react-dom";

export default defineConfig([
  globalIgnores(["dist"]),
  {
    files: ["**/*.{ts,tsx}"],
    extends: [
      // Other configs...
      // Enable lint rules for React
      reactX.configs["recommended-typescript"],
      // Enable lint rules for React DOM
      reactDom.configs.recommended,
    ],
    languageOptions: {
      parserOptions: {
        project: ["./tsconfig.node.json", "./tsconfig.app.json"],
        tsconfigRootDir: import.meta.dirname,
      },
      // other options...
    },
  },
]);
```
