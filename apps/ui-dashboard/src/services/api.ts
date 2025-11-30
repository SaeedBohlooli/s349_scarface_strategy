import axios, { AxiosError } from 'axios'
import type {
  PortfolioResponse,
  DirectoryResponse,
  FilesResponse,
  FileContentResponse,
  ApiError,
  LogDirectoriesResponse,
  LogFilesResponse,
  LogContentResponse,
  DirectorySearchResponse,
} from '../types/api'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:5000'
const API_VERSION = 'v1'

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
})

/**
 * Handle API errors and extract error message
 */
function handleApiError(error: unknown): ApiError {
  if (axios.isAxiosError(error)) {
    const axiosError = error as AxiosError<ApiError>
    if (axiosError.response) {
      // Server responded with error status
      return {
        error: axiosError.response.data?.error || `Error: ${axiosError.response.status}`,
        message: axiosError.response.data?.message,
      }
    } else if (axiosError.request) {
      // Request was made but no response received
      return {
        error: 'Network error: Unable to reach the server',
      }
    }
  }
  // Unknown error
  return {
    error: error instanceof Error ? error.message : 'An unknown error occurred',
  }
}

/**
 * Get all portfolios
 */
export async function getPortfolios(): Promise<PortfolioResponse> {
  try {
    const response = await apiClient.get<PortfolioResponse>(`/api/${API_VERSION}/portfolios`)
    return response.data
  } catch (error) {
    throw handleApiError(error)
  }
}

/**
 * Get all directories
 */
export async function getDirectories(): Promise<DirectoryResponse> {
  try {
    const response = await apiClient.get<DirectoryResponse>(`/api/${API_VERSION}/directories`)
    return response.data
  } catch (error) {
    throw handleApiError(error)
  }
}

/**
 * Get files for a specific directory and portfolio
 */
export async function getFiles(
  directory: string,
  portfolioId: string
): Promise<FilesResponse> {
  try {
    const response = await apiClient.get<FilesResponse>(
      `/api/${API_VERSION}/files/${directory}/${portfolioId}`
    )
    return response.data
  } catch (error) {
    throw handleApiError(error)
  }
}

/**
 * Get file content as JSON
 */
export async function getFileContent(
  directory: string,
  portfolioId: string,
  file: string
): Promise<FileContentResponse> {
  try {
    const response = await apiClient.get<FileContentResponse>(
      `/api/${API_VERSION}/files/${directory}/${portfolioId}/${file}`
    )
    return response.data
  } catch (error) {
    throw handleApiError(error)
  }
}

/**
 * Get log directories for a portfolio
 */
export async function getLogDirectories(portfolioId: string): Promise<LogDirectoriesResponse> {
  try {
    const response = await apiClient.get<LogDirectoriesResponse>(
      `/api/${API_VERSION}/logs/directories/${portfolioId}`
    )
    return response.data
  } catch (error) {
    throw handleApiError(error)
  }
}

/**
 * Get log files in a specific log directory
 */
export async function getLogFiles(
  portfolioId: string,
  logDirectory: string
): Promise<LogFilesResponse> {
  try {
    const response = await apiClient.get<LogFilesResponse>(
      `/api/${API_VERSION}/logs/files/${portfolioId}/${logDirectory}`
    )
    return response.data
  } catch (error) {
    throw handleApiError(error)
  }
}

/**
 * Get log file content with pagination
 */
export async function getLogContent(
  portfolioId: string,
  logDirectory: string,
  file: string,
  page: number = 1,
  perPage: number = 1000,
  search?: string,
  contextLines: number = 5
): Promise<LogContentResponse> {
  try {
    const params = new URLSearchParams()
    params.append('page', page.toString())
    params.append('per_page', perPage.toString())
    if (search) {
      params.append('search', search)
      params.append('context_lines', contextLines.toString())
    }
    
    const response = await apiClient.get<LogContentResponse>(
      `/api/${API_VERSION}/logs/content/${portfolioId}/${logDirectory}/${file}?${params.toString()}`
    )
    return response.data
  } catch (error) {
    throw handleApiError(error)
  }
}

/**
 * Search across all log files in a directory
 */
export async function searchLogDirectory(
  portfolioId: string,
  logDirectory: string,
  searchQuery: string,
  page: number = 1,
  perPage: number = 50,
  contextLines: number = 5
): Promise<DirectorySearchResponse> {
  try {
    const params = new URLSearchParams()
    params.append('search', searchQuery)
    params.append('page', page.toString())
    params.append('per_page', perPage.toString())
    params.append('context_lines', contextLines.toString())
    
    const response = await apiClient.get<DirectorySearchResponse>(
      `/api/${API_VERSION}/logs/search/${portfolioId}/${logDirectory}?${params.toString()}`
    )
    return response.data
  } catch (error) {
    throw handleApiError(error)
  }
}

