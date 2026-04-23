from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import List, Optional, Dict, Any

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import json
import asyncio

from joule.config import load_settings
from joule.utils.db import JouleDB


# Pydantic models for API
class ProjectInfo(BaseModel):
    path: str
    name: str
    config: Optional[Dict[str, Any]] = None
    health: Optional[Dict[str, Any]] = None


class TargetSpec(BaseModel):
    qualname: str
    file_path: str
    line_number: int
    function_type: str


class WorkloadSpec(BaseModel):
    id: str
    kind: str
    description: str
    file_path: Optional[str] = None
    node_id: Optional[str] = None


class BaselineConfig(BaseModel):
    target: str
    workloads: List[str]
    backend: str
    repetitions: int
    hotspots: bool
    hotspot_limit: int
    cache: bool


class OptimizationConfig(BaseModel):
    target: str
    workloads: List[str]
    backend: str
    budget: int
    analysis: bool
    cache: bool
    fresh_surrogate: bool
    parallel: int
    improvement_threshold: float


class ApplyConfig(BaseModel):
    run_id: str
    candidate_id: Optional[str] = None
    branch: bool = False
    commit_changes: bool = False


# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def send_personal_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            await connection.send_text(message)


manager = ConnectionManager()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("JOULE Web UI backend starting up...")
    yield
    # Shutdown
    print("JOULE Web UI backend shutting down...")


