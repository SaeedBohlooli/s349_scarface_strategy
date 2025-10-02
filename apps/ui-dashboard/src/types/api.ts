// API Response Types
export interface ApiResponse<T> {
  success: boolean;
  data: T;
  error?: string;
}

// OHLC Data Types
export interface OHLCData {
  date: string;
  open: number;
  close: number;
  high: number;
  low: number;
  volume: number;
}

export interface DataResponse {
  symbol: string;
  timeframe: string;
  data: OHLCData[];
  metadata: {
    totalRecords: number;
    startDate: string;
    endDate: string;
    lastUpdated: string;
    page?: number;
    limit?: number;
    totalPages?: number;
    dateRange?: {
      startDate: string;
      endDate: string;
    };
  };
}

// Drawing Objects Types
export interface DrawingObject {
  symbol: string;
  time_frame: string;
  object: string;
  color: string;
  date_1: string;
  price_1: string;
  date_2: string;
  price_2: string;
  memo: string;
  unique_id: string;
}

// Levels Types
export interface LevelData {
  symbol: string;
  time_frame: string;
  object: string;
  color: string;
  date_1: string;
  price_1: string;
  date_2: string;
  price_2: string;
  memo: string;
}

export interface SymbolLevels {
  PDH?: LevelData;
  PDL?: LevelData;
  LDH?: LevelData;
  "5MH"?: LevelData;
  "5ML"?: LevelData;
  PML?: LevelData;
  PMH?: LevelData;
}

export interface MappedLevelsResponse {
  [symbol: string]: SymbolLevels;
}

// File List Types
export interface FileListResponse {
  files: string[];
  symbols: string[];
  timeframes: string[];
}

// Statistics Types
export interface StatsResponse {
  symbol: string;
  timeframe: string;
  totalRecords: number;
  priceStats: {
    min: number;
    max: number;
    average: number;
    latest: number;
  };
  volumeStats: {
    min: number;
    max: number;
    average: number;
    total: number;
  };
  dateRange: {
    start: string;
    end: string;
  };
}

// Request Types
export interface MultipleSymbolsRequest {
  symbols: string[];
  timeframe: string;
}

export interface DataQueryParams {
  page?: number;
  limit?: number;
  startDate?: string;
  endDate?: string;
}
