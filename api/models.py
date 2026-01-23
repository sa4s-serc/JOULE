
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from datetime import datetime

class OptimizationRequest(BaseModel):
    """Request model for starting an optimization."""
    target_code: str
    test_code: str
    config: Optional[Dict[str, Any]] = None

class TaskStatus(BaseModel):
    """Status of an optimization task."""
    task_id: str
    status: str  # 'running', 'completed', 'failed'
    current_generation: int
    total_generations: int
    best_metrics: Optional[Dict[str, float]] = None
    best_code: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None

class WebSocketMessage(BaseModel):
    """Structure for WebSocket messages."""
    type: str  # 'log', 'metric', 'status', 'error'
    payload: Dict[str, Any]
    timestamp: float
