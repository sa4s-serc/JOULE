import { useEffect, useRef, useState, useCallback } from 'react';
import { config } from '../config';

/**
 * Custom hook for managing WebSocket connections with automatic reconnection
 */
export const useWebSocket = (taskId, onMessage, onError) => {
  const wsRef = useRef(null);
  const reconnectTimeoutRef = useRef(null);
  const reconnectAttemptsRef = useRef(0);
  const [isConnected, setIsConnected] = useState(false);
  const [connectionStatus, setConnectionStatus] = useState('disconnected');

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      return;
    }

    try {
      const wsUrl = `${config.WS_BASE_URL}${config.ENDPOINTS.WEBSOCKET}/${taskId}`;
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      setConnectionStatus('connecting');

      ws.onopen = () => {
        setIsConnected(true);
        setConnectionStatus('connected');
        reconnectAttemptsRef.current = 0;
        onMessage?.({
          type: 'system',
          payload: { message: 'Connected to live stream', level: 'success' }
        });
      };

      ws.onclose = (event) => {
        setIsConnected(false);
        setConnectionStatus('disconnected');
        
        if (!event.wasClean && reconnectAttemptsRef.current < config.WS_MAX_RECONNECT_ATTEMPTS) {
          const delay = config.WS_RECONNECT_INTERVAL * Math.pow(config.WS_RECONNECT_BACKOFF, reconnectAttemptsRef.current);
          reconnectAttemptsRef.current++;
          
          setConnectionStatus('reconnecting');
          onMessage?.({
            type: 'system',
            payload: { 
              message: `Connection lost. Reconnecting in ${Math.round(delay/1000)}s... (${reconnectAttemptsRef.current}/${config.WS_MAX_RECONNECT_ATTEMPTS})`,
              level: 'warning'
            }
          });

          reconnectTimeoutRef.current = setTimeout(() => {
            connect();
          }, delay);
        } else if (reconnectAttemptsRef.current >= config.WS_MAX_RECONNECT_ATTEMPTS) {
          onError?.('Failed to reconnect after maximum attempts');
          onMessage?.({
            type: 'system',
            payload: { message: 'Connection failed after maximum retry attempts', level: 'error' }
          });
        }
      };

      ws.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data);
          onMessage?.(message);
        } catch (err) {
          console.error('Failed to parse WebSocket message:', err);
          onError?.('Invalid message format received');
        }
      };

      ws.onerror = (err) => {
        console.error('WebSocket error:', err);
        setConnectionStatus('error');
        onError?.('WebSocket connection error');
      };

    } catch (err) {
      console.error('Failed to create WebSocket connection:', err);
      onError?.('Failed to establish connection');
    }
  }, [taskId, onMessage, onError]);

  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
    
    if (wsRef.current) {
      wsRef.current.close(1000, 'User disconnected');
      wsRef.current = null;
    }
    
    setIsConnected(false);
    setConnectionStatus('disconnected');
    reconnectAttemptsRef.current = 0;
  }, []);

  const sendMessage = useCallback((message) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(message));
      return true;
    }
    return false;
  }, []);

  useEffect(() => {
    if (taskId) {
      connect();
    }

    return () => {
      disconnect();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [taskId]);

  return {
    isConnected,
    connectionStatus,
    sendMessage,
    reconnect: connect,
    disconnect
  };
};