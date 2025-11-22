/**
 * Check if data is suitable for table display
 * Data is suitable if:
 * - It's an array
 * - Each item is an object (not nested arrays/objects)
 * - Values are primitive types (string, number, boolean, null)
 */
export function isTableSuitable(data: unknown): boolean {
  // Must be an array
  if (!Array.isArray(data)) {
    return false
  }

  // Empty array is fine for table
  if (data.length === 0) {
    return true
  }

  // Check first few items to determine structure
  const sampleSize = Math.min(10, data.length)
  for (let i = 0; i < sampleSize; i++) {
    const item = data[i]
    
    // Each item must be an object
    if (typeof item !== 'object' || item === null || Array.isArray(item)) {
      return false
    }

    // Check all values in the object
    for (const key in item) {
      if (Object.prototype.hasOwnProperty.call(item, key)) {
        const value = item[key]
        
        // Values must be primitive types (not nested objects/arrays)
        if (value !== null && typeof value === 'object') {
          // If it's an object or array, it's too complex for table
          return false
        }
      }
    }
  }

  return true
}

