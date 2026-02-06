from datetime import datetime, timedelta
import asyncio
import threading
import uuid
import logging
import time
import json
from typing import Dict, List, Optional
from fastapi import WebSocket

from src.application.engine.evolution import EvolutionaryEngine, OptimizationEvent, EngineConfig
from src.infrastructure.execution.runner import GreenGymRunner
from cli.utils.mutator_factory import create_mutators
from src.application.mutators.base import MutationLayer
from api.models import TaskStatus, OptimizationRequest, SolutionResponse
from api.utils import sanitize_for_json

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Thread-safe WebSocket connection manager."""

    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}
        self._lock = threading.Lock()

    async def connect(self, websocket: WebSocket, task_id: str):
        await websocket.accept()
        with self._lock:
            if task_id not in self.active_connections:
                self.active_connections[task_id] = []
            self.active_connections[task_id].append(websocket)
        logger.info(f"WebSocket connected for task {task_id}")

    def disconnect(self, websocket: WebSocket, task_id: str):
        with self._lock:
            if task_id in self.active_connections:
                if websocket in self.active_connections[task_id]:
                    self.active_connections[task_id].remove(websocket)
                # Clean up empty task connections
                if not self.active_connections[task_id]:
                    del self.active_connections[task_id]
        logger.info(f"WebSocket disconnected for task {task_id}")

    async def broadcast(self, message: dict, task_id: str):
        with self._lock:
            connections = self.active_connections.get(task_id, []).copy()
        
        if not connections:
            return
            
        # Send to all connections, remove failed ones
        failed_connections = []
        for connection in connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"Failed to send message to {task_id}: {e}")
                failed_connections.append(connection)
        
        # Clean up failed connections
        if failed_connections:
            with self._lock:
                if task_id in self.active_connections:
                    for failed_conn in failed_connections:
                        if failed_conn in self.active_connections[task_id]:
                            self.active_connections[task_id].remove(failed_conn)

    def get_connection_count(self, task_id: str) -> int:
        with self._lock:
            return len(self.active_connections.get(task_id, []))


class OptimizationTaskManager:
    """Thread-safe optimization task manager."""

    def __init__(self, connection_manager: ConnectionManager):
        self.tasks: Dict[str, TaskStatus] = {}
        self.connection_manager = connection_manager
        self.threads: Dict[str, threading.Thread] = {}
        self.stop_events: Dict[str, threading.Event] = {}
        self.archive_solutions: Dict[str, Dict[str, SolutionResponse]] = {}
        self._lock = threading.Lock()
        
        # Capture the loop running the API
        try:
            self.loop = asyncio.get_running_loop()
        except RuntimeError:
            self.loop = asyncio.new_event_loop()

    async def start_task(self, request: OptimizationRequest) -> str:
        # Ensure we have the current loop if it wasn't available at init
        try:
            self.loop = asyncio.get_running_loop()
        except RuntimeError:
            pass

        task_id = str(uuid.uuid4())
        
        # Initialize archive for this task
        with self._lock:
            self.archive_solutions[task_id] = {}
            
            self.tasks[task_id] = TaskStatus(
                task_id=task_id,
                status="running",
                current_generation=0,
                total_generations=request.generations,
                start_time=datetime.now()
            )

            stop_event = threading.Event()
            self.stop_events[task_id] = stop_event

            thread = threading.Thread(
                target=self._run_optimization,
                args=(task_id, request, stop_event),
                daemon=True  # Daemon thread for cleanup
            )
            self.threads[task_id] = thread
            thread.start()

        logger.info(f"Started optimization task {task_id}")
        return task_id

    def get_task(self, task_id: str) -> Optional[TaskStatus]:
        with self._lock:
            return self.tasks.get(task_id)

    def get_solution(self, task_id: str, variant_id: str) -> Optional[SolutionResponse]:
        with self._lock:
            task_solutions = self.archive_solutions.get(task_id)
            if not task_solutions:
                return None
            return task_solutions.get(variant_id)

    def stop_task(self, task_id: str) -> bool:
        """Stop a running optimization task."""
        with self._lock:
            task = self.tasks.get(task_id)
            if not task:
                return False
            
            # Only stop if task is running
            if task.status != "running":
                return False
                
            if task_id in self.stop_events:
                self.stop_events[task_id].set()
                return True
            return False

    def cleanup_completed_tasks(self, max_age_hours: int = 24):
        """Clean up old completed tasks to prevent memory leaks."""
        cutoff_time = datetime.now() - timedelta(hours=max_age_hours)
        
        with self._lock:
            tasks_to_remove = []
            for task_id, task in self.tasks.items():
                if (task.status in ["completed", "failed", "stopped"] and 
                    task.end_time and task.end_time < cutoff_time):
                    tasks_to_remove.append(task_id)
            
            for task_id in tasks_to_remove:
                # Clean up all related data
                self.tasks.pop(task_id, None)
                self.archive_solutions.pop(task_id, None)
                self.stop_events.pop(task_id, None)
                
                # Clean up thread reference
                thread = self.threads.pop(task_id, None)
                if thread and thread.is_alive():
                    logger.warning(f"Thread for task {task_id} still alive during cleanup")
                
                logger.info(f"Cleaned up old task {task_id}")

    def _make_json_safe(self, obj, depth=0, max_depth=10):
        """
        Convert objects to JSON-safe format with recursion protection.
        
        This is a wrapper around the sanitize_for_json utility function
        for backward compatibility.
        """
        return sanitize_for_json(obj, depth, max_depth)

    def _run_optimization(self, task_id: str, request: OptimizationRequest, stop_event: threading.Event):
        """Run optimization in a separate thread."""
        try:
            # Event callback for real-time updates
            def event_callback(event: OptimizationEvent):
                if stop_event.is_set():
                    raise InterruptedError("Optimization stopped by user")

                # Update local task status
                with self._lock:
                    if task_id not in self.tasks:
                        return
                        
                    if event.type == "generation_complete":
                        self.tasks[task_id].current_generation = event.data.get("generation", 0) + 1
                        self.tasks[task_id].best_metrics = event.data.get("best_metrics", {})
                    elif event.type == "new_best_solution":
                        self.tasks[task_id].best_code = event.data.get("code")
                        self.tasks[task_id].best_metrics = {
                            "energy_joules": event.data.get("energy", 0.0),
                            "duration_seconds": event.data.get("time", 0.0)
                        }
                        # Store in archive as well for fetching
                        variant_id = event.data.get("variant_id", "best")
                        if task_id not in self.archive_solutions:
                            self.archive_solutions[task_id] = {}
                        self.archive_solutions[task_id][variant_id] = SolutionResponse(
                            variant_id=variant_id,
                            code=event.data.get("code", ""),
                            metrics=self.tasks[task_id].best_metrics
                        )
                    elif event.type == "pareto_update":
                        solutions = event.data.get("solutions", [])
                        if task_id not in self.archive_solutions:
                            self.archive_solutions[task_id] = {}
                        for sol in solutions:
                            variant_id = sol.get("variant_id")
                            code = sol.get("code")
                            energy = sol.get("energy")
                            duration = sol.get("time")
                            
                            if variant_id and code and energy is not None and duration is not None:
                                self.archive_solutions[task_id][variant_id] = SolutionResponse(
                                    variant_id=variant_id,
                                    code=code,
                                    metrics={
                                        "energy_joules": energy,
                                        "duration_seconds": duration
                                    }
                                )
                    elif event.type == "optimization_complete":
                        self.tasks[task_id].best_code = event.data.get("best_code")
                    
                    # Log mutation events with detailed info
                    if event.type in ["mutation_attempt", "mutation_result"]:
                        mutator = event.data.get("mutator", "Unknown")
                        strategy = event.data.get("strategy", "Unknown")

                # Broadcast via WebSocket safely
                try:
                    # CRITICAL FIX: Sanitize event data to prevent JSON serialization errors
                    # This handles IR objects like Constant that might leak into metrics/output
                    safe_payload = sanitize_for_json(event.data)
                    
                    # Verify the payload is actually JSON-serializable before sending
                    try:
                        json.dumps(safe_payload)  # Test serialization
                    except (TypeError, ValueError) as json_err:
                        logger.error(f"[WEBSOCKET_ERROR] Payload still not JSON-serializable after sanitization: {json_err}")
                        logger.error(f"[WEBSOCKET_ERROR] Event type: {event.type}, Payload keys: {safe_payload.keys() if isinstance(safe_payload, dict) else 'not a dict'}")
                        # Create a minimal safe payload
                        safe_payload = {
                            "error": "Payload serialization failed",
                            "event_type": str(event.type),
                            "original_keys": list(safe_payload.keys()) if isinstance(safe_payload, dict) else []
                        }
                    
                    asyncio.run_coroutine_threadsafe(
                        self.connection_manager.broadcast({
                            "type": event.type,
                            "payload": safe_payload,
                            "timestamp": time.time()
                        }, task_id),
                        self.loop
                    )
                except Exception as e:
                    logger.error(f"Failed to broadcast event {event.type}: {e}", exc_info=True)
                    # Try to send a minimal error message
                    try:
                        asyncio.run_coroutine_threadsafe(
                            self.connection_manager.broadcast({
                                "type": "error",
                                "payload": {"message": f"Event broadcast failed: {str(e)}"},
                                "timestamp": time.time()
                            }, task_id),
                            self.loop
                        )
                    except Exception as fallback_err:
                        logger.error(f"Failed to send fallback error message: {fallback_err}")

            # Run the actual optimization
            self._execute_optimization(task_id, request, event_callback)
            
            with self._lock:
                if task_id in self.tasks:
                    self.tasks[task_id].status = "completed"
                    self.tasks[task_id].end_time = datetime.now()

            # Broadcast completion
            asyncio.run_coroutine_threadsafe(
                self.connection_manager.broadcast({
                    "type": "optimization_complete",
                    "payload": {},
                    "timestamp": time.time()
                }, task_id),
                self.loop
            )

        except InterruptedError:
            with self._lock:
                if task_id in self.tasks:
                    self.tasks[task_id].status = "stopped"
                    self.tasks[task_id].end_time = datetime.now()
        except Exception as e:
            logger.error(f"Task {task_id} failed: {e}")
            with self._lock:
                if task_id in self.tasks:
                    self.tasks[task_id].status = "failed"
                    self.tasks[task_id].end_time = datetime.now()
            
            # Broadcast error
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

    def _execute_optimization(self, task_id: str, request: OptimizationRequest, event_callback):
        """Execute the optimization with proper configuration."""
        # Extract configuration
        llm_provider = request.llm.provider if request.llm else None
        llm_model = request.llm.model if request.llm else None

        layers = None
        if request.mutators and request.mutators.layers:
            layers = ",".join(request.mutators.layers)

        exclude_mutators = None
        if request.mutators and request.mutators.disabled_mutators:
            exclude_mutators = ",".join(request.mutators.disabled_mutators)

        # Initialize Engine
        mutators, enabled_layers_set, llm_client = create_mutators(
            level=request.level,
            layers=layers,
            llm_provider=llm_provider,
            llm_model=llm_model,
            exclude_mutators=exclude_mutators,
            allowed_imports=set(request.allowed_imports)
        )

        timeout = 30
        if request.engine:
            timeout = request.engine.timeout

        runner = GreenGymRunner(timeout_seconds=timeout)

        # Configure EngineConfig
        engine_config = EngineConfig(
            generations=request.generations,
            population_size=request.population_size,
            allowed_imports=request.allowed_imports,
        )

        if request.engine:
            engine_config.elite_size = request.engine.elite_size
            # Note: mutation_rate is defined in the model but not used by EngineConfig
            # This is a design limitation of the current EngineConfig class

        engine = EvolutionaryEngine(
            mutators=mutators,
            runner=runner,
            event_callback=event_callback,
            llm_client=llm_client,
            config=engine_config
        )

        # Run optimization
        logger.info(f"Starting optimization for task {task_id}")
        logger.info(f"Target code length: {len(request.target_code)}")
        logger.info(f"Test code length: {len(request.test_code)}")
        logger.info(f"Enabled layers: {enabled_layers_set}")
        logger.info(f"Number of mutators: {len(mutators)}")
        
        try:
            engine.optimize(request.target_code, request.test_code,
                            enabled_layers=enabled_layers_set)
            logger.info(f"Optimization completed successfully for task {task_id}")
        except Exception as e:
            logger.error(f"Optimization failed for task {task_id}: {e}")
            raise

        return engine