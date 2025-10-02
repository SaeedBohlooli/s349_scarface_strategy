import axios, { type AxiosResponse } from "axios";
import type {
  ApiResponse,
  DataResponse,
  DrawingObject,
  MappedLevelsResponse,
  SymbolLevels,
  LevelData,
  FileListResponse,
  StatsResponse,
  MultipleSymbolsRequest,
  DataQueryParams,
} from "../types/api";

// Create axios instance with base configuration
const apiClient = axios.create({
  baseURL: "/api/v1", // This will use the proxy we set up in vite.config.ts
  timeout: 30000, // 30 seconds timeout
  headers: {
    "Content-Type": "application/json",
  },
});

// Request interceptor for logging
apiClient.interceptors.request.use(
  (config) => {
    console.log(
      `🚀 API Request: ${config.method?.toUpperCase()} ${config.url}`
    );
    return config;
  },
  (error) => {
    console.error("❌ Request Error:", error);
    return Promise.reject(error);
  }
);

// Response interceptor for logging and error handling
apiClient.interceptors.response.use(
  (response) => {
    console.log(`✅ API Response: ${response.config.url} - ${response.status}`);
    return response;
  },
  (error) => {
    console.error("❌ Response Error:", error.response?.data || error.message);
    return Promise.reject(error);
  }
);

class ApiService {
  // File and metadata endpoints
  async getFileList(): Promise<FileListResponse> {
    const response: AxiosResponse<ApiResponse<FileListResponse>> =
      await apiClient.get("/files");
    return response.data.data;
  }

  // OHLC Data endpoints
  async getOHLCData(
    symbol: string,
    timeframe: string,
    params?: DataQueryParams
  ): Promise<DataResponse> {
    const queryParams = new URLSearchParams();

    if (params?.page) queryParams.append("page", params.page.toString());
    if (params?.limit) queryParams.append("limit", params.limit.toString());
    if (params?.startDate) queryParams.append("startDate", params.startDate);
    if (params?.endDate) queryParams.append("endDate", params.endDate);

    const url = `/data/${symbol}/${timeframe}${
      queryParams.toString() ? `?${queryParams.toString()}` : ""
    }`;
    const response: AxiosResponse<ApiResponse<DataResponse>> =
      await apiClient.get(url);
    return response.data.data;
  }

  async getMultipleSymbolsData(
    request: MultipleSymbolsRequest
  ): Promise<DataResponse[]> {
    const response: AxiosResponse<ApiResponse<DataResponse[]>> =
      await apiClient.post("/data/multiple", request);
    return response.data.data;
  }

  // Drawing Objects endpoints
  async getDrawingObjects(): Promise<DrawingObject[]> {
    const response: AxiosResponse<ApiResponse<DrawingObject[]>> =
      await apiClient.get("/drawing-objects");
    return response.data.data;
  }

  // Levels endpoints
  async getAllLevels(): Promise<MappedLevelsResponse> {
    const response: AxiosResponse<ApiResponse<MappedLevelsResponse>> =
      await apiClient.get("/levels");
    return response.data.data;
  }

  async getSymbolLevels(symbol: string): Promise<SymbolLevels> {
    const response: AxiosResponse<ApiResponse<SymbolLevels>> =
      await apiClient.get(`/levels/${symbol}`);
    return response.data.data;
  }

  async getSpecificLevel(
    symbol: string,
    levelType: string
  ): Promise<LevelData> {
    const response: AxiosResponse<ApiResponse<LevelData>> = await apiClient.get(
      `/levels/${symbol}/${levelType}`
    );
    return response.data.data;
  }

  // Statistics endpoints
  async getStats(symbol: string, timeframe: string): Promise<StatsResponse> {
    const response: AxiosResponse<ApiResponse<StatsResponse>> =
      await apiClient.get(`/stats/${symbol}/${timeframe}`);
    return response.data.data;
  }

  // Utility methods for common operations
  async getSymbolsAndTimeframes(): Promise<{
    symbols: string[];
    timeframes: string[];
  }> {
    const fileList = await this.getFileList();
    return {
      symbols: fileList.symbols,
      timeframes: fileList.timeframes,
    };
  }

  async getLatestDataForSymbol(
    symbol: string,
    timeframe: string,
    limit = 100
  ): Promise<DataResponse> {
    return this.getOHLCData(symbol, timeframe, { limit });
  }

  async getDateRangeData(
    symbol: string,
    timeframe: string,
    startDate: string,
    endDate: string
  ): Promise<DataResponse> {
    return this.getOHLCData(symbol, timeframe, { startDate, endDate });
  }

  // Batch operations
  async getAllSymbolsLatestData(
    timeframe: string,
    symbols?: string[]
  ): Promise<DataResponse[]> {
    if (!symbols) {
      const fileList = await this.getFileList();
      symbols = fileList.symbols;
    }

    return this.getMultipleSymbolsData({ symbols, timeframe });
  }

  async getPortfolioOverview(
    symbols: string[],
    timeframe: string
  ): Promise<{
    data: DataResponse[];
    levels: MappedLevelsResponse;
    stats: StatsResponse[];
  }> {
    const [data, levels, ...statsResponses] = await Promise.all([
      this.getMultipleSymbolsData({ symbols, timeframe }),
      this.getAllLevels(),
      ...symbols.map((symbol) => this.getStats(symbol, timeframe)),
    ]);

    return {
      data,
      levels,
      stats: statsResponses,
    };
  }
}

// Create and export a singleton instance
export const apiService = new ApiService();

// Export the class for testing or custom instances
export default ApiService;
