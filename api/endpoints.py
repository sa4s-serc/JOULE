
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, Depends
from api.models import OptimizationRequest, TaskStatus
from api.manager import ConnectionManager, OptimizationTaskManager

router = APIRouter()

# Global managers (dependency injection pattern would be better but keeping it simple)
connection_manager = ConnectionManager()
task_manager = OptimizationTaskManager(connection_manager)

@router.post("/optimize", response_model=TaskStatus)
async def start_optimization(request: OptimizationRequest):
    """Start a new optimization task."""
    task_id = await task_manager.start_task(
        request.target_code,
        request.test_code,
        request.config or {}
    )
    return task_manager.get_task(task_id)

@router.get("/tasks/{task_id}", response_model=TaskStatus)
async def get_task_status(task_id: str):
    """Get the status of a task."""
    task = task_manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task

@router.websocket("/ws/{task_id}")
async def websocket_endpoint(websocket: WebSocket, task_id: str):
    """WebSocket endpoint for real-time updates."""
    await connection_manager.connect(websocket, task_id)
    try:
        while True:
            # We don't expect messages from client, just keep connection open
            # But we need to await receive to keep the loop running
            await websocket.receive_text()
    except WebSocketDisconnect:
        connection_manager.disconnect(websocket, task_id)
