import fs from "fs";
import path from "path";
import csv from "csv-parser";
import {
  OHLCData,
  DataResponse,
  FileListResponse,
  DrawingObject,
  MappedLevelsResponse,
  SymbolLevels,
  LevelData,
} from "../types";

export class DataFormatter {
  private readonly chartsPath: string;

  constructor(portfolioId: string = "p250") {
    this.chartsPath = path.resolve(
      __dirname,
      `../../../../portfolios/charts/${portfolioId}`
    );
  }

  /**
   * Get list of all available files in the charts directory
   */
  async getFileList(): Promise<FileListResponse> {
    try {
      const files = await fs.promises.readdir(this.chartsPath);
      const csvFiles = files.filter((file) => file.endsWith(".csv"));

      // Extract symbols and timeframes from filenames
      const symbols = new Set<string>();
      const timeframes = new Set<string>();

      csvFiles.forEach((file) => {
        const match = file.match(/^([A-Z]+)-(\w+)\.csv$/);
        if (match) {
          const [, symbol, timeframe] = match;
          symbols.add(symbol);
          timeframes.add(timeframe);
        }
      });

      return {
        files: csvFiles,
        symbols: Array.from(symbols).sort(),
        timeframes: Array.from(timeframes).sort(),
      };
    } catch (error) {
      throw new Error(
        `Failed to read charts directory: ${
          error instanceof Error ? error.message : "Unknown error"
        }`
      );
    }
  }

  /**
   * Read and parse OHLC data from CSV file
   */
  async readOHLCData(symbol: string, timeframe: string): Promise<DataResponse> {
    const filename = `${symbol}-${timeframe}.csv`;
    const filePath = path.join(this.chartsPath, filename);

    if (!fs.existsSync(filePath)) {
      throw new Error(`File not found: ${filename}`);
    }

    return new Promise((resolve, reject) => {
      const data: OHLCData[] = [];

      fs.createReadStream(filePath)
        .pipe(csv())
        .on("data", (row) => {
          try {
            data.push({
              date: row.date,
              open: parseFloat(row.open),
              close: parseFloat(row.close),
              high: parseFloat(row.high),
              low: parseFloat(row.low),
              volume: parseFloat(row.volume),
            });
          } catch (error) {
            console.warn(`Error parsing row: ${JSON.stringify(row)}`);
          }
        })
        .on("end", () => {
          const metadata = this.generateMetadata(
            data,
            symbol,
            timeframe,
            filePath
          );
          resolve({
            symbol,
            timeframe,
            data,
            metadata,
          });
        })
        .on("error", (error) => {
          reject(new Error(`Failed to read CSV file: ${error.message}`));
        });
    });
  }

  /**
   * Read drawing objects data
   */
  async readDrawingObjects(): Promise<DrawingObject[]> {
    const filename = "10-drawing_objects_df.csv";
    const filePath = path.join(this.chartsPath, filename);

    if (!fs.existsSync(filePath)) {
      throw new Error(`Drawing objects file not found: ${filename}`);
    }

    return new Promise((resolve, reject) => {
      const data: DrawingObject[] = [];

      fs.createReadStream(filePath)
        .pipe(csv())
        .on("data", (row) => {
          data.push(row);
        })
        .on("end", () => {
          resolve(data);
        })
        .on("error", (error) => {
          reject(
            new Error(`Failed to read drawing objects file: ${error.message}`)
          );
        });
    });
  }

  /**
   * Get data for multiple symbols
   */
  async getMultipleSymbolsData(
    symbols: string[],
    timeframe: string
  ): Promise<DataResponse[]> {
    const promises = symbols.map((symbol) =>
      this.readOHLCData(symbol, timeframe)
    );
    return Promise.all(promises);
  }

  /**
   * Get data with pagination
   */
  async getPaginatedData(
    symbol: string,
    timeframe: string,
    page: number = 1,
    limit: number = 1000
  ): Promise<DataResponse> {
    const fullData = await this.readOHLCData(symbol, timeframe);
    const startIndex = (page - 1) * limit;
    const endIndex = startIndex + limit;

    return {
      ...fullData,
      data: fullData.data.slice(startIndex, endIndex),
      metadata: {
        ...fullData.metadata,
        totalRecords: fullData.data.length,
        page,
        limit,
        totalPages: Math.ceil(fullData.data.length / limit),
      } as any,
    };
  }

  /**
   * Get data within a date range
   */
  async getDataByDateRange(
    symbol: string,
    timeframe: string,
    startDate: string,
    endDate: string
  ): Promise<DataResponse> {
    const fullData = await this.readOHLCData(symbol, timeframe);

    const filteredData = fullData.data.filter((item) => {
      const itemDate = new Date(item.date);
      const start = new Date(startDate);
      const end = new Date(endDate);
      return itemDate >= start && itemDate <= end;
    });

    return {
      ...fullData,
      data: filteredData,
      metadata: {
        ...fullData.metadata,
        totalRecords: filteredData.length,
        dateRange: { startDate, endDate },
      } as any,
    };
  }

  /**
   * Map drawing objects to organized levels by symbol
   */
  async getMappedLevels(): Promise<MappedLevelsResponse> {
    const drawingObjects = await this.readDrawingObjects();
    const mappedLevels: MappedLevelsResponse = {};

    drawingObjects.forEach((obj) => {
      const { symbol, unique_id } = obj;

      // Initialize symbol if not exists
      if (!mappedLevels[symbol]) {
        mappedLevels[symbol] = {};
      }

      // Extract level type from unique_id
      const levelType = this.extractLevelType(unique_id);

      if (levelType) {
        // Remove unique_id from the object and create LevelData
        const { unique_id: _, ...levelData } = obj;
        mappedLevels[symbol][levelType] = levelData as LevelData;
      }
    });

    return mappedLevels;
  }

  /**
   * Get levels for a specific symbol
   */
  async getSymbolLevels(symbol: string): Promise<SymbolLevels> {
    const mappedLevels = await this.getMappedLevels();
    return mappedLevels[symbol.toUpperCase()] || {};
  }

  /**
   * Get a specific level for a symbol
   */
  async getSpecificLevel(
    symbol: string,
    levelType: string
  ): Promise<LevelData | null> {
    const symbolLevels = await this.getSymbolLevels(symbol);
    return symbolLevels[levelType as keyof SymbolLevels] || null;
  }

  /**
   * Extract level type from unique_id
   */
  private extractLevelType(uniqueId: string): keyof SymbolLevels | null {
    // Handle different patterns in unique_id
    if (uniqueId.includes("-PDH")) return "PDH";
    if (uniqueId.includes("-PDL")) return "PDL";
    if (uniqueId.includes("-LDH")) return "LDH";
    if (uniqueId.includes("HIGH_5_MIN")) return "5MH";
    if (uniqueId.includes("LOW_5_MIN")) return "5ML";

    return null;
  }

  /**
   * Generate metadata for the dataset
   */
  private generateMetadata(
    data: OHLCData[],
    symbol: string,
    timeframe: string,
    filePath: string
  ) {
    const stats = fs.statSync(filePath);

    return {
      totalRecords: data.length,
      startDate: data.length > 0 ? data[0].date : "",
      endDate: data.length > 0 ? data[data.length - 1].date : "",
      lastUpdated: stats.mtime.toISOString(),
    };
  }
}
