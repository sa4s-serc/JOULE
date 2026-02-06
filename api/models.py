
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime


class LLMSettings(BaseModel):
    """Configuration for LLM providers."""
    provider: str = Field(default="gemini", description="LLM provider (gemini, openai)")
    model: str = Field(default="gemini-2.5-flash", description="Model name")
    api_key: Optional[str] = Field(default=None, description="API key (optional)")


class MutatorSettings(BaseModel):
    """Configuration for mutator layers."""
    layers: List[str] = Field(default=["micro", "algorithmic", "syntactic", "semantic"], 
                             description="Enabled mutator layers")
    disabled_mutators: List[str] = Field(default=[], description="Disabled specific mutators")


class EngineSettings(BaseModel):
    """Evolutionary engine parameters."""
    elite_size: int = Field(default=2, ge=1, description="Number of elite solutions to preserve")
    mutation_rate: float = Field(default=0.1, ge=0.0, le=1.0, description="Mutation rate")
    timeout: int = Field(default=30, ge=1, description="Execution timeout in seconds")


class OptimizationRequest(BaseModel):
    """Request model for starting an optimization."""
    target_code: str = Field(..., description="Python code to optimize")
    test_code: str = Field(..., description="Test code to validate optimizations")
    generations: int = Field(default=10, ge=1, le=100, description="Number of generations")
    population_size: int = Field(default=10, ge=2, le=50, description="Population size")
    level: str = Field(default="standard", description="Optimization level (micro/standard/advanced)")
    llm: Optional[LLMSettings] = Field(default=None, description="LLM configuration")
    mutators: Optional[MutatorSettings] = Field(default=None, description="Mutator configuration")
    engine: Optional[EngineSettings] = Field(default=None, description="Engine configuration")
    allowed_imports: List[str] = Field(default=[], description="Allowed import modules")
    config: Optional[Dict[str, Any]] = Field(default=None, description="Legacy config support")

    class Config:
        json_schema_extra = {
            "example": {
                "target_code": "def fib(n):\n    if n <= 1: return n\n    return fib(n-1) + fib(n-2)",
                "test_code": "def test_fib():\n    assert fib(10) == 55",
                "generations": 10,
                "population_size": 10,
                "level": "standard",
                "llm": {
                    "provider": "gemini",
                    "model": "gemini-2.5-flash"
                },
                "mutators": {
                    "layers": ["micro", "algorithmic", "syntactic", "semantic"]
                },
                "allowed_imports": ["math", "itertools"]
            }
        }


class TaskStatus(BaseModel):
    """Status of an optimization task."""
    task_id: str = Field(..., description="Unique task identifier")
    status: str = Field(..., description="Task status (running/completed/failed/stopped)")
    current_generation: int = Field(..., description="Current generation number")
    total_generations: int = Field(..., description="Total number of generations")
    best_metrics: Optional[Dict[str, float]] = Field(default=None, description="Best solution metrics")
    best_code: Optional[str] = Field(default=None, description="Best optimized code")
    start_time: Optional[datetime] = Field(default=None, description="Task start time")
    end_time: Optional[datetime] = Field(default=None, description="Task end time")

    class Config:
        json_schema_extra = {
            "example": {
                "task_id": "123e4567-e89b-12d3-a456-426614174000",
                "status": "running",
                "current_generation": 5,
                "total_generations": 10,
                "best_metrics": {
                    "energy_joules": 0.0012,
                    "duration_seconds": 0.0034
                },
                "best_code": "def fib(n):\n    a, b = 0, 1\n    for _ in range(n):\n        a, b = b, a + b\n    return a"
            }
        }


class WebSocketMessage(BaseModel):
    """Structure for WebSocket messages."""
    type: str = Field(..., description="Message type")
    payload: Dict[str, Any] = Field(..., description="Message payload")
    timestamp: float = Field(..., description="Unix timestamp")

    class Config:
        json_schema_extra = {
            "example": {
                "type": "generation_complete",
                "payload": {
                    "generation": 5,
                    "best_metrics": {
                        "energy_joules": 0.0012,
                        "duration_seconds": 0.0034
                    }
                },
                "timestamp": 1640995200.0
            }
        }


class SolutionResponse(BaseModel):
    """Response model for solution data."""
    variant_id: str = Field(..., description="Unique solution identifier")
    code: str = Field(..., description="Optimized code")
    metrics: Dict[str, float] = Field(..., description="Performance metrics")
    generation: Optional[int] = Field(default=None, description="Generation when found")
    mutator_used: Optional[str] = Field(default=None, description="Mutator that created this solution")

    class Config:
        json_schema_extra = {
            "example": {
                "variant_id": "solution_123",
                "code": "def fib(n):\n    a, b = 0, 1\n    for _ in range(n):\n        a, b = b, a + b\n    return a",
                "metrics": {
                    "energy_joules": 0.0012,
                    "duration_seconds": 0.0034
                },
                "generation": 5,
                "mutator_used": "IterativeOptimizer"
            }
        }


class ErrorResponse(BaseModel):
    """Error response model."""
    error: str = Field(..., description="Error type")
    message: str = Field(..., description="Error message")
    details: Optional[Dict[str, Any]] = Field(default=None, description="Additional error details")

    class Config:
        json_schema_extra = {
            "example": {
                "error": "ValidationError",
                "message": "Invalid Python code provided",
                "details": {
                    "line": 5,
                    "column": 12,
                    "syntax_error": "unexpected token"
                }
            }
        }
