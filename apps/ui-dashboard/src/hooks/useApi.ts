import { useState, useEffect, useCallback } from "react";
import { apiService } from "../services/ApiService";
import type {
  DataResponse,
  FileListResponse,
  StatsResponse,
  MappedLevelsResponse,
  SymbolLevels,
  DataQueryParams,
} from "../types/api";

// Generic hook for API calls with loading and error states
function useApiCall<T>() {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const execute = useCallback(async (apiCall: () => Promise<T>) => {
    setLoading(true);
    setError(null);
    try {
      const result = await apiCall();
      setData(result);
      return result;
    } catch (err) {
      const errorMessage =
        err instanceof Error ? err.message : "An error occurred";
      setError(errorMessage);
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  const reset = useCallback(() => {
    setData(null);
    setError(null);
    setLoading(false);
  }, []);

  return { data, loading, error, execute, reset };
}

// Hook for getting file list and available symbols/timeframes
export function useFileList() {
  const { data, loading, error, execute } = useApiCall<FileListResponse>();

  const fetchFileList = useCallback(() => {
    return execute(() => apiService.getFileList());
  }, [execute]);

  useEffect(() => {
    fetchFileList();
  }, [fetchFileList]);

  return {
    fileList: data,
    loading,
    error,
    refetch: fetchFileList,
  };
}

// Hook for getting OHLC data
export function useOHLCData(
  symbol?: string,
  timeframe?: string,
  params?: DataQueryParams
) {
  const { data, loading, error, execute, reset } = useApiCall<DataResponse>();

  const fetchData = useCallback(
    (sym?: string, tf?: string, queryParams?: DataQueryParams) => {
      const s = sym || symbol;
      const t = tf || timeframe;

      if (!s || !t) {
        throw new Error("Symbol and timeframe are required");
      }

      return execute(() => apiService.getOHLCData(s, t, queryParams || params));
    },
    [symbol, timeframe, params, execute]
  );

  useEffect(() => {
    if (symbol && timeframe) {
      fetchData();
    }
  }, [symbol, timeframe, params, fetchData]);

  return {
    ohlcData: data,
    loading,
    error,
    fetchData,
    reset,
  };
}

// Hook for getting multiple symbols data
export function useMultipleSymbolsData() {
  const { data, loading, error, execute } = useApiCall<DataResponse[]>();

  const fetchMultipleSymbols = useCallback(
    (symbols: string[], timeframe: string) => {
      return execute(() =>
        apiService.getMultipleSymbolsData({ symbols, timeframe })
      );
    },
    [execute]
  );

  return {
    multipleData: data,
    loading,
    error,
    fetchMultipleSymbols,
  };
}

// Hook for getting statistics
export function useStats(symbol?: string, timeframe?: string) {
  const { data, loading, error, execute } = useApiCall<StatsResponse>();

  const fetchStats = useCallback(
    (sym?: string, tf?: string) => {
      const s = sym || symbol;
      const t = tf || timeframe;

      if (!s || !t) {
        throw new Error("Symbol and timeframe are required");
      }

      return execute(() => apiService.getStats(s, t));
    },
    [symbol, timeframe, execute]
  );

  useEffect(() => {
    if (symbol && timeframe) {
      fetchStats();
    }
  }, [symbol, timeframe, fetchStats]);

  return {
    stats: data,
    loading,
    error,
    fetchStats,
  };
}

// Hook for getting levels data
export function useLevels() {
  const { data, loading, error, execute } = useApiCall<MappedLevelsResponse>();

  const fetchAllLevels = useCallback(() => {
    return execute(() => apiService.getAllLevels());
  }, [execute]);

  useEffect(() => {
    fetchAllLevels();
  }, [fetchAllLevels]);
  console.log("useLevels Levels Data from hook:", data);
  return {
    allLevels: data,
    loading,
    error,
    refetch: fetchAllLevels,
  };
}

// Hook for getting levels for a specific symbol
export function useSymbolLevels(symbol?: string) {
  const { data, loading, error, execute } = useApiCall<SymbolLevels>();

  const fetchSymbolLevels = useCallback(
    (sym?: string) => {
      const s = sym || symbol;

      if (!s) {
        throw new Error("Symbol is required");
      }

      return execute(() => apiService.getSymbolLevels(s));
    },
    [symbol, execute]
  );

  useEffect(() => {
    if (symbol) {
      fetchSymbolLevels();
    }
  }, [symbol, fetchSymbolLevels]);
  return {
    symbolLevels: data,
    loading,
    error,
    fetchSymbolLevels,
  };
}

// Hook for portfolio overview (combines multiple API calls)
export function usePortfolioOverview(symbols: string[], timeframe: string) {
  const [portfolioData, setPortfolioData] = useState<{
    data: DataResponse[];
    levels: MappedLevelsResponse;
    stats: StatsResponse[];
  } | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchPortfolioOverview = useCallback(async () => {
    if (symbols.length === 0 || !timeframe) return;

    setLoading(true);
    setError(null);

    try {
      const overview = await apiService.getPortfolioOverview(
        symbols,
        timeframe
      );
      setPortfolioData(overview);
    } catch (err) {
      const errorMessage =
        err instanceof Error
          ? err.message
          : "Failed to fetch portfolio overview";
      setError(errorMessage);
    } finally {
      setLoading(false);
    }
  }, [symbols, timeframe]);

  useEffect(() => {
    fetchPortfolioOverview();
  }, [fetchPortfolioOverview]);

  return {
    portfolioData,
    loading,
    error,
    refetch: fetchPortfolioOverview,
  };
}

// Hook for real-time data updates (polling)
export function useRealTimeData(
  symbol: string,
  timeframe: string,
  intervalMs: number = 30000 // 30 seconds default
) {
  const { data, loading, error, execute } = useApiCall<DataResponse>();
  const [isPolling, setIsPolling] = useState(false);

  const startPolling = useCallback(() => {
    setIsPolling(true);
  }, []);

  const stopPolling = useCallback(() => {
    setIsPolling(false);
  }, []);

  const fetchData = useCallback(() => {
    return execute(() => apiService.getOHLCData(symbol, timeframe));
  }, [symbol, timeframe, execute]);

  useEffect(() => {
    if (symbol && timeframe) {
      fetchData(); // Initial fetch
    }
  }, [symbol, timeframe, fetchData]);

  useEffect(() => {
    if (!isPolling || !symbol || !timeframe) return;

    const interval = setInterval(() => {
      fetchData();
    }, intervalMs);

    return () => clearInterval(interval);
  }, [isPolling, symbol, timeframe, intervalMs, fetchData]);

  return {
    data,
    loading,
    error,
    isPolling,
    startPolling,
    stopPolling,
    refetch: fetchData,
  };
}
