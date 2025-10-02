import express from "express";
import dataRoutes from "./routes/data";

const app = express();
const PORT = process.env.PORT || 3000;

// Middleware
app.use(express.json());
app.use(express.urlencoded({ extended: true }));

// CORS middleware (basic)
app.use((req, res, next) => {
  res.header("Access-Control-Allow-Origin", "*");
  res.header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS");
  res.header(
    "Access-Control-Allow-Headers",
    "Origin, X-Requested-With, Content-Type, Accept, Authorization"
  );

  if (req.method === "OPTIONS") {
    res.sendStatus(200);
  } else {
    next();
  }
});

// Routes
app.use("/api/v1", dataRoutes);

// Health check endpoint
app.get("/health", (req, res) => {
  res.json({
    status: "OK",
    timestamp: new Date().toISOString(),
    service: "S349 Scarface Strategy API",
  });
});

// Root endpoint
app.get("/", (req, res) => {
  res.json({
    message: "S349 Scarface Strategy API",
    version: "1.0.0",
    endpoints: {
      health: "/health",
      files: "/api/v1/files",
      data: "/api/v1/data/:symbol/:timeframe",
      multipleData: "/api/v1/data/multiple",
      drawingObjects: "/api/v1/drawing-objects",
      stats: "/api/v1/stats/:symbol/:timeframe",
    },
  });
});

// Error handling middleware
app.use(
  (
    err: Error,
    req: express.Request,
    res: express.Response,
    next: express.NextFunction
  ) => {
    console.error("Error:", err.message);
    res.status(500).json({
      success: false,
      error: "Internal server error",
    });
  }
);

// 404 handler
app.use("*", (req, res) => {
  res.status(404).json({
    success: false,
    error: "Endpoint not found",
  });
});

app.listen(PORT, () => {
  console.log(`🚀 Server running on port ${PORT}`);
  console.log(`📊 Data API ready at http://localhost:${PORT}/api/v1`);
  console.log(`🔍 Health check: http://localhost:${PORT}/health`);
});
