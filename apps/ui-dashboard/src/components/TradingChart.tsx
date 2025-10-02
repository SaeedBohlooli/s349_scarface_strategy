import React, { useEffect, useRef } from "react";
import { createChart, CandlestickSeries } from "lightweight-charts";
import type { UTCTimestamp } from "lightweight-charts";
import type { OHLCData } from "../types/api";

interface SimpleChartProps {
  data: OHLCData[];
  symbol: string;
  width?: number;
  height?: number;
}

const SimpleChart: React.FC<SimpleChartProps> = ({
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

    // Create chart
    const chart = createChart(chartContainerRef.current, {
      width: chartWidth,
      height,
      layout: {
        textColor: "black",
        background: { color: "white" },
      },
      grid: {
        vertLines: { color: "#f0f0f0" },
        horzLines: { color: "#f0f0f0" },
      },
    });

    // Add candlestick series using the correct v5 API
    const series = chart.addSeries(CandlestickSeries, {
      upColor: "#26a69a",
      downColor: "#ef5350",
      borderVisible: false,
      wickUpColor: "#26a69a",
      wickDownColor: "#ef5350",
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
          border: "1px solid #ccc",
          backgroundColor: "#f9f9f9",
          color: "#666",
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
          backgroundColor: "#f8f9fa",
          borderRadius: "5px",
        }}
      >
        <h3 style={{ margin: 0 }}>📈 {symbol} Chart</h3>
        <p style={{ margin: "5px 0 0 0", fontSize: "0.9rem", color: "#666" }}>
          {data.length} data points • From {data[0]?.date} to{" "}
          {data[data.length - 1]?.date}
        </p>
      </div>
      <div
        ref={chartContainerRef}
        style={{
          width: "100%",
          height: height + "px",
          border: "1px solid #ccc",
          margin: "0",
        }}
      />
    </div>
  );
};

export default SimpleChart;
