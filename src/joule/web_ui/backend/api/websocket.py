from __future__ import annotations

from typing import List, Dict, Any
from fastapi import WebSocket, WebSocketDisconnect
import json
import asyncio
import logging

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages WebSocket connections for real-time updates."""
    
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.run_subscribers: Dict[str, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket):
        """Accept and register a WebSocket connection."""
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket connected. Total connections: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        """Unregister a WebSocket connection."""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        
        # Remove from run subscriptions
        for run_id, subscribers in self.run_subscribers.items():
            if websocket in subscribers:
                subscribers.remove(websocket)
                if not subscribers:
                    del self.run_subscribers[run_id]
        
        logger.info(f"WebSocket disconnected. Total connections: {len(self.active_connections)}")

    async def send_personal_message(self, message: Dict[str, Any], websocket: WebSocket):
        """Send a message to a specific WebSocket."""
        try:
            await websocket.send_text(json.dumps(message))
        except Exception as e:
            logger.error(f"Failed to send personal message: {e}")
            self.disconnect(websocket)

    async def broadcast(self, message: Dict[str, Any]):
        """Broadcast a message to all connected WebSockets."""
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_text(json.dumps(message))
            except Exception as e:
                logger.error(f"Failed to broadcast message: {e}")
                disconnected.append(connection)
        
        # Clean up disconnected connections
        for connection in disconnected:
            self.disconnect(connection)

    async def send_run_update(self, run_id: str, message: Dict[str, Any]):
        """Send a message to all subscribers of a specific run."""
        if run_id not in self.run_subscribers:
            return
        
        disconnected = []
        for connection in self.run_subscribers[run_id]:
            try:
                await connection.send_text(json.dumps({
                    "type": "run_update",
                    "run_id": run_id,
                    "data": message
                }))
            except Exception as e:
                logger.error(f"Failed to send run update: {e}")
                disconnected.append(connection)
        
        # Clean up disconnected connections
        for connection in disconnected:
            self.disconnect(connection)

    def subscribe_to_run(self, run_id: str, websocket: WebSocket):
        """Subscribe a WebSocket to updates for a specific run."""
        if run_id not in self.run_subscribers:
            self.run_subscribers[run_id] = []
        self.run_subscribers[run_id].append(websocket)

    def unsubscribe_from_run(self, run_id: str, websocket: WebSocket):
        """Unsubscribe a WebSocket from updates for a specific run."""
        if run_id in self.run_subscribers and websocket in self.run_subscribers[run_id]:
            self.run_subscribers[run_id].remove(websocket)
            if not self.run_subscribers[run_id]:
                del self.run_subscribers[run_id]


# Global connection manager
manager = ConnectionManager()


async def handle_websocket_connection(websocket: WebSocket):
    """Handle incoming WebSocket connections."""
    await manager.connect(websocket)
    
    try:
        while True:
            # Receive message from client
            data = await websocket.receive_text()
            message = json.loads(data)
            
            # Handle different message types
            message_type = message.get("type")
            
            if message_type == "subscribe_run":
                run_id = message.get("run_id")
                if run_id:
                    manager.subscribe_to_run(run_id, websocket)
                    await manager.send_personal_message({
                        "type": "subscription_confirmed",
                        "run_id": run_id
                    }, websocket)
            
            elif message_type == "unsubscribe_run":
                run_id = message.get("run_id")
                if run_id:
                    manager.unsubscribe_from_run(run_id, websocket)
                    await manager.send_personal_message({
                        "type": "unsubscription_confirmed", 
                        "run_id": run_id
                    }, websocket)
            
            elif message_type == "ping":
                await manager.send_personal_message({
                    "type": "pong",
                    "timestamp": message.get("timestamp")
                }, websocket)
            
            else:
                # Echo unknown messages
                await manager.send_personal_message({
                    "type": "echo",
                    "original": message
                }, websocket)
                
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(websocket)


# Helper functions for sending run updates
async def send_run_status_update(run_id: str, status: str, progress: float = None):
    """Send a run status update."""
    message = {
        "type": "status_update",
        "status": status,
        "timestamp": asyncio.get_event_loop().time()
    }
    if progress is not None:
        message["progress"] = progress
    
    await manager.send_run_update(run_id, message)


async def send_candidate_update(run_id: str, candidate: Dict[str, Any]):
    """Send a candidate update."""
    message = {
        "type": "candidate_update",
        "candidate": candidate,
        "timestamp": asyncio.get_event_loop().time()
    }
    await manager.send_run_update(run_id, message)


async def send_error_update(run_id: str, error: str):
    """Send an error update."""
    message = {
        "type": "error",
        "error": error,
        "timestamp": asyncio.get_event_loop().time()
    }
    await manager.send_run_update(run_id, message)


async def send_log_message(run_id: str, level: str, message: str):
    """Send a log message."""
    log_message = {
        "type": "log",
        "level": level,
        "message": message,
        "timestamp": asyncio.get_event_loop().time()
    }
    await manager.send_run_update(run_id, log_message)
