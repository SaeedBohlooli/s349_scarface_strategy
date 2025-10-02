import React, { useEffect, useRef, useState } from "react";
import { createChart, CandlestickSeries, LineSeries } from "lightweight-charts";
import type { UTCTimestamp } from "lightweight-charts";
import type { OHLCData, SymbolLevels } from "../types/api";

interface TradingChartProps {
  data: OHLCData[];
  symbol: string;
  levels?: SymbolLevels;
  width?: number;
  height?: number;
}

const TradingChart: React.FC<TradingChartProps> = ({
  data,
  symbol,
  levels,
  width,
  height = 400,
}) => {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const [isFullscreen, setIsFullscreen] = useState(false);

  const toggleFullscreen = () => {
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
  };

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
      <div style={{ position: "relative" }}>
        <div
          ref={chartContainerRef}
          style={{
            width: "100%",
            height: isFullscreen ? "100vh" : height + "px",
            border: "1px solid #4a5568",
            margin: "0",
            borderRadius: "4px",
          }}
        />

        {/* Fullscreen Button */}
        <button
          onClick={toggleFullscreen}
          style={{
            position: "absolute",
            top: "10px",
            right: "10px",
            background: "rgba(45, 55, 72, 0.9)",
            border: "1px solid #4a5568",
            borderRadius: "4px",
            color: "#e2e8f0",
            padding: "8px 12px",
            cursor: "pointer",
            fontSize: "14px",
            fontWeight: "bold",
            zIndex: 1000,
            display: "flex",
            alignItems: "center",
            gap: "4px",
            transition: "background-color 0.2s",
          }}
          onMouseOver={(e) => {
            e.currentTarget.style.background = "rgba(45, 55, 72, 1)";
          }}
          onMouseOut={(e) => {
            e.currentTarget.style.background = "rgba(45, 55, 72, 0.9)";
          }}
          title={isFullscreen ? "Exit Fullscreen" : "Enter Fullscreen"}
        >
          {isFullscreen ? "⊟" : "⊠"} {isFullscreen ? "Exit" : "Fullscreen"}
        </button>
      </div>
    </div>
  );
};

export default TradingChart;
