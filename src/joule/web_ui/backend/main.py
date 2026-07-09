from __future__ import annotations

import os
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    project_path = os.environ.get("JOULE_PROJECT_PATH", ".")
    app.state.project_path = str(Path(project_path).resolve())
    logger.info("JOULE Web UI backend starting for %s", app.state.project_path)
    yield
    logger.info("JOULE Web UI backend shutting down")


app = FastAPI(
    title="JOULE Web UI API",
    description="Web API for the JOULE energy-optimisation toolkit",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from joule.web_ui.backend.api.projects import router as projects_router  # noqa: E402
from joule.web_ui.backend.api.runs import router as runs_router  # noqa: E402
from joule.web_ui.backend.api.websocket import router as ws_router  # noqa: E402


@app.get("/api/health")
def health_check():
    return {"status": "ok"}

app.include_router(projects_router, prefix="/api")
app.include_router(runs_router, prefix="/api")
app.include_router(ws_router)


@app.get("/")
async def root():
    return {"message": "JOULE Web UI API", "version": "0.1.0"}


_FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if _FRONTEND_DIST.is_dir():
    app.mount("/", StaticFiles(directory=str(_FRONTEND_DIST), html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn

    host = os.environ.get("JOULE_UI_HOST", "127.0.0.1")
    port = int(os.environ.get("JOULE_UI_PORT", "8000"))
    uvicorn.run(app, host=host, port=port)
