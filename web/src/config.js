// Configuration for the HEDGE web interface
export const config = {
  // API Configuration - try both legacy and v1 endpoints
  API_BASE_URL: import.meta.env.VITE_API_URL || 'http://localhost:8000',
  WS_BASE_URL: import.meta.env.VITE_WS_URL || 'ws://localhost:8000',
  
  // API Endpoints (with fallback support)
  ENDPOINTS: {
    OPTIMIZE: '/optimize',
    OPTIMIZE_V1: '/api/v1/optimize',
    WEBSOCKET: '/ws',
    WEBSOCKET_V1: '/api/v1/ws',
    HEALTH: '/health',
    TASKS: '/tasks',
    TASKS_V1: '/api/v1/tasks'
  },
  
  // WebSocket Configuration
  WS_RECONNECT_INTERVAL: 3000, // 3 seconds
  WS_MAX_RECONNECT_ATTEMPTS: 5,
  WS_RECONNECT_BACKOFF: 1.5, // Exponential backoff multiplier
  
  // UI Configuration
  LOG_MAX_ENTRIES: 1000,
  CHART_UPDATE_INTERVAL: 500, // ms
  
  // Default optimization settings
  DEFAULT_OPTIMIZATION: {
    generations: 10,
    population_size: 10,
    level: 'standard',
    llm: {
      provider: 'gemini',
      model: 'gemini-2.5-flash'
    },
    mutators: {
      layers: ['micro', 'algorithmic', 'syntactic', 'semantic']
    }
  }
};

export default config;