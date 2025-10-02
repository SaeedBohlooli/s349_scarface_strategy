import React from "react";
import { Link, useLocation } from "react-router-dom";

const Navigation: React.FC = () => {
  const location = useLocation();

  const navStyle: React.CSSProperties = {
    backgroundColor: "#2c3e50",
    padding: "1rem 0",
    marginBottom: "2rem",
    boxShadow: "0 2px 4px rgba(0,0,0,0.1)",
  };

  const containerStyle: React.CSSProperties = {
    maxWidth: "1200px",
    margin: "0 auto",
    padding: "0 2rem",
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
  };

  const logoStyle: React.CSSProperties = {
    color: "#ecf0f1",
    fontSize: "1.5rem",
    fontWeight: "bold",
    textDecoration: "none",
  };

  const navLinksStyle: React.CSSProperties = {
    display: "flex",
    gap: "2rem",
    listStyle: "none",
    margin: 0,
    padding: 0,
  };

  const linkStyle = (isActive: boolean): React.CSSProperties => ({
    color: isActive ? "#3498db" : "#ecf0f1",
    textDecoration: "none",
    padding: "0.5rem 1rem",
    borderRadius: "4px",
    transition: "all 0.3s ease",
    backgroundColor: isActive ? "rgba(52, 152, 219, 0.1)" : "transparent",
    border: isActive ? "1px solid #3498db" : "1px solid transparent",
  });

  return (
    <nav style={navStyle}>
      <div style={containerStyle}>
        <Link to="/" style={logoStyle}>
          📊 S349 Scarface Strategy
        </Link>
        <ul style={navLinksStyle}>
          <li>
            <Link to="/" style={linkStyle(location.pathname === "/")}>
              🏠 Home
            </Link>
          </li>
          <li>
            <Link
              to="/charts"
              style={linkStyle(location.pathname === "/charts")}
            >
              📈 Charts
            </Link>
          </li>
        </ul>
      </div>
    </nav>
  );
};

export default Navigation;
