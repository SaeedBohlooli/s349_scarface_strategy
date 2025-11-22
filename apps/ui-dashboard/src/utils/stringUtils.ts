/**
 * Convert snake_case string to camelCase
 * @param str - String in snake_case format
 * @returns String in camelCase format
 */
export function toCamelCase(str: string): string {
  return str
    .split('_')
    .map((word, index) => {
      if (index === 0) {
        return word.toLowerCase()
      }
      return word.charAt(0).toUpperCase() + word.slice(1).toLowerCase()
    })
    .join('')
}

/**
 * Format column header for display
 * Splits by underscore and capitalizes each word
 * @param str - String in snake_case format
 * @returns Formatted string for display (e.g., "Key Levels Df")
 */
export function formatColumnHeader(str: string): string {
  return str
    .split('_')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
    .join(' ')
}

