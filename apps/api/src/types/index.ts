export interface OHLCData {
  date: string;
  open: number;
  close: number;
  high: number;
  low: number;
  volume: number;
}

export interface DrawingObject {
  [key: string]: any;
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
