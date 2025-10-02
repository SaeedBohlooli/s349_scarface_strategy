import { DataFormatter } from "../services/DataFormatter";

async function testLevelsMapping() {
  const formatter = new DataFormatter();

  try {
    console.log("🎯 Testing Levels Mapping...\n");

    // 1. Get all mapped levels
    console.log("📊 All mapped levels:");
    const allLevels = await formatter.getMappedLevels();
    console.log(JSON.stringify(allLevels, null, 2));

    // 2. Get levels for QQQ
    console.log("\n📈 QQQ levels:");
    const qqqLevels = await formatter.getSymbolLevels("QQQ");
    console.log(JSON.stringify(qqqLevels, null, 2));

    // 3. Get specific level (PDH for QQQ)
    console.log("\n🎯 QQQ PDH level:");
    const qqqPDH = await formatter.getSpecificLevel("QQQ", "PDH");
    console.log(JSON.stringify(qqqPDH, null, 2));

    // 4. Test for AAPL
    console.log("\n🍎 AAPL levels:");
    const aaplLevels = await formatter.getSymbolLevels("AAPL");
    console.log(JSON.stringify(aaplLevels, null, 2));

    // 5. Test for TSLA
    console.log("\n🚗 TSLA levels:");
    const tslaLevels = await formatter.getSymbolLevels("TSLA");
    console.log(JSON.stringify(tslaLevels, null, 2));

    // 6. Test non-existent level
    console.log("\n❌ Non-existent level test:");
    const nonExistent = await formatter.getSpecificLevel("QQQ", "INVALID");
    console.log("Non-existent level result:", nonExistent);
  } catch (error) {
    console.error("❌ Error:", error instanceof Error ? error.message : error);
  }
}

// Run the test if this file is executed directly
if (require.main === module) {
  testLevelsMapping();
}

export { testLevelsMapping };
