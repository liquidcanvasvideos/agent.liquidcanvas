/**
 * Safe utility functions for handling arrays and API responses
 * Prevents crashes from undefined/null values and invalid data structures
 */

/**
 * Safely checks if a value is a valid array
 * @param value - The value to check
 * @returns true if value is a non-null array, false otherwise
 */
export function isSafeArray(value: any): value is any[] {
  return Array.isArray(value) && value !== null && value !== undefined
}

/**
 * Safely executes forEach on an array, with error handling
 * @param array - The array to iterate over
 * @param callback - The callback function to execute for each element
 * @param context - Optional context for error logging
 */
export function safeForEach<T>(
  array: T[] | null | undefined,
  callback: (item: T, index: number, array: T[]) => void,
  context?: string
): void {
  if (!isSafeArray(array)) {
    const contextMsg = context ? ` in ${context}` : ''
    console.warn(`⚠️ safeForEach: Array is not valid${contextMsg}. Got:`, typeof array, array)
    return
  }

  try {
    array.forEach(callback)
  } catch (error) {
    const contextMsg = context ? ` in ${context}` : ''
    console.error(`❌ Error in safeForEach${contextMsg}:`, error)
    // Continue execution - don't crash the app
  }
}

/**
 * Safely executes map on an array, returns empty array if invalid
 * @param array - The array to map over
 * @param callback - The callback function to execute for each element
 * @param context - Optional context for error logging
 * @returns Mapped array or empty array if input is invalid
 */
export function safeMap<T, R>(
  array: T[] | null | undefined,
  callback: (item: T, index: number, array: T[]) => R,
  context?: string
): R[] {
  if (!isSafeArray(array)) {
    const contextMsg = context ? ` in ${context}` : ''
    console.warn(`⚠️ safeMap: Array is not valid${contextMsg}. Got:`, typeof array, array)
    return []
  }

  try {
    return array.map(callback)
  } catch (error) {
    const contextMsg = context ? ` in ${context}` : ''
    console.error(`❌ Error in safeMap${contextMsg}:`, error)
    return [] // Return empty array instead of crashing
  }
}

/**
 * Safely executes filter on an array, returns empty array if invalid
 * @param array - The array to filter
 * @param callback - The filter predicate function
 * @param context - Optional context for error logging
 * @returns Filtered array or empty array if input is invalid
 */
export function safeFilter<T>(
  array: T[] | null | undefined,
  callback: (item: T, index: number, array: T[]) => boolean,
  context?: string
): T[] {
  if (!isSafeArray(array)) {
    const contextMsg = context ? ` in ${context}` : ''
    console.warn(`⚠️ safeFilter: Array is not valid${contextMsg}. Got:`, typeof array, array)
    return []
  }

  try {
    return array.filter(callback)
  } catch (error) {
    const contextMsg = context ? ` in ${context}` : ''
    console.error(`❌ Error in safeFilter${contextMsg}:`, error)
    return [] // Return empty array instead of crashing
  }
}

/**
 * Safely extracts an array from a nested response structure
 * Handles various API response formats:
 * - Direct array: [item1, item2]
 * - Wrapped: { data: [item1, item2] }
 * - Nested: { data: { items: [item1, item2] } }
 * @param response - The API response object
 * @param paths - Array of possible paths to the data (e.g., ['data.items', 'data', 'items'])
 * @param context - Optional context for error logging
 * @returns Extracted array or empty array if not found
 */
export function safeExtractArray(
  response: any,
  paths: string[] = ['data', 'items', 'results', 'prospects', 'jobs'],
  context?: string
): any[] {
  // If response is already an array, return it
  if (isSafeArray(response)) {
    return response
  }

  // If response is null/undefined, return empty array
  if (response === null || response === undefined) {
    const contextMsg = context ? ` in ${context}` : ''
    console.warn(`⚠️ safeExtractArray: Response is null/undefined${contextMsg}`)
    return []
  }

  // Try each path
  for (const path of paths) {
    try {
      const value = path.split('.').reduce((obj, key) => obj?.[key], response)
      if (isSafeArray(value)) {
        return value
      }
    } catch (error) {
      // Continue to next path
      continue
    }
  }

  // If no path worked, log and return empty array
  const contextMsg = context ? ` in ${context}` : ''
  console.warn(`⚠️ safeExtractArray: Could not extract array from response${contextMsg}. Response:`, response)
  return []
}

/**
 * Validates API response structure and logs clear errors
 * @param response - The API response to validate
 * @param expectedStructure - Description of expected structure (for logging)
 * @param context - Optional context for error logging
 * @returns true if response is valid, false otherwise
 */
export function validateApiResponse(
  response: any,
  expectedStructure: string = 'object',
  context?: string
): boolean {
  if (response === null || response === undefined) {
    const contextMsg = context ? ` in ${context}` : ''
    console.error(`❌ API Response is null/undefined${contextMsg}. Expected: ${expectedStructure}`)
    return false
  }

  if (typeof response !== 'object') {
    const contextMsg = context ? ` in ${context}` : ''
    console.error(`❌ API Response is not an object${contextMsg}. Got: ${typeof response}. Expected: ${expectedStructure}`)
    return false
  }

  return true
}

/**
 * Safely gets a property from an object with fallback
 * @param obj - The object to get property from
 * @param path - Dot-separated path to the property (e.g., 'data.items')
 * @param fallback - Fallback value if property doesn't exist
 * @returns The property value or fallback
 */
export function safeGet<T>(
  obj: any,
  path: string,
  fallback: T
): T {
  try {
    const value = path.split('.').reduce((current, key) => current?.[key], obj)
    return value !== undefined && value !== null ? value : fallback
  } catch (error) {
    return fallback
  }
}

