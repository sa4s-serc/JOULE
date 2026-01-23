
import asyncio
import threading
import uuid
import logging
import time
from typing import Dict, List, Optional
from fastapi import WebSocket

from src.application.engine.evolution import EvolutionaryEngine, OptimizationEvent
from src.infrastructure.execution.runner import GreenGymRunner
from cli.utils.mutator_factory import create_mutators
from api.models import TaskStatus

logger = logging.getLogger(__name__)

class ConnectionManager:
    """Manages WebSocket connections."""
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, task_id: str):
        await websocket.accept()
        if task_id not in self.active_connections:
            self.active_connections[task_id] = []
        self.active_connections[task_id].append(websocket)

    def disconnect(self, websocket: WebSocket, task_id: str):
        if task_id in self.active_connections:
            if websocket in self.active_connections[task_id]:
                self.active_connections[task_id].remove(websocket)

    async def broadcast(self, message: dict, task_id: str):
        if task_id in self.active_connections:
            for connection in self.active_connections[task_id]:
                try:
                    await connection.send_json(message)
                except Exception as e:
                    logger.error(f"Failed to send message to {task_id}: {e}")

class OptimizationTaskManager:
    """Manages optimization tasks in background threads."""
    
    def __init__(self, connection_manager: ConnectionManager):
        self.tasks: Dict[str, TaskStatus] = {}
        self.connection_manager = connection_manager
        self.threads: Dict[str, threading.Thread] = {}
        self.stop_events: Dict[str, threading.Event] = {}
        # Capture the loop running the API
        try:
             self.loop = asyncio.get_running_loop()
        except RuntimeError:
             self.loop = asyncio.new_event_loop()

    async def start_task(self, target_code: str, test_code: str, config: dict) -> str:
        # Ensure we have the current loop if it wasn't available at init
        try:
             self.loop = asyncio.get_running_loop()
        except RuntimeError:
             pass
             
        task_id = str(uuid.uuid4())
        
        self.tasks[task_id] = TaskStatus(
            task_id=task_id,
            status="running",
            current_generation=0,
            total_generations=config.get("generations", 10),
            start_time=datetime.now()
        )
        
        stop_event = threading.Event()
        self.stop_events[task_id] = stop_event
        
        thread = threading.Thread(
            target=self._run_optimization,
            args=(task_id, target_code, test_code, config, stop_event)
        )
        self.threads[task_id] = thread
        thread.start()
        
        return task_id

    def _run_optimization(self, task_id: str, target_code: str, test_code: str, config: dict, stop_event: threading.Event):
        """Run optimization in a separate thread."""
        try:
            # Event callback for real-time updates
            def event_callback(event: OptimizationEvent):
                if stop_event.is_set():
                    raise InterruptedError("Optimization stopped by user")
                
                # Update local task status
                if event.type == "generation_complete":
                    self.tasks[task_id].current_generation = event.data.get("generation", 0)
                    self.tasks[task_id].best_metrics = event.data.get("best_metrics", {})
                elif event.type == "new_best_solution":
                    self.tasks[task_id].best_code = event.data.get("code")
                    self.tasks[task_id].best_metrics = {
                        "energy_joules": event.data.get("energy"),
                        "duration_seconds": event.data.get("time")
                    }
                elif event.type == "optimization_complete":
                     self.tasks[task_id].best_code = event.data.get("best_code")
                
                # Broadcast via WebSocket safely
                try:
                    asyncio.run_coroutine_threadsafe(
                        self.connection_manager.broadcast({
                            "type": event.type.value,
                            "payload": event.data,
                            "timestamp": event.timestamp
                        }, task_id),
                        self.loop
                    )
                except Exception as e:
                    logger.error(f"Failed to broadcast event: {e}")

            # Initialize Engine
            mutators, _ = create_mutators(
                level=config.get("level", "standard"),
                llm_provider=config.get("llm_provider"),
                llm_model=config.get("llm_model")
            )
            
            runner = GreenGymRunner(timeout_seconds=config.get("timeout", 30))
            
            # TODO: Configure EngineConfig properly based on request config
            # engine_config = EngineConfig(...) 
            
            engine = EvolutionaryEngine(
                mutators=mutators,
                runner=runner,
                event_callback=event_callback
                # config=engine_config
            )
            
            # Run optimization
            engine.optimize(target_code, test_code)
            
            self.tasks[task_id].status = "completed"
            self.tasks[task_id].end_time = datetime.now()
            
            # Broadcast validation completion
            asyncio.run_coroutine_threadsafe(
                self.connection_manager.broadcast({
                    "type": "optimization_complete",
                    "payload": {},
                    "timestamp": time.time()
                }, task_id),
                self.loop
            )
            
        except InterruptedError:
            self.tasks[task_id].status = "stopped"
        except Exception as e:
            logger.error(f"Task {task_id} failed: {e}")
            self.tasks[task_id].status = "failed"
            # async broadcast error
            try:
                asyncio.run_coroutine_threadsafe(
                    self.connection_manager.broadcast({
                        "type": "error",
                        "payload": {"message": str(e)},
                        "timestamp": time.time()
                    }, task_id),
                    self.loop
                )
            except Exception as loop_e:
                logger.error(f"Failed to broadcast error: {loop_e}")

    def get_task(self, task_id: str) -> Optional[TaskStatus]:
        return self.tasks.get(task_id)

from datetime import datetime
