import React from "react";
import { Outlet } from "react-router-dom";
import Navigation from "../components/Navigation";

const Layout: React.FC = () => {
  const layoutStyle: React.CSSProperties = {
    minHeight: "100vh",
  };

  const mainStyle: React.CSSProperties = {
    paddingBottom: "3rem",
  };

  const footerStyle: React.CSSProperties = {
    backgroundColor: "#2c3e50",
    color: "#ecf0f1",
    textAlign: "center",
    padding: "2rem 0",
    marginTop: "3rem",
  };

  return (
    <div style={layoutStyle}>
      <Navigation />
      <main style={mainStyle}>
        <Outlet />
      </main>
      <footer style={footerStyle}>
        <div
          style={{ maxWidth: "1200px", margin: "0 auto", padding: "0 2rem" }}
        >
          <p style={{ margin: 0 }}>
            © 2025 S349 Scarface Strategy Dashboard - Built with React &
            TypeScript
          </p>
        </div>
      </footer>
    </div>
  );
};

export default Layout;
