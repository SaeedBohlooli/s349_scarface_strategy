import React, { useEffect, useRef } from "react";
import { createChart, CandlestickSeries } from "lightweight-charts";
import type { UTCTimestamp } from "lightweight-charts";
import type { OHLCData } from "../types/api";

interface TradingChartProps {
  data: OHLCData[];
  symbol: string;
  width?: number;
  height?: number;
}

const TradingChart: React.FC<TradingChartProps> = ({
  data,
  symbol,
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
  }, [data, symbol, width, height]);

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
