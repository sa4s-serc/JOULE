
import os
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.endpoints import router

# Configure logging based on environment variable
LOG_LEVEL = os.getenv("LOG_LEVEL", "DEBUG").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

logger.info(f"Starting HEDGE API with log level: {LOG_LEVEL}")

app = FastAPI(
    title="HEDGE API", 
    description="API for HEDGE Optimization Tool",
    version="1.0.0"
)

# Environment-based CORS configuration
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:5173,http://localhost:3000").split(",")
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")

logger.info(f"Environment: {ENVIRONMENT}")
logger.info(f"Allowed origins: {ALLOWED_ORIGINS}")

# Setup CORS with environment-specific settings
if ENVIRONMENT == "development":
    logger.info("Setting up CORS for development (allow all origins)")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Allow all in development
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
else:
    logger.info(f"Setting up CORS for production (restricted origins)")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["*"],
    )

# Include router with both old and new paths for backward compatibility
app.include_router(router, prefix="/api/v1", tags=["v1"])
app.include_router(router, tags=["legacy"])  # Legacy support without prefix

logger.info("API routes configured")

# Health check endpoint
@app.get("/health")
async def health_check():
    return {"status": "healthy", "version": "1.0.0", "log_level": LOG_LEVEL}

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    host = os.getenv("HOST", "0.0.0.0")
    logger.info(f"Starting server on {host}:{port}")
    uvicorn.run(app, host=host, port=port, log_level=LOG_LEVEL.lower())
