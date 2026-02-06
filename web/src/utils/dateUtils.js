/**
 * Date utility functions with error handling
 */

/**
 * Safely format a date to locale time string
 * @param {Date|string|number} date - Date to format
 * @returns {string} Formatted time string or fallback
 */
export const safeToLocaleTimeString = (date) => {
  try {
    if (!date) {
      return new Date().toLocaleTimeString();
    }
    
    if (date instanceof Date) {
      return date.toLocaleTimeString();
    }
    
    if (typeof date === 'string' || typeof date === 'number') {
      return new Date(date).toLocaleTimeString();
    }
    
    // Fallback for invalid input
    return new Date().toLocaleTimeString();
  } catch (error) {
    console.warn('Error formatting date:', error);
    // Return a simple timestamp format as fallback
    const now = new Date();
    return `${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}:${now.getSeconds().toString().padStart(2, '0')}`;
  }
};

/**
 * Get current timestamp in a safe way
 * @returns {string} Current time as string
 */
export const getCurrentTimeString = () => {
  return safeToLocaleTimeString(new Date());
};

/**
 * Format duration in a human-readable way
 * @param {number} seconds - Duration in seconds
 * @returns {string} Formatted duration
 */
export const formatDuration = (seconds) => {
  if (!seconds || isNaN(seconds)) {
    return '0s';
  }
  
  if (seconds < 60) {
    return `${seconds.toFixed(1)}s`;
  }
  
  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = seconds % 60;
  
  if (minutes < 60) {
    return `${minutes}m ${remainingSeconds.toFixed(0)}s`;
  }
  
  const hours = Math.floor(minutes / 60);
  const remainingMinutes = minutes % 60;
  
  return `${hours}h ${remainingMinutes}m`;
};