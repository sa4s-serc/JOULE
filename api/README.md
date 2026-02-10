# HEDGE API Server

FastAPI-based REST API and WebSocket server for the HEDGE optimization tool.

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run the server (default: INFO level logging)
python api/main.py

# Run with DEBUG logging
LOG_LEVEL=DEBUG python api/main.py

# Or using environment file
echo "LOG_LEVEL=DEBUG" > api/.env
python api/main.py
```

## Environment Variables

### Logging Configuration

- `LOG_LEVEL`: Set logging verbosity (default: `INFO`)
  - `DEBUG`: Detailed debugging information including mutation events, WebSocket messages
  - `INFO`: General informational messages
  - `WARNING`: Warning messages only
  - `ERROR`: Error messages only

### Server Configuration

- `HOST`: Server host address (default: `0.0.0.0`)
- `PORT`: Server port (default: `8000`)
- `ENVIRONMENT`: Environment mode (default: `development`)
  - `development`: Allows all CORS origins
  - `production`: Restricts CORS to `ALLOWED_ORIGINS`
- `ALLOWED_ORIGINS`: Comma-separated list of allowed origins for CORS (default: `http://localhost:5173,http://localhost:3000`)

## Debug Logging

When `LOG_LEVEL=DEBUG`, you'll see detailed logs including:

- API request/response details
- WebSocket connection events
- Mutation attempt and result events with mutator names
- Event broadcasting details
- Merge operation details in parallel orchestrator

Example debug output:
```
2024-01-01 12:00:00 - api.manager - DEBUG - [EVENT] Task abc-123: mutation_attempt - dict_keys(['mutator', 'mutator_display', 'strategy', 'parent'])
2024-01-01 12:00:00 - api.manager - DEBUG - [MUTATION_EVENT] mutation_attempt: mutator=CodePatternOptimizer, strategy=Pattern_ConditionalSimplification
2024-01-01 12:00:00 - api.manager - DEBUG - [WEBSOCKET_SEND] mutation_attempt: {'mutator': 'CodePatternOptimizer', 'mutator_display': 'Code Pattern Optimizer', 'strategy': 'Pattern_ConditionalSimplification', 'parent': 'variant_001'}
```

## Troubleshooting

### "Unknown" Mutator Names

If you see "Unknown" mutator names in the web interface:

1. Enable DEBUG logging: `LOG_LEVEL=DEBUG python api/main.py`
2. Check the logs for `[MERGE_DEBUG]` and `[MUTATOR_DEBUG]` messages
3. Look for warnings about empty mutator names
4. The system will attempt to infer mutator names from strategy names

The most common causes:
- Mutators not properly setting `mutator_name` when creating `MutationResult` objects
- Merge operations combining results with missing mutator metadata
- Custom mutators not using the mutation factory

### WebSocket Connection Issues

1. Check that the WebSocket URL matches your server configuration
2. Verify CORS settings allow your frontend origin
3. Enable DEBUG logging to see connection events
4. Check browser console for WebSocket errors

## API Endpoints

### REST Endpoints

- `POST /api/v1/optimize` - Start optimization task
  - Supports `mode` in request payload: `"standard"` (default) or `"agentic"`.
  - Example:
    ```json
    {
      "target_code": "def f(x): return x",
      "test_code": "def test_f(): assert f(1) == 1",
      "mode": "agentic"
    }
    ```
- `GET /api/v1/tasks/{task_id}` - Get task status
- `DELETE /api/v1/tasks/{task_id}` - Stop task
- `GET /api/v1/tasks/{task_id}/solutions/{variant_id}` - Get specific solution
- `GET /api/v1/tasks` - List all tasks
- `GET /health` - Health check

### WebSocket

- `WS /api/v1/ws/{task_id}` - Real-time optimization updates
  - Includes structured `stage_event` messages in `agentic` mode with: `action`, `stage`, `role`, `payload`, and `timestamp`.

## Development

```bash
# Run with auto-reload
uvicorn api.main:app --reload --log-level debug

# Run tests
pytest tests/test_api_endpoints.py -v
```
