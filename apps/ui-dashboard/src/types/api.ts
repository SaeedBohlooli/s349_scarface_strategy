/**
 * TypeScript interfaces for API responses
 */

export interface PortfolioResponse {
  path: string;
  portfolios: string[];
}

export interface DirectoryResponse {
  path: string;
  directories: string[];
}

export interface FilesResponse {
  path: string;
  files: string[];
}

export interface FileContentResponse {
  data: unknown; // Can be array, object, or any JSON structure
  count: number;
}

export interface ApiError {
  error: string;
  message?: string;
}

export interface LogDirectoriesResponse {
  path: string;
  directories: string[];
}

export interface LogFilesResponse {
  path: string;
  files: string[];
}

export interface LogLine {
  lineNumber: number;
  content: string;
}

export interface LogContentResponse {
  type: "log";
  lines: LogLine[];
  totalLines: number;
  originalTotalLines: number;
  page: number;
  perPage: number;
  totalPages: number;
  hasSearch: boolean;
  searchQuery?: string;
}
