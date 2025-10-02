import React, { useState } from "react";
import {
  useFileList,
  useOHLCData,
  useStats,
  useLevels,
  usePortfolioOverview,
} from "../hooks/useApi";
import type { DataQueryParams } from "../types/api";

const ApiDemo: React.FC = () => {
  const [selectedSymbol, setSelectedSymbol] = useState<string>("");
  const [selectedTimeframe, setSelectedTimeframe] = useState<string>("");
  const [queryParams, setQueryParams] = useState<DataQueryParams>({
    limit: 10,
  });

  // Fetch available files/symbols/timeframes
  const {
    fileList,
    loading: fileListLoading,
    error: fileListError,
  } = useFileList();

  // Fetch OHLC data for selected symbol
  const {
    ohlcData,
    loading: ohlcLoading,
    error: ohlcError,
    fetchData,
  } = useOHLCData(selectedSymbol, selectedTimeframe, queryParams);

  // Fetch statistics for selected symbol
  const {
    stats,
    loading: statsLoading,
    error: statsError,
  } = useStats(selectedSymbol, selectedTimeframe);

  // Fetch all levels
  const { allLevels, loading: levelsLoading, error: levelsError } = useLevels();

  // Portfolio overview for all available symbols
  const {
    portfolioData,
    loading: portfolioLoading,
    error: portfolioError,
  } = usePortfolioOverview(fileList?.symbols || [], selectedTimeframe);

  const handleSymbolChange = (symbol: string) => {
    setSelectedSymbol(symbol);
  };

  const handleTimeframeChange = (timeframe: string) => {
    setSelectedTimeframe(timeframe);
  };

  const handleLimitChange = (limit: number) => {
    setQueryParams({ ...queryParams, limit });
  };

  const handleRefreshData = () => {
    if (selectedSymbol && selectedTimeframe) {
      fetchData(selectedSymbol, selectedTimeframe, queryParams);
    }
  };

  return (
    <div style={{ padding: "20px", fontFamily: "Arial, sans-serif" }}>
      <h1>📊 S349 Scarface Strategy - API Demo</h1>

      {/* File List Section */}
      <div
        style={{
          marginBottom: "30px",
          padding: "15px",
          border: "1px solid #ddd",
          borderRadius: "5px",
        }}
      >
        <h2>📁 Available Files</h2>
        {fileListLoading && <p>Loading file list...</p>}
        {fileListError && (
          <p style={{ color: "red" }}>Error: {fileListError}</p>
        )}
        {fileList && (
          <div>
            <p>
              <strong>Symbols:</strong> {fileList.symbols.join(", ")}
            </p>
            <p>
              <strong>Timeframes:</strong> {fileList.timeframes.join(", ")}
            </p>
            <p>
              <strong>Total Files:</strong> {fileList.files.length}
            </p>
          </div>
        )}
      </div>

      {/* Symbol and Timeframe Selection */}
      <div
        style={{
          marginBottom: "30px",
          padding: "15px",
          border: "1px solid #ddd",
          borderRadius: "5px",
        }}
      >
        <h2>🎯 Data Selection</h2>
        <div style={{ marginBottom: "10px" }}>
          <label>
            Symbol:
            <select
              value={selectedSymbol}
              onChange={(e) => handleSymbolChange(e.target.value)}
              style={{ marginLeft: "10px", padding: "5px" }}
            >
              <option value="">Select Symbol</option>
              {fileList?.symbols.map((symbol) => (
                <option key={symbol} value={symbol}>
                  {symbol}
                </option>
              ))}
            </select>
          </label>
        </div>
        <div style={{ marginBottom: "10px" }}>
          <label>
            Timeframe:
            <select
              value={selectedTimeframe}
              onChange={(e) => handleTimeframeChange(e.target.value)}
              style={{ marginLeft: "10px", padding: "5px" }}
            >
              <option value="">Select Timeframe</option>
              {fileList?.timeframes.map((timeframe) => (
                <option key={timeframe} value={timeframe}>
                  {timeframe}
                </option>
              ))}
            </select>
          </label>
        </div>
        <div style={{ marginBottom: "10px" }}>
          <label>
            Limit:
            <input
              type="number"
              value={queryParams.limit || 10}
              onChange={(e) => handleLimitChange(parseInt(e.target.value))}
              style={{ marginLeft: "10px", padding: "5px", width: "100px" }}
            />
          </label>
        </div>
        <button
          onClick={handleRefreshData}
          disabled={!selectedSymbol || !selectedTimeframe}
          style={{
            padding: "10px 20px",
            backgroundColor: "#007bff",
            color: "white",
            border: "none",
            borderRadius: "5px",
          }}
        >
          🔄 Refresh Data
        </button>
      </div>

      {/* OHLC Data Section */}
      {selectedSymbol && selectedTimeframe && (
        <div
          style={{
            marginBottom: "30px",
            padding: "15px",
            border: "1px solid #ddd",
            borderRadius: "5px",
          }}
        >
          <h2>
            📈 OHLC Data for {selectedSymbol} ({selectedTimeframe})
          </h2>
          {ohlcLoading && <p>Loading OHLC data...</p>}
          {ohlcError && <p style={{ color: "red" }}>Error: {ohlcError}</p>}
          {ohlcData && (
            <div>
              <p>
                <strong>Total Records:</strong> {ohlcData.metadata.totalRecords}
              </p>
              <p>
                <strong>Date Range:</strong> {ohlcData.metadata.startDate} to{" "}
                {ohlcData.metadata.endDate}
              </p>
              <p>
                <strong>Showing:</strong> {ohlcData.data.length} records
              </p>

              {ohlcData.data.length > 0 && (
                <div style={{ marginTop: "15px" }}>
                  <h3>Latest Data Points:</h3>
                  <div style={{ maxHeight: "200px", overflowY: "auto" }}>
                    <table
                      style={{ width: "100%", borderCollapse: "collapse" }}
                    >
                      <thead>
                        <tr style={{ backgroundColor: "#f8f9fa" }}>
                          <th
                            style={{ border: "1px solid #ddd", padding: "8px" }}
                          >
                            Date
                          </th>
                          <th
                            style={{ border: "1px solid #ddd", padding: "8px" }}
                          >
                            Open
                          </th>
                          <th
                            style={{ border: "1px solid #ddd", padding: "8px" }}
                          >
                            High
                          </th>
                          <th
                            style={{ border: "1px solid #ddd", padding: "8px" }}
                          >
                            Low
                          </th>
                          <th
                            style={{ border: "1px solid #ddd", padding: "8px" }}
                          >
                            Close
                          </th>
                          <th
                            style={{ border: "1px solid #ddd", padding: "8px" }}
                          >
                            Volume
                          </th>
                        </tr>
                      </thead>
                      <tbody>
                        {ohlcData.data.slice(-5).map((item, index) => (
                          <tr key={index}>
                            <td
                              style={{
                                border: "1px solid #ddd",
                                padding: "8px",
                              }}
                            >
                              {new Date(item.date).toLocaleString()}
                            </td>
                            <td
                              style={{
                                border: "1px solid #ddd",
                                padding: "8px",
                              }}
                            >
                              {item.open.toFixed(2)}
                            </td>
                            <td
                              style={{
                                border: "1px solid #ddd",
                                padding: "8px",
                              }}
                            >
                              {item.high.toFixed(2)}
                            </td>
                            <td
                              style={{
                                border: "1px solid #ddd",
                                padding: "8px",
                              }}
                            >
                              {item.low.toFixed(2)}
                            </td>
                            <td
                              style={{
                                border: "1px solid #ddd",
                                padding: "8px",
                              }}
                            >
                              {item.close.toFixed(2)}
                            </td>
                            <td
                              style={{
                                border: "1px solid #ddd",
                                padding: "8px",
                              }}
                            >
                              {item.volume.toLocaleString()}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Statistics Section */}
      {selectedSymbol && selectedTimeframe && (
        <div
          style={{
            marginBottom: "30px",
            padding: "15px",
            border: "1px solid #ddd",
            borderRadius: "5px",
          }}
        >
          <h2>
            📊 Statistics for {selectedSymbol} ({selectedTimeframe})
          </h2>
          {statsLoading && <p>Loading statistics...</p>}
          {statsError && <p style={{ color: "red" }}>Error: {statsError}</p>}
          {stats && (
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "1fr 1fr",
                gap: "20px",
              }}
            >
              <div>
                <h3>💰 Price Statistics</h3>
                <ul>
                  <li>
                    <strong>Min:</strong> ${stats.priceStats.min.toFixed(2)}
                  </li>
                  <li>
                    <strong>Max:</strong> ${stats.priceStats.max.toFixed(2)}
                  </li>
                  <li>
                    <strong>Average:</strong> $
                    {stats.priceStats.average.toFixed(2)}
                  </li>
                  <li>
                    <strong>Latest:</strong> $
                    {stats.priceStats.latest.toFixed(2)}
                  </li>
                </ul>
              </div>
              <div>
                <h3>📦 Volume Statistics</h3>
                <ul>
                  <li>
                    <strong>Min:</strong>{" "}
                    {stats.volumeStats.min.toLocaleString()}
                  </li>
                  <li>
                    <strong>Max:</strong>{" "}
                    {stats.volumeStats.max.toLocaleString()}
                  </li>
                  <li>
                    <strong>Average:</strong>{" "}
                    {stats.volumeStats.average.toLocaleString()}
                  </li>
                  <li>
                    <strong>Total:</strong>{" "}
                    {stats.volumeStats.total.toLocaleString()}
                  </li>
                </ul>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Levels Section */}
      <div
        style={{
          marginBottom: "30px",
          padding: "15px",
          border: "1px solid #ddd",
          borderRadius: "5px",
        }}
      >
        <h2>🎯 Support/Resistance Levels</h2>
        {levelsLoading && <p>Loading levels...</p>}
        {levelsError && <p style={{ color: "red" }}>Error: {levelsError}</p>}
        {allLevels && (
          <div>
            {Object.entries(allLevels).map(([symbol, levels]) => (
              <div key={symbol} style={{ marginBottom: "20px" }}>
                <h3>{symbol}</h3>
                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
                    gap: "10px",
                  }}
                >
                  {Object.entries(levels).map(([levelType, levelData]) => (
                    <div
                      key={levelType}
                      style={{
                        padding: "10px",
                        backgroundColor: "#f8f9fa",
                        borderRadius: "3px",
                      }}
                    >
                      <strong>{levelType}:</strong> ${levelData.price_1}
                      <br />
                      <small style={{ color: "#666" }}>{levelData.memo}</small>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Portfolio Overview */}
      {selectedTimeframe && (
        <div
          style={{
            marginBottom: "30px",
            padding: "15px",
            border: "1px solid #ddd",
            borderRadius: "5px",
          }}
        >
          <h2>📋 Portfolio Overview ({selectedTimeframe})</h2>
          {portfolioLoading && <p>Loading portfolio overview...</p>}
          {portfolioError && (
            <p style={{ color: "red" }}>Error: {portfolioError}</p>
          )}
          {portfolioData && (
            <div>
              <p>
                <strong>Symbols:</strong> {portfolioData.data.length}
              </p>
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(auto-fit, minmax(250px, 1fr))",
                  gap: "15px",
                }}
              >
                {portfolioData.stats.map((stat) => (
                  <div
                    key={stat.symbol}
                    style={{
                      padding: "15px",
                      backgroundColor: "#f8f9fa",
                      borderRadius: "5px",
                    }}
                  >
                    <h4>{stat.symbol}</h4>
                    <p>
                      <strong>Latest:</strong> $
                      {stat.priceStats.latest.toFixed(2)}
                    </p>
                    <p>
                      <strong>Range:</strong> ${stat.priceStats.min.toFixed(2)}{" "}
                      - ${stat.priceStats.max.toFixed(2)}
                    </p>
                    <p>
                      <strong>Records:</strong>{" "}
                      {stat.totalRecords.toLocaleString()}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default ApiDemo;
