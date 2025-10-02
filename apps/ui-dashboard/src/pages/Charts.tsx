import React, { useState } from "react";
import ApiDemo from "../components/ApiDemo";
import SimpleChart from "../components/TradingChart";
import { useFileList, useOHLCData, useLevels } from "../hooks/useApi";
import type { DataQueryParams } from "../types/api";

const Charts: React.FC = () => {
  const [selectedSymbol, setSelectedSymbol] = useState<string>("");
  const [selectedTimeframe, setSelectedTimeframe] = useState<string>("");
  const [queryParams, setQueryParams] = useState<DataQueryParams>({
    limit: 100000, // Get much more data for charts (default 100k bars)
  });

  // Fetch available files/symbols/timeframes
  const { fileList } = useFileList();

  // Fetch OHLC data for selected symbol
  const {
    ohlcData,
    fetchData,
    loading: ohlcLoading,
  } = useOHLCData(selectedSymbol, selectedTimeframe, queryParams);

  // Fetch all levels
  const { allLevels } = useLevels();

  // Debug logging
  console.log("Charts page state:", {
    selectedSymbol,
    selectedTimeframe,
    hasOhlcData: !!ohlcData,
    ohlcDataLength: ohlcData?.data?.length || 0,
    hasLevels: !!allLevels,
    levelsForSymbol: allLevels?.[selectedSymbol],
  });

  const containerStyle: React.CSSProperties = {
    maxWidth: "1400px",
    margin: "0 auto",
    padding: "0 2rem",
  };

  const headerStyle: React.CSSProperties = {
    textAlign: "center",
    marginBottom: "2rem",
    padding: "2rem 0",
    background: "linear-gradient(135deg, #667eea 0%, #764ba2 100%)",
    borderRadius: "12px",
    color: "white",
  };

  const chartSectionStyle: React.CSSProperties = {
    marginBottom: "3rem",
    padding: "2rem",
    backgroundColor: "#f8f9fa",
    borderRadius: "12px",
    border: "1px solid #e9ecef",
  };

  const symbolSelectorStyle: React.CSSProperties = {
    marginBottom: "2rem",
    padding: "1rem",
    backgroundColor: "white",
    borderRadius: "8px",
    border: "1px solid #dee2e6",
  };

  return (
    <div style={containerStyle}>
      <div style={headerStyle}>
        <h1 style={{ fontSize: "2.5rem", marginBottom: "1rem" }}>
          📈 Charts & Analytics
        </h1>
        <p style={{ fontSize: "1.1rem", opacity: 0.9 }}>
          Interactive financial data visualization and analysis tools
        </p>
      </div>

      {/* Interactive Chart Section */}
      <div style={chartSectionStyle}>
        <h2 style={{ marginBottom: "1.5rem", color: "#2c3e50" }}>
          🎯 Interactive Trading Chart
        </h2>

        {/* Symbol and Timeframe Selection */}
        <div style={symbolSelectorStyle}>
          <div
            style={{
              display: "flex",
              gap: "1rem",
              alignItems: "center",
              flexWrap: "wrap",
            }}
          >
            <div>
              <label style={{ marginRight: "0.5rem", fontWeight: "bold" }}>
                Symbol:
              </label>
              <select
                value={selectedSymbol}
                onChange={(e) => setSelectedSymbol(e.target.value)}
                style={{
                  padding: "0.5rem",
                  borderRadius: "4px",
                  border: "1px solid #ced4da",
                  minWidth: "120px",
                }}
              >
                <option value="">Select Symbol</option>
                {fileList?.symbols.map((symbol) => (
                  <option key={symbol} value={symbol}>
                    {symbol}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label style={{ marginRight: "0.5rem", fontWeight: "bold" }}>
                Timeframe:
              </label>
              <select
                value={selectedTimeframe}
                onChange={(e) => setSelectedTimeframe(e.target.value)}
                style={{
                  padding: "0.5rem",
                  borderRadius: "4px",
                  border: "1px solid #ced4da",
                  minWidth: "120px",
                }}
              >
                <option value="">Select Timeframe</option>
                {fileList?.timeframes.map((timeframe) => (
                  <option key={timeframe} value={timeframe}>
                    {timeframe}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label style={{ marginRight: "0.5rem", fontWeight: "bold" }}>
                Data Points:
              </label>
              <input
                type="number"
                value={queryParams.limit || 100000}
                onChange={(e) =>
                  setQueryParams({
                    ...queryParams,
                    limit: parseInt(e.target.value),
                  })
                }
                style={{
                  padding: "0.5rem",
                  borderRadius: "4px",
                  border: "1px solid #ced4da",
                  width: "100px",
                }}
                min="10"
                max="1000000"
              />
            </div>
          </div>
        </div>

        {/* Simple Chart with Real Data */}
        {selectedSymbol && selectedTimeframe && ohlcData?.data ? (
          <SimpleChart
            data={ohlcData.data}
            symbol={selectedSymbol}
            levels={allLevels?.[selectedSymbol]}
            height={500}
            timeframe={selectedTimeframe}
            onRefresh={() =>
              fetchData(selectedSymbol, selectedTimeframe, queryParams)
            }
            isRefreshing={ohlcLoading}
          />
        ) : (
          <div
            style={{
              padding: "3rem",
              textAlign: "center",
              backgroundColor: "white",
              borderRadius: "8px",
              border: "2px dashed #dee2e6",
              color: "#6c757d",
            }}
          >
            <h3>📊 Select Symbol and Timeframe</h3>
            <p>
              Choose a symbol and timeframe from the dropdowns above to display
              the interactive chart
            </p>
          </div>
        )}
      </div>

      {/* API Demo Section */}
      <div style={{ marginTop: "2rem" }}>
        <h2 style={{ marginBottom: "1.5rem", color: "#2c3e50" }}>
          🔧 API Demo & Raw Data
        </h2>
        <ApiDemo />
      </div>
    </div>
  );
};

export default Charts;
