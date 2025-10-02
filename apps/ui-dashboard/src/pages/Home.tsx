import React from "react";
import { Link } from "react-router-dom";
import { useFileList, useLevels, usePortfolioOverview } from "../hooks/useApi";

const Home: React.FC = () => {
  const {
    fileList,
    loading: fileListLoading,
    error: fileListError,
  } = useFileList();
  const { allLevels, loading: levelsLoading } = useLevels();
  const { portfolioData, loading: portfolioLoading } = usePortfolioOverview(
    fileList?.symbols || [],
    "1min"
  );

  const containerStyle: React.CSSProperties = {
    maxWidth: "1200px",
    margin: "0 auto",
    padding: "0 2rem",
  };

  const heroStyle: React.CSSProperties = {
    textAlign: "center",
    padding: "3rem 0",
    background: "linear-gradient(135deg, #667eea 0%, #764ba2 100%)",
    borderRadius: "12px",
    color: "white",
    marginBottom: "3rem",
  };

  const gridStyle: React.CSSProperties = {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))",
    gap: "2rem",
    marginBottom: "3rem",
  };

  const cardStyle: React.CSSProperties = {
    backgroundColor: "#ffffff",
    padding: "2rem",
    borderRadius: "12px",
    boxShadow: "0 4px 6px rgba(0, 0, 0, 0.1)",
    border: "1px solid #e1e8ed",
  };

  const statsCardStyle: React.CSSProperties = {
    ...cardStyle,
    background: "linear-gradient(135deg, #f093fb 0%, #f5576c 100%)",
    color: "white",
  };

  const levelsCardStyle: React.CSSProperties = {
    ...cardStyle,
    background: "linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)",
    color: "white",
  };

  const buttonStyle: React.CSSProperties = {
    backgroundColor: "#3498db",
    color: "white",
    padding: "1rem 2rem",
    border: "none",
    borderRadius: "8px",
    fontSize: "1.1rem",
    cursor: "pointer",
    textDecoration: "none",
    display: "inline-block",
    transition: "all 0.3s ease",
    marginTop: "1rem",
  };

  if (fileListLoading) {
    return (
      <div style={containerStyle}>
        <div style={{ textAlign: "center", padding: "3rem" }}>
          <h2>Loading dashboard...</h2>
        </div>
      </div>
    );
  }

  if (fileListError) {
    return (
      <div style={containerStyle}>
        <div style={{ textAlign: "center", padding: "3rem", color: "red" }}>
          <h2>Error loading data</h2>
          <p>{fileListError}</p>
        </div>
      </div>
    );
  }

  return (
    <div style={containerStyle}>
      {/* Hero Section */}
      <div style={heroStyle}>
        <h1 style={{ fontSize: "3rem", marginBottom: "1rem" }}>
          📊 S349 Scarface Strategy Dashboard
        </h1>
        <p style={{ fontSize: "1.2rem", marginBottom: "2rem", opacity: 0.9 }}>
          Real-time financial data analysis and portfolio management
        </p>
        <Link to="/charts" style={buttonStyle}>
          🚀 Explore Charts
        </Link>
      </div>

      {/* Quick Stats Grid */}
      <div style={gridStyle}>
        {/* Portfolio Overview */}
        <div style={statsCardStyle}>
          <h3 style={{ marginBottom: "1rem", fontSize: "1.5rem" }}>
            📋 Portfolio Overview
          </h3>
          {portfolioLoading ? (
            <p>Loading portfolio data...</p>
          ) : portfolioData ? (
            <div>
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  marginBottom: "1rem",
                }}
              >
                <span>Active Symbols:</span>
                <strong>{portfolioData.data.length}</strong>
              </div>
              <div style={{ marginBottom: "1rem" }}>
                <strong>Symbols:</strong>{" "}
                {portfolioData.data.map((d) => d.symbol).join(", ")}
              </div>
              <div>
                <strong>Total Records:</strong>{" "}
                {portfolioData.stats
                  .reduce((sum, stat) => sum + stat.totalRecords, 0)
                  .toLocaleString()}
              </div>
            </div>
          ) : (
            <p>No portfolio data available</p>
          )}
        </div>

        {/* Available Data */}
        <div style={cardStyle}>
          <h3
            style={{
              marginBottom: "1rem",
              fontSize: "1.5rem",
              color: "#2c3e50",
            }}
          >
            📁 Available Data
          </h3>
          {fileList ? (
            <div>
              <div style={{ marginBottom: "1rem" }} className="text-black">
                <strong>Symbols ({fileList.symbols.length}):</strong>
                <div style={{ marginTop: "0.5rem" }}>
                  {fileList.symbols.map((symbol) => (
                    <span
                      key={symbol}
                      style={{
                        display: "inline-block",
                        backgroundColor: "#ecf0f1",
                        padding: "0.25rem 0.5rem",
                        margin: "0.25rem",
                        borderRadius: "4px",
                        fontSize: "0.9rem",
                      }}
                    >
                      {symbol}
                    </span>
                  ))}
                </div>
              </div>
              <div style={{ marginBottom: "1rem" }}>
                <strong>Timeframes:</strong> {fileList.timeframes.join(", ")}
              </div>
              <div>
                <strong>Total Files:</strong> {fileList.files.length}
              </div>
            </div>
          ) : (
            <p>Loading file information...</p>
          )}
        </div>

        {/* Support/Resistance Levels */}
        <div style={levelsCardStyle}>
          <h3 style={{ marginBottom: "1rem", fontSize: "1.5rem" }}>
            🎯 Support/Resistance Levels
          </h3>
          {levelsLoading ? (
            <p>Loading levels...</p>
          ) : allLevels ? (
            <div>
              <div style={{ marginBottom: "1rem" }}>
                <strong>Symbols with Levels:</strong>{" "}
                {Object.keys(allLevels).length}
              </div>
              <div style={{ marginBottom: "1rem" }}>
                <strong>Total Levels:</strong>{" "}
                {Object.values(allLevels).reduce(
                  (total, symbolLevels) =>
                    total + Object.keys(symbolLevels).length,
                  0
                )}
              </div>
              <div style={{ fontSize: "0.9rem" }}>
                <strong>Level Types:</strong> PDH, PDL, LDH, 5MH, 5ML
              </div>
            </div>
          ) : (
            <p>No levels data available</p>
          )}
        </div>
      </div>

      {/* Latest Price Updates */}
      {portfolioData && (
        <div style={cardStyle}>
          <h3
            style={{
              marginBottom: "1.5rem",
              fontSize: "1.5rem",
              color: "#2c3e50",
            }}
          >
            💰 Latest Price Updates
          </h3>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
              gap: "1rem",
            }}
          >
            {portfolioData.stats.map((stat) => (
              <div
                key={stat.symbol}
                style={{
                  padding: "1rem",
                  backgroundColor: "#f8f9fa",
                  borderRadius: "8px",
                  textAlign: "center",
                  border: "2px solid #e9ecef",
                }}
              >
                <h4 style={{ margin: "0 0 0.5rem 0", color: "#2c3e50" }}>
                  {stat.symbol}
                </h4>
                <div
                  style={{
                    fontSize: "1.2rem",
                    fontWeight: "bold",
                    color: "#27ae60",
                  }}
                >
                  ${stat.priceStats.latest.toFixed(2)}
                </div>
                <div
                  style={{
                    fontSize: "0.9rem",
                    color: "#7f8c8d",
                    marginTop: "0.25rem",
                  }}
                >
                  Range: ${stat.priceStats.min.toFixed(2)} - $
                  {stat.priceStats.max.toFixed(2)}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Feature Cards */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(250px, 1fr))",
          gap: "1.5rem",
          marginTop: "3rem",
        }}
      >
        <div style={cardStyle}>
          <h4 style={{ color: "#2c3e50", marginBottom: "1rem" }}>
            📈 Real-time Charts
          </h4>
          <p style={{ color: "#7f8c8d", marginBottom: "1rem" }}>
            Interactive OHLC charts with support/resistance levels
          </p>
          <Link
            to="/charts"
            style={{
              ...buttonStyle,
              fontSize: "0.9rem",
              padding: "0.75rem 1.5rem",
            }}
          >
            View Charts
          </Link>
        </div>

        <div style={cardStyle}>
          <h4 style={{ color: "#2c3e50", marginBottom: "1rem" }}>
            🎯 Level Analysis
          </h4>
          <p style={{ color: "#7f8c8d", marginBottom: "1rem" }}>
            Previous day high/low and 5-minute levels
          </p>
          <Link
            to="/charts"
            style={{
              ...buttonStyle,
              fontSize: "0.9rem",
              padding: "0.75rem 1.5rem",
            }}
          >
            Analyze Levels
          </Link>
        </div>

        <div style={cardStyle}>
          <h4 style={{ color: "#2c3e50", marginBottom: "1rem" }}>
            📊 Portfolio Stats
          </h4>
          <p style={{ color: "#7f8c8d", marginBottom: "1rem" }}>
            Comprehensive portfolio analytics and metrics
          </p>
          <Link
            to="/charts"
            style={{
              ...buttonStyle,
              fontSize: "0.9rem",
              padding: "0.75rem 1.5rem",
            }}
          >
            View Stats
          </Link>
        </div>
      </div>
    </div>
  );
};

export default Home;
