# JOULE Web UI

A comprehensive web interface for the JOULE optimization toolkit that exposes all CLI capabilities through an interactive web interface.

## Features

- **Complete CLI Parity**: All JOULE commands accessible through web interface
- **Real-time Updates**: Live optimization progress with WebSocket updates
- **Interactive Code Exploration**: Syntax-highlighted code browsing and candidate inspection
- **Modern UI**: React + TypeScript with TailwindCSS, matching JOULE's aesthetic
- **Project Management**: Multi-project support with health monitoring
- **Visualization**: Charts and graphs for optimization metrics and hotspots

## Architecture

### Frontend
- **Framework**: React 18 + TypeScript
- **Styling**: TailwindCSS with JOULE color scheme
- **State Management**: Zustand stores
- **Routing**: React Router
- **Real-time**: WebSocket client
- **Code Display**: Monaco Editor integration

### Backend
- **API**: FastAPI with async endpoints
- **WebSocket**: Real-time updates for running optimizations
- **CORS**: Proper cross-origin configuration
- **Integration**: Direct access to JOULE's core modules

## Development

### Prerequisites
- Node.js 18+ and npm
- Python 3.12+ with JOULE dependencies

### Setup

1. **Install Frontend Dependencies**
   ```bash
   cd src/joule/web_ui/frontend
   npm install
   ```

2. **Install Backend Dependencies**
   ```bash
   cd src/joule/web_ui/backend
   pip install -r requirements.txt
   ```

### Running the Development Servers

#### Option 1: Using the CLI Command (Recommended)
```bash
# From your project directory
joule ui .
```

This will start both frontend and backend servers automatically.

#### Option 2: Manual Start

**Backend Server:**
```bash
cd src/joule/web_ui/backend
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

**Frontend Server:**
```bash
cd src/joule/web_ui/frontend
npm run dev
```

### Accessing the UI

- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs

## CLI Options

```bash
joule ui [PROJECT_PATH] [OPTIONS]

Options:
  --host TEXT          UI server host [default: 127.0.0.1]
  --port INTEGER       UI server port [default: from config]
  --backend-only       Start only the backend API server
  --frontend-only      Start only the frontend dev server
  --verbose            Print detailed events
  --quiet              Reduce terminal output
```

## Project Structure

```
src/joule/web_ui/
├── frontend/                 # React frontend
│   ├── src/
│   │   ├── components/      # Reusable UI components
│   │   ├── pages/          # Page components
│   │   ├── hooks/          # Custom React hooks
│   │   ├── stores/         # Zustand state stores
│   │   ├── types/          # TypeScript type definitions
│   │   └── utils/          # Utility functions
│   ├── public/             # Static assets
│   └── package.json
├── backend/                  # FastAPI backend
│   ├── api/                # API route handlers
│   ├── main.py             # FastAPI application
│   └── requirements.txt
└── README.md
```

## API Endpoints

### Projects
- `GET /api/projects` - List projects
- `GET /api/projects/{path}` - Get project details
- `POST /api/projects/{path}/doctor` - Run health check

### Discovery
- `GET /api/projects/{path}/discover/targets` - Discover targets
- `GET /api/projects/{path}/discover/workloads/{target}` - Discover workloads

### Execution
- `POST /api/projects/{path}/baseline` - Run baseline
- `POST /api/projects/{path}/optimize` - Run optimization

### Runs
- `GET /api/runs` - List runs
- `GET /api/runs/{run_id}` - Get run details
- `POST /api/runs/{run_id}/apply` - Apply candidate

### WebSocket
- `WS /ws` - Real-time updates

## WebSocket Events

### Client → Server
- `subscribe_run` - Subscribe to run updates
- `unsubscribe_run` - Unsubscribe from run updates
- `ping` - Keep-alive ping

### Server → Client
- `run_update` - Run status/progress updates
- `candidate_update` - New candidate evaluation
- `error` - Error notifications
- `log` - Log messages

## State Management

### Project Store
- Project list and current project
- Target and workload discovery
- Selection state

### Run Store
- Run history and current run details
- Real-time run updates
- Baseline and optimization execution

## Contributing

1. Follow the existing code style and patterns
2. Add TypeScript types for new components
3. Include proper error handling
4. Update API documentation for new endpoints
5. Test WebSocket functionality for real-time features

## Production Deployment

For production deployment:

1. **Build Frontend**
   ```bash
   cd frontend
   npm run build
   ```

2. **Configure Production Backend**
   - Use production ASGI server (Gunicorn + Uvicorn)
   - Configure proper CORS origins
   - Set up SSL/TLS

3. **Static File Serving**
   - Serve built frontend from backend
   - Or use reverse proxy (nginx)

## Troubleshooting

### Common Issues

1. **Port Conflicts**: Change ports using `--port` option
2. **CORS Errors**: Ensure frontend URL is in CORS allow list
3. **WebSocket Connection**: Check firewall and proxy settings
4. **Missing Dependencies**: Run `npm install` and `pip install -r requirements.txt`

### Debug Mode

Enable verbose logging:
```bash
joule ui . --verbose
```

This will show detailed startup logs and error messages.
