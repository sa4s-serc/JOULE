import axios from 'axios';
import { config } from '../config';

/**
 * API utility with automatic fallback between v1 and legacy endpoints
 */

class APIClient {
  constructor() {
    this.baseURL = config.API_BASE_URL;
    this.client = axios.create({
      baseURL: this.baseURL,
      timeout: 30000, // 30 second timeout
    });
    
    // Add request interceptor for logging
    this.client.interceptors.request.use(
      (config) => {
        console.log(`🔄 API Request: ${config.method?.toUpperCase()} ${config.url}`);
        return config;
      },
      (error) => {
        console.error('🔥 API Request Error:', error);
        return Promise.reject(error);
      }
    );
    
    // Add response interceptor for logging
    this.client.interceptors.response.use(
      (response) => {
        console.log(`✅ API Response: ${response.status} ${response.config.url}`);
        return response;
      },
      (error) => {
        console.error(`❌ API Error: ${error.response?.status || 'Network'} ${error.config?.url}`, error.response?.data);
        return Promise.reject(error);
      }
    );
  }

  /**
   * Make API request with automatic fallback
   */
  async request(method, endpoint, data = null, options = {}) {
    const endpoints = Array.isArray(endpoint) ? endpoint : [endpoint];
    
    for (let i = 0; i < endpoints.length; i++) {
      const currentEndpoint = endpoints[i];
      
      try {
        const requestConfig = {
          method,
          url: currentEndpoint,
          ...options
        };
        
        if (data) {
          if (method.toLowerCase() === 'get') {
            requestConfig.params = data;
          } else {
            requestConfig.data = data;
          }
        }
        
        const response = await this.client.request(requestConfig);
        return response;
        
      } catch (error) {
        console.warn(`⚠️ Endpoint ${currentEndpoint} failed:`, error.message);
        
        // If this is the last endpoint, throw the error
        if (i === endpoints.length - 1) {
          throw error;
        }
        
        // Otherwise, try the next endpoint
        console.log(`🔄 Trying fallback endpoint...`);
      }
    }
  }

  /**
   * Start optimization with fallback
   */
  async startOptimization(payload) {
    return this.request('POST', [
      config.ENDPOINTS.OPTIMIZE_V1,  // Try v1 first
      config.ENDPOINTS.OPTIMIZE      // Fallback to legacy
    ], payload);
  }

  /**
   * Get task status with fallback
   */
  async getTaskStatus(taskId) {
    return this.request('GET', [
      `${config.ENDPOINTS.TASKS_V1}/${taskId}`,
      `${config.ENDPOINTS.TASKS}/${taskId}`
    ]);
  }

  /**
   * Health check
   */
  async healthCheck() {
    return this.request('GET', config.ENDPOINTS.HEALTH);
  }

  /**
   * Test API connectivity
   */
  async testConnection() {
    try {
      await this.healthCheck();
      return { connected: true, message: 'API server is reachable' };
    } catch (error) {
      return { 
        connected: false, 
        message: `API server unreachable: ${error.message}`,
        suggestion: 'Make sure the API server is running on http://localhost:8000'
      };
    }
  }
}

// Create singleton instance
export const apiClient = new APIClient();

// Export convenience methods
export const startOptimization = (payload) => apiClient.startOptimization(payload);
export const getTaskStatus = (taskId) => apiClient.getTaskStatus(taskId);
export const testConnection = () => apiClient.testConnection();

export default apiClient;