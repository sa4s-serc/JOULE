
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, BackgroundTasks
from api.models import OptimizationRequest, TaskStatus, SolutionResponse
from api.manager import ConnectionManager, OptimizationTaskManager
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

# Global managers (dependency injection pattern would be better but keeping it simple)
connection_manager = ConnectionManager()
task_manager = OptimizationTaskManager(connection_manager)


@router.post("/optimize", response_model=TaskStatus)
async def start_optimization(request: OptimizationRequest, background_tasks: BackgroundTasks):
    """Start a new optimization task."""
    try:
        # Validate that code is not empty
        if not request.target_code or not request.target_code.strip():
            raise HTTPException(status_code=400, detail="Target code cannot be empty")
        
        if not request.test_code or not request.test_code.strip():
            raise HTTPException(status_code=400, detail="Test code cannot be empty")
        
        task_id = await task_manager.start_task(request)
        # Schedule cleanup of old tasks
        background_tasks.add_task(task_manager.cleanup_completed_tasks)
        return task_manager.get_task(task_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to start optimization: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to start optimization: {str(e)}")


@router.get("/tasks/{task_id}", response_model=TaskStatus)
async def get_task_status(task_id: str):
    """Get the status of a task."""
    task = task_manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.delete("/tasks/{task_id}")
async def stop_task(task_id: str):
    """Stop a running optimization task."""
    success = task_manager.stop_task(task_id)
    if not success:
        raise HTTPException(status_code=404, detail="Task not found or already completed")
    return {"message": "Task stopped successfully"}


@router.get("/tasks/{task_id}/solutions/{variant_id}", response_model=SolutionResponse)
async def get_solution(task_id: str, variant_id: str):
    """Get a specific solution from a task."""
    task = task_manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    solution = task_manager.get_solution(task_id, variant_id)
    if not solution:
        raise HTTPException(status_code=404, detail="Solution not found")
    return solution


@router.get("/tasks")
async def list_tasks():
    """List all tasks with their current status."""
    try:
        with task_manager._lock:
            tasks = [task.dict() for task in task_manager.tasks.values()]
        return {"tasks": tasks, "count": len(tasks)}
    except Exception as e:
        logger.error(f"Failed to list tasks: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list tasks: {str(e)}")


@router.websocket("/ws/{task_id}")
async def websocket_endpoint(websocket: WebSocket, task_id: str):
    """WebSocket endpoint for real-time updates."""
    # Verify task exists before accepting connection
    task = task_manager.get_task(task_id)
    if not task:
        await websocket.close(code=1008, reason="Task not found")
        return
    
    await connection_manager.connect(websocket, task_id)
    try:
        while True:
            # Keep connection alive and handle any client messages
            try:
                message = await websocket.receive_text()
                # Handle client messages if needed (e.g., pause/resume commands)
            except Exception:
                break
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for task {task_id}")
    except Exception as e:
        logger.error(f"WebSocket error for task {task_id}: {e}")
    finally:
        connection_manager.disconnect(websocket, task_id)
