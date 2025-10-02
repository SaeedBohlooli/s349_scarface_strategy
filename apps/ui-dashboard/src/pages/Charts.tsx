import React from "react";
import ApiDemo from "../components/ApiDemo";

const Charts: React.FC = () => {
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

      <ApiDemo />
    </div>
  );
};

export default Charts;
