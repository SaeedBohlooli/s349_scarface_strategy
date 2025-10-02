import React, { useEffect, useRef } from "react";
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

    // Create chart with dark theme
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
      timeScale: {
        borderColor: "#485c7b",
      },
      rightPriceScale: {
        borderColor: "#485c7b",
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
    const chartData = data.map((item) => ({
      time: Math.floor(new Date(item.date).getTime() / 1000) as UTCTimestamp,
      open: item.open,
      high: item.high,
      low: item.low,
      close: item.close,
    }));

    console.log("Converted chart data:", chartData.slice(0, 3));

    // Set the data
    series.setData(chartData);

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
            const levelData = [
              { time: firstTime, value: price },
              { time: lastTime, value: price },
            ];

            levelSeries.setData(levelData);
          }
        }
      });
    }

    // Fit content to show all data
    chart.timeScale().fitContent();

    // Add resize handler for responsive design
    const handleResize = () => {
      if (chartContainerRef.current) {
        const newWidth = chartContainerRef.current.offsetWidth;
        chart.applyOptions({ width: newWidth });
      }
    };

    window.addEventListener("resize", handleResize);

    return () => {
      window.removeEventListener("resize", handleResize);
      chart.remove();
    };
  }, [data, symbol, levels, width, height]);

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
      <div
        ref={chartContainerRef}
        style={{
          width: "100%",
          height: height + "px",
          border: "1px solid #4a5568",
          margin: "0",
          borderRadius: "4px",
        }}
      />
    </div>
  );
};

export default TradingChart;
