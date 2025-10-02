import express, { Request, Response } from "express";
import { DataFormatter } from "../services/DataFormatter";

const router = express.Router();
const dataFormatter = new DataFormatter();

// Get list of available files and symbols
router.get("/files", async (req: Request, res: Response) => {
  try {
    const fileList = await dataFormatter.getFileList();
    res.json({
      success: true,
      data: fileList,
    });
  } catch (error) {
    res.status(500).json({
      success: false,
      error: error instanceof Error ? error.message : "Unknown error",
    });
  }
});

// Get OHLC data for a specific symbol and timeframe
router.get("/data/:symbol/:timeframe", async (req: Request, res: Response) => {
  try {
    const { symbol, timeframe } = req.params;
    const { page, limit, startDate, endDate } = req.query;

    let data;

    if (startDate && endDate) {
      // Get data by date range
      data = await dataFormatter.getDataByDateRange(
        symbol.toUpperCase(),
        timeframe,
        startDate as string,
        endDate as string
      );
    } else if (page || limit) {
      // Get paginated data
      data = await dataFormatter.getPaginatedData(
        symbol.toUpperCase(),
        timeframe,
        page ? parseInt(page as string) : 1,
        limit ? parseInt(limit as string) : 1000
      );
    } else {
      // Get all data
      data = await dataFormatter.readOHLCData(symbol.toUpperCase(), timeframe);
    }

    res.json({
      success: true,
      data,
    });
  } catch (error) {
    res.status(404).json({
      success: false,
      error: error instanceof Error ? error.message : "Unknown error",
    });
  }
});

// Get data for multiple symbols
router.post("/data/multiple", async (req: Request, res: Response) => {
  try {
    const { symbols, timeframe } = req.body;

    if (!symbols || !Array.isArray(symbols) || !timeframe) {
      return res.status(400).json({
        success: false,
        error:
          "Invalid request body. Expected { symbols: string[], timeframe: string }",
      });
    }

    const data = await dataFormatter.getMultipleSymbolsData(
      symbols.map((s: string) => s.toUpperCase()),
      timeframe
    );

    res.json({
      success: true,
      data,
    });
  } catch (error) {
    res.status(500).json({
      success: false,
      error: error instanceof Error ? error.message : "Unknown error",
    });
  }
});

// Get drawing objects
router.get("/drawing-objects", async (req: Request, res: Response) => {
  try {
    const data = await dataFormatter.readDrawingObjects();
    res.json({
      success: true,
      data,
    });
  } catch (error) {
    res.status(500).json({
      success: false,
      error: error instanceof Error ? error.message : "Unknown error",
    });
  }
});

// Get basic statistics for a symbol
router.get("/stats/:symbol/:timeframe", async (req: Request, res: Response) => {
  try {
    const { symbol, timeframe } = req.params;
    const data = await dataFormatter.readOHLCData(
      symbol.toUpperCase(),
      timeframe
    );

    // Calculate basic statistics
    const prices = data.data.map((d) => d.close);
    const volumes = data.data.map((d) => d.volume);

    const stats = {
      symbol: data.symbol,
      timeframe: data.timeframe,
      totalRecords: data.data.length,
      priceStats: {
        min: Math.min(...prices),
        max: Math.max(...prices),
        average: prices.reduce((a, b) => a + b, 0) / prices.length,
        latest: prices[prices.length - 1],
      },
      volumeStats: {
        min: Math.min(...volumes),
        max: Math.max(...volumes),
        average: volumes.reduce((a, b) => a + b, 0) / volumes.length,
        total: volumes.reduce((a, b) => a + b, 0),
      },
      dateRange: {
        start: data.metadata.startDate,
        end: data.metadata.endDate,
      },
    };

    res.json({
      success: true,
      data: stats,
    });
  } catch (error) {
    res.status(404).json({
      success: false,
      error: error instanceof Error ? error.message : "Unknown error",
    });
  }
});

// Get mapped levels for all symbols
router.get("/levels", async (req: Request, res: Response) => {
  try {
    const data = await dataFormatter.getMappedLevels();
    res.json({
      success: true,
      data,
    });
  } catch (error) {
    res.status(500).json({
      success: false,
      error: error instanceof Error ? error.message : "Unknown error",
    });
  }
});

// Get levels for a specific symbol
router.get("/levels/:symbol", async (req: Request, res: Response) => {
  try {
    const { symbol } = req.params;
    const data = await dataFormatter.getSymbolLevels(symbol.toUpperCase());
    res.json({
      success: true,
      data,
    });
  } catch (error) {
    res.status(500).json({
      success: false,
      error: error instanceof Error ? error.message : "Unknown error",
    });
  }
});

// Get a specific level for a symbol
router.get(
  "/levels/:symbol/:levelType",
  async (req: Request, res: Response) => {
    try {
      const { symbol, levelType } = req.params;
      const data = await dataFormatter.getSpecificLevel(
        symbol.toUpperCase(),
        levelType
      );

      if (!data) {
        return res.status(404).json({
          success: false,
          error: `Level ${levelType} not found for symbol ${symbol.toUpperCase()}`,
        });
      }

      res.json({
        success: true,
        data,
      });
    } catch (error) {
      res.status(500).json({
        success: false,
        error: error instanceof Error ? error.message : "Unknown error",
      });
    }
  }
);

export default router;
