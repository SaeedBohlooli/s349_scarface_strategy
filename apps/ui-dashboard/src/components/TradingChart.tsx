import React, { useEffect, useRef, useState, useCallback } from "react";
import { createChart, CandlestickSeries, LineSeries } from "lightweight-charts";
import type { UTCTimestamp } from "lightweight-charts";
import type { OHLCData, SymbolLevels } from "../types/api";
import { createRoot, type Root } from "react-dom/client";
import {
  Fullscreen,
  FullscreenExit,
  Refresh,
  HourglassEmpty,
} from "@mui/icons-material";

// Extend HTMLElement to include our React root
interface HTMLElementWithRoot extends HTMLElement {
  _reactRoot?: Root;
}

interface TradingChartProps {
  data: OHLCData[];
  symbol: string;
  levels?: SymbolLevels;
  width?: number;
  height?: number;
  timeframe?: string; // e.g., "5m", "1h", "1D", etc.
  onRefresh?: () => void; // Callback to refresh data
  isRefreshing?: boolean; // Loading state for refresh button
}

const TradingChart: React.FC<TradingChartProps> = ({
  data,
  symbol,
  levels,
  width,
  height = 400,
  timeframe,
  onRefresh,
  isRefreshing = false,
}) => {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const chartRef = useRef<any>(null);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [selectedTimeRange, setSelectedTimeRange] = useState<string>("All");

  // Auto-detect timeframe from data if not provided
  const detectTimeframe = (): string => {
    if (timeframe) return timeframe;

    if (data.length < 2) return "Unknown";

    // Calculate time difference between first two data points
    const date1 = new Date(data[0].date);
    const date2 = new Date(data[1].date);
    const diffMinutes =
      Math.abs(date2.getTime() - date1.getTime()) / (1000 * 60);

    if (diffMinutes <= 1) return "1m";
    else if (diffMinutes <= 5) return "5m";
    else if (diffMinutes <= 15) return "15m";
    else if (diffMinutes <= 30) return "30m";
    else if (diffMinutes <= 60) return "1h";
    else if (diffMinutes <= 240) return "4h";
    else if (diffMinutes <= 1440) return "1D";
    else return "1W";
  };

  const detectedTimeframe = detectTimeframe();

  // Time range selector configuration - common trading timeframes
  const timeRanges = [
    { label: "1H", hours: 1 },
    { label: "4H", hours: 4 },
    { label: "1D", hours: 24 },
    { label: "3D", hours: 72 },
    { label: "1W", hours: 168 },
    { label: "1M", hours: 720 },
    { label: "All", hours: -1 }, // Show all data
  ];

  // Function to set visible time range on the chart
  const setTimeRange = (range: string, hours: number) => {
    if (!chartRef.current) return;

    setSelectedTimeRange(range);

    if (hours === -1) {
      // Show all data
      chartRef.current.timeScale().fitContent();
    } else {
      // Calculate time range based on hours from the data
      if (data.length === 0) return;

      // Get the latest timestamp from our data
      const latestTimestamp = Math.floor(
        new Date(data[data.length - 1].date).getTime() / 1000
      ) as UTCTimestamp;
      const fromTimestamp = (latestTimestamp - hours * 60 * 60) as UTCTimestamp;

      chartRef.current.timeScale().setVisibleRange({
        from: fromTimestamp,
        to: latestTimestamp,
      });
    }
  };

  const toggleFullscreen = useCallback(() => {
    if (!chartContainerRef.current) return;

    if (!isFullscreen) {
      // Enter fullscreen
      if (chartContainerRef.current.requestFullscreen) {
        chartContainerRef.current.requestFullscreen();
      }
    } else {
      // Exit fullscreen
      if (document.exitFullscreen) {
        document.exitFullscreen();
      }
    }
  }, [isFullscreen]);

  // Listen for fullscreen changes
  useEffect(() => {
    const handleFullscreenChange = () => {
      setIsFullscreen(!!document.fullscreenElement);
    };

    document.addEventListener("fullscreenchange", handleFullscreenChange);
    return () => {
      document.removeEventListener("fullscreenchange", handleFullscreenChange);
    };
  }, []);

  useEffect(() => {
    if (!chartContainerRef.current) return;

    console.log("SimpleChart received data:", {
      symbol,
      dataLength: data.length,
      firstItem: data[0],
      lastItem: data[data.length - 1],
    });

    // Get the actual container width for responsive design
    const containerWidth = chartContainerRef.current.offsetWidth;
    const chartWidth = width || containerWidth || 800;

    // Create chart with dark theme and timezone configuration
    const chart = createChart(chartContainerRef.current, {
      width: chartWidth,
      height,
      layout: {
        textColor: "#d1d4dc",
        background: { color: "#1a1a1a" },
      },
      grid: {
        vertLines: { color: "#2a2a2a" },
        horzLines: { color: "#2a2a2a" },
      },
      // Remove watermark attempt - not available in current version
      localization: {
        timeFormatter: (time: UTCTimestamp) => {
          // Convert UTC timestamp to EST for tooltip display
          const date = new Date(time * 1000);
          return date.toLocaleString("en-US", {
            timeZone: "America/New_York",
            hour: "2-digit",
            minute: "2-digit",
            hour12: true,
          });
        },
        dateFormat: "dd MMM yyyy",
      },
      timeScale: {
        borderColor: "#485c7b",
        timeVisible: true,
        secondsVisible: false,
        fixLeftEdge: false,
        fixRightEdge: false,
        lockVisibleTimeRangeOnResize: true,
        rightBarStaysOnScroll: true,
        tickMarkFormatter: (time: UTCTimestamp) => {
          // Convert UTC timestamp to EST for display on time axis
          const date = new Date(time * 1000);
          return date.toLocaleString("en-US", {
            timeZone: "America/New_York",
            month: "short",
            day: "numeric",
            hour: "2-digit",
            minute: "2-digit",
            hour12: false,
          });
        },
      },
      rightPriceScale: {
        borderColor: "#485c7b",
        autoScale: true,
        scaleMargins: {
          top: 0.1,
          bottom: 0.1,
        },
      },
    });

    // Store chart reference for time range operations
    chartRef.current = chart;

    // Add candlestick series with blue/yellow colors
    const series = chart.addSeries(CandlestickSeries, {
      upColor: "#2196f3", // Blue for up candles
      downColor: "#ffeb3b", // Yellow for down candles
      borderVisible: false,
      wickUpColor: "#2196f3", // Blue wicks for up candles
      wickDownColor: "#ffeb3b", // Yellow wicks for down candles
    });

    // Convert our API data to the format expected by lightweight-charts
    // Use Unix timestamps to handle intraday data properly
    const chartData = data.map((item) => {
      const jsDate = new Date(item.date);
      const timestamp = Math.floor(jsDate.getTime() / 1000) as UTCTimestamp;

      return {
        time: timestamp,
        open: item.open,
        high: item.high,
        low: item.low,
        close: item.close,
      };
    });

    // Sort by time and remove any potential duplicates
    chartData.sort((a, b) => a.time - b.time);

    // Remove duplicates while keeping the latest data for each timestamp
    const deduplicatedData = chartData.filter(
      (item, index) => index === 0 || item.time !== chartData[index - 1].time
    );

    console.log("Chart data summary:", {
      original: data.length,
      processed: deduplicatedData.length,
      first: deduplicatedData[0],
      last: deduplicatedData[deduplicatedData.length - 1],
    });

    // Set the data
    series.setData(deduplicatedData);

    // Add support/resistance levels if available
    if (levels) {
      console.log("Drawing levels for", symbol, levels);

      // Define level colors and styles
      const levelStyles = {
        PDH: { color: "#ff6b6b", lineStyle: 2, title: "Previous Day High" },
        PDL: { color: "#51cf66", lineStyle: 2, title: "Previous Day Low" },
        LDH: { color: "#ffa726", lineStyle: 1, title: "Last Day High" },
        "5MH": { color: "#42a5f5", lineStyle: 1, title: "5M High" },
        "5ML": { color: "#ab47bc", lineStyle: 1, title: "5M Low" },
        PML: {
          color: "#7e57c2",
          lineStyle: 3,
          title: "Pre-Market Low",
        },
        PMH: {
          color: "#26a69a",
          lineStyle: 3,
          title: "Pre-Market High",
        },
      };

      // Get the time range from chart data for levels
      const firstTime = chartData[0]?.time;
      const lastTime = chartData[chartData.length - 1]?.time;

      // Draw each level
      Object.entries(levels).forEach(([levelType, levelData]) => {
        if (levelData && levelData.price_1) {
          const price = parseFloat(levelData.price_1);
          const style = levelStyles[levelType as keyof typeof levelStyles];

          if (style && !isNaN(price) && firstTime && lastTime) {
            // Create a line series for this level
            const levelSeries = chart.addSeries(LineSeries, {
              color: style.color,
              lineStyle: style.lineStyle,
              priceLineVisible: true,
              lastValueVisible: true,
              title: `${style.title}: ${price.toFixed(2)}`,
            });

            // Create horizontal line data points
            // Ensure we have at least 2 different timestamps for the line
            const levelData =
              firstTime === lastTime
                ? [{ time: firstTime, value: price }] // Single point if same time
                : [
                    { time: firstTime, value: price },
                    { time: lastTime, value: price },
                  ];

            levelSeries.setData(levelData);
          }
        }
      });
    }

    // Initial zoom to show only recent data with big bars
    // Show last 50-100 candles initially for better visibility
    const totalCandles = deduplicatedData.length;
    const initialCandlesToShow = Math.min(35, Math.max(50, totalCandles)); // Show 20-50 candles

    if (totalCandles > initialCandlesToShow) {
      const startIndex = totalCandles - initialCandlesToShow;
      const startTime = deduplicatedData[startIndex].time;
      const endTime = deduplicatedData[totalCandles - 1].time;

      // Set visible range to show only recent candles
      chart.timeScale().setVisibleRange({
        from: startTime,
        to: endTime,
      });
    } else {
      // If we have fewer candles, fit all content
      chart.timeScale().fitContent();
    }

    // Auto-scale the price axis to fit visible data
    chart.priceScale("right").applyOptions({
      autoScale: true,
    });

    // Add resize handler for responsive design and fullscreen
    const handleResize = () => {
      if (chartContainerRef.current) {
        const newWidth = chartContainerRef.current.offsetWidth;
        const newHeight = isFullscreen ? window.innerHeight : height;
        chart.applyOptions({
          width: newWidth,
          height: newHeight,
        });
      }
    };

    // Handle initial sizing for fullscreen
    if (isFullscreen && chartContainerRef.current) {
      chart.applyOptions({
        width: chartContainerRef.current.offsetWidth,
        height: window.innerHeight,
      });
    }

    window.addEventListener("resize", handleResize);

    return () => {
      window.removeEventListener("resize", handleResize);
      chart.remove();
    };
  }, [data, symbol, levels, width, height, isFullscreen]);

  // Inject control buttons into the lightweight-charts container
  useEffect(() => {
    if (!chartRef.current) return;

    const chartContainer = chartContainerRef.current; // Capture ref for cleanup

    const injectControlButtons = () => {
      const chartsContainer = chartContainer?.querySelector(
        ".tv-lightweight-charts"
      ) as HTMLElement;
      if (
        chartsContainer &&
        !chartsContainer.querySelector(".chart-controls")
      ) {
        const buttonContainer = document.createElement("div");
        buttonContainer.className = "chart-controls";
        buttonContainer.style.cssText = `
          position: absolute;
          top: 10px;
          left: 10px;
          display: flex;
          gap: 8px;
          z-index: 1000;
          pointer-events: auto;
        `;
        chartsContainer.appendChild(buttonContainer);

        // Create React component for buttons
        const ButtonControls = () => (
          <>
            {/* Refresh Button */}
            {onRefresh && (
              <button
                onClick={onRefresh}
                disabled={isRefreshing}
                style={{
                  background: isRefreshing
                    ? "rgba(74, 85, 104, 0.9)"
                    : "rgba(45, 55, 72, 0.9)",
                  border: "1px solid #4a5568",
                  borderRadius: "4px",
                  color: isRefreshing ? "#a0aec0" : "#e2e8f0",
                  padding: "6px",
                  cursor: isRefreshing ? "not-allowed" : "pointer",
                  fontSize: "20px",
                  fontWeight: "bold",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  transition: "background-color 0.2s",
                  width: "36px",
                  height: "36px",
                  opacity: isRefreshing ? 0.7 : 1,
                  boxShadow: isFullscreen
                    ? "0 4px 12px rgba(0,0,0,0.5)"
                    : "0 2px 4px rgba(0,0,0,0.2)",
                }}
                onMouseOver={(e) => {
                  if (!isRefreshing) {
                    e.currentTarget.style.background = "rgba(45, 55, 72, 1)";
                    e.currentTarget.style.color = "#81c784";
                  }
                }}
                onMouseOut={(e) => {
                  if (!isRefreshing) {
                    e.currentTarget.style.background = "rgba(45, 55, 72, 0.9)";
                    e.currentTarget.style.color = "#e2e8f0";
                  }
                }}
                title={isRefreshing ? "Refreshing..." : "Refresh Chart Data"}
              >
                {isRefreshing ? <HourglassEmpty /> : <Refresh />}
              </button>
            )}

            {/* Fullscreen Button */}
            <button
              onClick={toggleFullscreen}
              style={{
                background: "rgba(45, 55, 72, 0.9)",
                border: "1px solid #4a5568",
                borderRadius: "4px",
                color: "#e2e8f0",
                padding: "6px",
                cursor: "pointer",
                fontSize: "20px",
                fontWeight: "bold",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                transition: "background-color 0.2s",
                width: "36px",
                height: "36px",
                boxShadow: isFullscreen
                  ? "0 4px 12px rgba(0,0,0,0.5)"
                  : "0 2px 4px rgba(0,0,0,0.2)",
              }}
              onMouseOver={(e) => {
                e.currentTarget.style.background = "rgba(45, 55, 72, 1)";
                e.currentTarget.style.color = "#63b3ed";
              }}
              onMouseOut={(e) => {
                e.currentTarget.style.background = "rgba(45, 55, 72, 0.9)";
                e.currentTarget.style.color = "#e2e8f0";
              }}
              title={isFullscreen ? "Exit Fullscreen" : "Enter Fullscreen"}
            >
              {isFullscreen ? <FullscreenExit /> : <Fullscreen />}
            </button>
          </>
        );

        // Use React to render the component
        const root = createRoot(buttonContainer);
        root.render(<ButtonControls />);

        // Store root for cleanup
        (buttonContainer as HTMLElementWithRoot)._reactRoot = root;
      }
    };

    // Inject buttons after chart is ready
    const timeoutId = setTimeout(injectControlButtons, 100);

    return () => {
      clearTimeout(timeoutId);
      // Clean up injected buttons
      const chartsContainer = chartContainer?.querySelector(
        ".tv-lightweight-charts"
      );
      const buttonContainer = chartsContainer?.querySelector(".chart-controls");
      if (buttonContainer) {
        // Unmount React component
        const root = (buttonContainer as HTMLElementWithRoot)._reactRoot;
        if (root) {
          root.unmount();
        }
        buttonContainer.remove();
      }
    };
  }, [isFullscreen, isRefreshing, onRefresh, toggleFullscreen]);

  if (!data || data.length === 0) {
    return (
      <div
        style={{
          width,
          height,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          border: "1px solid #444",
          backgroundColor: "#1a1a1a",
          color: "#d1d4dc",
          borderRadius: "4px",
        }}
      >
        <div>
          <h3>No Data Available</h3>
          <p>Select a symbol and timeframe to display chart data</p>
        </div>
      </div>
    );
  }

  return (
    <div>
      <div
        style={{
          marginBottom: "10px",
          padding: "10px",
          backgroundColor: "#2d3748",
          borderRadius: "5px",
          border: "1px solid #4a5568",
        }}
      >
        <h3 style={{ margin: 0, color: "#e2e8f0" }}>📈 {symbol} Chart</h3>
        <p
          style={{ margin: "5px 0 0 0", fontSize: "0.9rem", color: "#a0aec0" }}
        >
          {data.length} data points • From {data[0]?.date} to{" "}
          {data[data.length - 1]?.date}
          {levels && Object.keys(levels).length > 0 && (
            <span style={{ marginLeft: "10px", color: "#81c784" }}>
              • {Object.keys(levels).length} levels displayed
            </span>
          )}
        </p>
      </div>

      {/* Time Range Selector */}
      <div
        style={{
          marginBottom: "10px",
          padding: "8px",
          backgroundColor: "#1a202c",
          borderRadius: "5px",
          border: "1px solid #4a5568",
          display: "flex",
          alignItems: "center",
          gap: "8px",
          flexWrap: "wrap",
        }}
      >
        <span
          style={{ color: "#a0aec0", fontSize: "0.9rem", fontWeight: "500" }}
        >
          Time Range:
        </span>
        {timeRanges.map((range) => (
          <button
            key={range.label}
            onClick={() => setTimeRange(range.label, range.hours)}
            style={{
              padding: "4px 12px",
              fontSize: "0.85rem",
              fontWeight: "500",
              border: "1px solid",
              borderRadius: "4px",
              cursor: "pointer",
              transition: "all 0.2s",
              backgroundColor:
                selectedTimeRange === range.label ? "#3182ce" : "transparent",
              borderColor:
                selectedTimeRange === range.label ? "#3182ce" : "#4a5568",
              color: selectedTimeRange === range.label ? "#ffffff" : "#a0aec0",
            }}
            onMouseOver={(e) => {
              if (selectedTimeRange !== range.label) {
                e.currentTarget.style.backgroundColor = "#2d3748";
                e.currentTarget.style.borderColor = "#718096";
              }
            }}
            onMouseOut={(e) => {
              if (selectedTimeRange !== range.label) {
                e.currentTarget.style.backgroundColor = "transparent";
                e.currentTarget.style.borderColor = "#4a5568";
              }
            }}
          >
            {range.label}
          </button>
        ))}
      </div>

      <div style={{ position: "relative" }}>
        <div
          ref={chartContainerRef}
          style={{
            width: "100%",
            height: isFullscreen ? "100vh" : height + "px",
            border: isFullscreen ? "none" : "1px solid #4a5568",
            margin: "0",
            borderRadius: isFullscreen ? "0" : "4px",
            position: "relative", // Ensure this is the positioning context
            backgroundColor: isFullscreen ? "#1a1a1a" : "transparent",
            overflow: "hidden", // Prevent content overflow
            isolation: isFullscreen ? "isolate" : "auto", // Create new stacking context in fullscreen
          }}
        >
          {/* Ticker Symbol & Timeframe Watermark - TradingView Style */}
          <div
            style={{
              position: "absolute",
              top: "50%",
              left: "50%",
              transform: "translate(-50%, -50%)",
              color: "rgba(255, 255, 255, 0.03)",
              fontSize: isFullscreen ? "110px" : "80px",
              fontWeight: "900",
              fontFamily:
                "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
              pointerEvents: "none",
              zIndex: 1000,
              userSelect: "none",
              letterSpacing: "8px",
              textAlign: "center",
              lineHeight: "1",
            }}
          >
            {symbol}/{detectedTimeframe.toUpperCase()}
          </div>
        </div>
      </div>
    </div>
  );
};

export default TradingChart;
