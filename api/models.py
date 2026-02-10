from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class LLMSettings(BaseModel):
    """Configuration for LLM providers."""

    provider: str = Field(default="gemini", description="LLM provider (gemini, openai)")
    model: str = Field(default="gemini-2.5-flash", description="Model name")
    api_key: Optional[str] = Field(default=None, description="API key (optional)")


class MutatorSettings(BaseModel):
    """Configuration for mutator layers."""

    layers: List[str] = Field(
        default=["micro", "algorithmic", "syntactic", "semantic"],
        description="Enabled mutator layers",
    )
    disabled_mutators: List[str] = Field(default=[], description="Disabled specific mutators")


class EngineSettings(BaseModel):
    """Evolutionary engine parameters."""

    elite_size: int = Field(default=2, ge=1, description="Number of elite solutions to preserve")
    mutation_rate: float = Field(default=0.1, ge=0.0, le=1.0, description="Mutation rate")
    timeout: int = Field(default=30, ge=1, description="Execution timeout in seconds")
    test_iterations: int = Field(
        default=3,
        ge=1,
        le=50,
        description="Number of measured iterations per candidate for metrics aggregation",
    )
    test_warmup_iterations: int = Field(
        default=0,
        ge=0,
        le=100,
        description="Number of warmup iterations before each measured run",
    )
    test_seed: Optional[int] = Field(
        default=None,
        description="Base seed for deterministic test execution across iterations",
    )


class StageEventPayload(BaseModel):
    """Structured stage event for API/WebSocket visibility."""

    action: str = Field(..., description="Lifecycle action (stage_started/stage_completed)")
    stage: str = Field(..., description="Current stage name")
    role: str = Field(..., description="Agent role handling the stage")
    payload: Dict[str, Any] = Field(default_factory=dict, description="Stage output payload")
    timestamp: float = Field(..., description="Unix timestamp")


class OptimizationRequest(BaseModel):
    """Request model for starting an optimization."""

    target_code: str = Field(..., description="Python code to optimize")
    test_code: str = Field(..., description="Test code to validate optimizations")
    generations: int = Field(default=10, ge=1, le=100, description="Number of generations")
    population_size: int = Field(default=10, ge=2, le=50, description="Population size")
    level: str = Field(default="standard", description="Optimization level (micro/standard/advanced)")
    mode: str = Field(default="standard", description="Execution mode (standard/agentic)")
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
                "mode": "agentic",
                "llm": {"provider": "gemini", "model": "gemini-2.5-flash"},
                "mutators": {"layers": ["micro", "algorithmic", "syntactic", "semantic"]},
                "allowed_imports": ["math", "itertools"],
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


class WebSocketMessage(BaseModel):
    """Structure for WebSocket messages."""

    type: str = Field(..., description="Message type")
    payload: Dict[str, Any] = Field(..., description="Message payload")
    timestamp: float = Field(..., description="Unix timestamp")


class SolutionResponse(BaseModel):
    """Response model for solution data."""

    variant_id: str = Field(..., description="Unique solution identifier")
    code: str = Field(..., description="Optimized code")
    metrics: Dict[str, float] = Field(..., description="Performance metrics")
    generation: Optional[int] = Field(default=None, description="Generation when found")
    mutator_used: Optional[str] = Field(default=None, description="Mutator that created this solution")


class ErrorResponse(BaseModel):
    """Error response model."""

    error: str = Field(..., description="Error type")
    message: str = Field(..., description="Error message")
    details: Optional[Dict[str, Any]] = Field(default=None, description="Additional error details")