app = FastAPI(
    title="JOULE Web UI API",
    description="Web API for JOULE optimization toolkit",
    version="0.1.0",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Helper functions
def get_project_info(project_path: str) -> ProjectInfo:
    """Get project information including health check."""
    try:
        path = Path(project_path)
        settings = load_settings(path)
        
        # Run health check
        health_issues = []
        try:
            db = JouleDB(settings.db_path)
            db_accessible = True
        except Exception as e:
            health_issues.append(f"Database inaccessible: {e}")
            db_accessible = False
        
        artifact_dir_exists = path / settings.artifact_dir / "runs"
        
        return ProjectInfo(
            path=str(path),
            name=path.name,
            config=settings.__dict__,
            health={
                "backend_available": True,  # TODO: Implement backend check
                "dependencies_ok": True,    # TODO: Implement dependency check
                "artifact_dir_exists": artifact_dir_exists.exists(),
                "db_accessible": db_accessible,
                "issues": health_issues,
            }
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to load project: {e}")


# API Routes
@app.get("/")
async def root():
    return {"message": "JOULE Web UI API", "version": "0.1.0"}


@app.get("/api/projects", response_model=List[ProjectInfo])
async def list_projects():
    """List available projects."""
    # TODO: Implement project discovery
    # For now, return current directory as example
    try:
        current_project = get_project_info(".")
        return [current_project]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/projects/{project_path:path}", response_model=ProjectInfo)
async def get_project(project_path: str):
    """Get specific project information."""
    try:
        return get_project_info(project_path)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/projects/{project_path:path}/doctor")
async def run_project_doctor(project_path: str):
    """Run doctor command on project."""
    try:
        # TODO: Implement doctor command integration
        return {
            "status": "success",
            "checks": {
                "backend": "ok",
                "dependencies": "ok",
                "artifacts": "ok",
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/projects/{project_path:path}/discover/targets", response_model=List[TargetSpec])
async def discover_targets(project_path: str):
    """Discover optimization targets in project."""
    try:
        # TODO: Implement target discovery
        mock_targets = [
            TargetSpec(
                qualname="example.process_data",
                file_path="example/main.py",
                line_number=42,
                function_type="function"
            ),
            TargetSpec(
                qualname="ExampleClass.analyze",
                file_path="example/models.py",
                line_number=15,
                function_type="method"
            ),
        ]
        return mock_targets
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/projects/{project_path:path}/discover/workloads/{target_qualname}", response_model=List[WorkloadSpec])
async def discover_workloads(project_path: str, target_qualname: str):
    """Discover workloads for a specific target."""
    try:
        # TODO: Implement workload discovery
        mock_workloads = [
            WorkloadSpec(
                id="test_process_data",
                kind="test",
                description="Test the process_data function",
                file_path="tests/test_main.py",
                node_id="test_process_data"
            ),
            WorkloadSpec(
                id="property_data_integrity",
                kind="property",
                description="Data integrity property",
                file_path="tests/properties.py",
                node_id="test_data_integrity"
            ),
        ]
        return mock_workloads
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/projects/{project_path:path}/baseline")
async def run_baseline(project_path: str, config: BaselineConfig):
    """Run baseline measurement."""
    try:
        # TODO: Implement baseline execution
        run_id = f"baseline_{project_path.replace('/', '_')}_{asyncio.get_event_loop().time()}"
        
        # Start baseline in background
        # For now, return mock response
        return {
            "run_id": run_id,
            "status": "started",
            "config": config.dict()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/projects/{project_path:path}/optimize")
async def run_optimization(project_path: str, config: OptimizationConfig):
    """Run optimization."""
    try:
        # TODO: Implement optimization execution
        run_id = f"optimize_{project_path.replace('/', '_')}_{asyncio.get_event_loop().time()}"
        
        return {
            "run_id": run_id,
            "status": "started",
            "config": config.dict()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/runs", response_model=List[Dict[str, Any]])
async def list_runs(project_path: str = "."):
    """List all runs for a project."""
    try:
        # TODO: Implement run listing from database
        mock_runs = [
            {
                "run_id": "run_20240423_001",
                "run_type": "optimize",
                "status": "completed",
                "target_qualname": "example.process_data",
                "backend": "mock",
                "created_at": "2024-04-23T10:30:00Z",
                "completed_at": "2024-04-23T10:45:00Z",
                "metadata": {
                    "total_candidates": 6,
                    "accepted_count": 2,
                    "best_improvement": 0.12,
                }
            },
        ]
        return mock_runs
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/runs/{run_id}", response_model=Dict[str, Any])
async def get_run(run_id: str, project_path: str = "."):
    """Get detailed run information."""
    try:
        # TODO: Implement run details from database
        return {
            "run_id": run_id,
            "run_type": "optimize",
            "status": "completed",
            "target_qualname": "example.process_data",
            "backend": "mock",
            "created_at": "2024-04-23T10:30:00Z",
            "completed_at": "2024-04-23T10:45:00Z",
            "baseline": {
                "energy_j": 125.5,
                "wall_time_s": 2.34,
                "cpu_time_s": 2.12,
                "peak_memory_bytes": 52428800,
            },
            "candidates": [
                {
                    "candidate_id": "candidate_001",
                    "operator_name": "loop_membership_set_cache",
                    "operator_tier": "tier_1",
                    "status": "accepted",
                    "improvements": {
                        "energy_ratio": 0.86,
                        "time_ratio": 0.86,
                        "memory_ratio": 0.94,
                    },
                    "explanation": "Optimized loop membership checks using set cache",
                }
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")


@app.post("/api/runs/{run_id}/apply")
async def apply_candidate(run_id: str, config: ApplyConfig, project_path: str = "."):
    """Apply a candidate from a run."""
    try:
        # TODO: Implement candidate application
        return {
            "status": "applied",
            "run_id": run_id,
            "candidate_id": config.candidate_id,
            "branch_created": config.branch,
            "commit_created": config.commit_changes,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/runs/{run_id}/artifacts/{artifact_name}")
async def get_artifact(run_id: str, artifact_name: str, project_path: str = "."):
    """Download run artifact."""
    try:
        # TODO: Implement artifact serving
        artifact_path = Path(project_path) / ".joule" / "runs" / run_id / artifact_name
        if not artifact_path.exists():
            raise HTTPException(status_code=404, detail=f"Artifact {artifact_name} not found")
        
        # Return file content
        return {"message": f"Serve artifact {artifact_name}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# WebSocket endpoint for real-time updates
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            # Echo back for now, implement real updates later
            await manager.send_personal_message(f"Echo: {data}", websocket)
    except WebSocketDisconnect:
        manager.disconnect(websocket)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
