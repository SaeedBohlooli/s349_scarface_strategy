export interface OHLCData {
  date: string;
  open: number;
  close: number;
  high: number;
  low: number;
  volume: number;
}

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
}

export interface MappedLevelsResponse {
  [symbol: string]: SymbolLevels;
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
  };
}

export interface FileListResponse {
  files: string[];
  symbols: string[];
  timeframes: string[];
}
