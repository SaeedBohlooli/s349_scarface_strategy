import { DataFormatter } from '../services/DataFormatter';

async function testDataFormatter() {
  const formatter = new DataFormatter();

  try {
    console.log('🔍 Testing Data Formatter...\n');

    // 1. Get list of available files
    console.log('📁 Available files:');
    const fileList = await formatter.getFileList();
    console.log(JSON.stringify(fileList, null, 2));

    // 2. Get AAPL 1min data (first 5 records)
    console.log('\n📈 AAPL 1min data (first 5 records):');
    const aaplData = await formatter.getPaginatedData('AAPL', '1min', 1, 5);
    console.log(JSON.stringify(aaplData, null, 2));

    // 3. Get drawing objects
    console.log('\n🎨 Drawing objects:');
    const drawingObjects = await formatter.readDrawingObjects();
    console.log(`Found ${drawingObjects.length} drawing objects`);
    if (drawingObjects.length > 0) {
      console.log('First drawing object:', JSON.stringify(drawingObjects[0], null, 2));
    }

    // 4. Get multiple symbols data
    console.log('\n📊 Multiple symbols data (first 2 records each):');
    const multipleData = await formatter.getMultipleSymbolsData(['AAPL', 'TSLA'], '1min');
    multipleData.forEach(data => {
      console.log(`${data.symbol}: ${data.data.length} records, latest: ${data.data[data.data.length - 1]?.date}`);
    });

  } catch (error) {
    console.error('❌ Error:', error instanceof Error ? error.message : error);
  }
}

// Run the test if this file is executed directly
if (require.main === module) {
  testDataFormatter();
}

export { testDataFormatter };