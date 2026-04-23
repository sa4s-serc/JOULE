#!/bin/bash

# Development startup script for JOULE Web UI
# This script starts both frontend and backend servers

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
BACKEND_PORT=${JOULE_BACKEND_PORT:-8000}
FRONTEND_PORT=${JOULE_FRONTEND_PORT:-3000}
HOST=${JOULE_HOST:-127.0.0.1}

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$SCRIPT_DIR/backend"
FRONTEND_DIR="$SCRIPT_DIR/frontend"

echo -e "${BLUE}JOULE Web UI Development Server${NC}"
echo "=================================="
echo ""

# Function to check if port is in use
check_port() {
    local port=$1
    if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1; then
        return 0
    else
        return 1
    fi
}

# Function to cleanup processes
cleanup() {
    echo -e "\n${YELLOW}Shutting down servers...${NC}"
    
    if [ ! -z "$BACKEND_PID" ]; then
        kill $BACKEND_PID 2>/dev/null || true
    fi
    
    if [ ! -z "$FRONTEND_PID" ]; then
        kill $FRONTEND_PID 2>/dev/null || true
    fi
    
    # Wait for processes to exit
    sleep 2
    
    echo -e "${GREEN}✓ All servers stopped${NC}"
    exit 0
}

# Set up signal handlers
trap cleanup SIGINT SIGTERM

# Check directories
if [ ! -d "$BACKEND_DIR" ]; then
    echo -e "${RED}Error: Backend directory not found: $BACKEND_DIR${NC}"
    exit 1
fi

if [ ! -d "$FRONTEND_DIR" ]; then
    echo -e "${RED}Error: Frontend directory not found: $FRONTEND_DIR${NC}"
    exit 1
fi

# Check if ports are available
if check_port $BACKEND_PORT; then
    echo -e "${RED}Error: Backend port $BACKEND_PORT is already in use${NC}"
    echo "Use a different port or stop the process using this port"
    exit 1
fi

if check_port $FRONTEND_PORT; then
    echo -e "${RED}Error: Frontend port $FRONTEND_PORT is already in use${NC}"
    echo "Use a different port or stop the process using this port"
    exit 1
fi

# Check dependencies
echo -e "${BLUE}Checking dependencies...${NC}"

# Check Python dependencies
cd "$BACKEND_DIR"
if ! python -c "import fastapi" 2>/dev/null; then
    echo -e "${YELLOW}Installing Python dependencies...${NC}"
    pip install -r requirements.txt
fi

# Check Node.js dependencies
cd "$FRONTEND_DIR"
if [ ! -d "node_modules" ]; then
    echo -e "${YELLOW}Installing Node.js dependencies...${NC}"
    npm install
fi

echo -e "${GREEN}✓ Dependencies checked${NC}"
echo ""

# Start backend server
echo -e "${BLUE}Starting backend server...${NC}"
cd "$BACKEND_DIR"
uvicorn main:app --host $HOST --port $BACKEND_PORT --reload &
BACKEND_PID=$!

# Wait for backend to start
echo -e "${YELLOW}Waiting for backend to start...${NC}"
sleep 3

# Check if backend started successfully
if ! check_port $BACKEND_PORT; then
    echo -e "${RED}Error: Backend server failed to start${NC}"
    kill $BACKEND_PID 2>/dev/null || true
    exit 1
fi

echo -e "${GREEN}✓ Backend server started at http://$HOST:$BACKEND_PORT${NC}"

# Start frontend server
echo -e "${BLUE}Starting frontend server...${NC}"
cd "$FRONTEND_DIR"
npm run dev &
FRONTEND_PID=$!

# Wait for frontend to start
echo -e "${YELLOW}Waiting for frontend to start...${NC}"
sleep 5

# Check if frontend started successfully
if ! check_port $FRONTEND_PORT; then
    echo -e "${RED}Error: Frontend server failed to start${NC}"
    kill $BACKEND_PID 2>/dev/null || true
    kill $FRONTEND_PID 2>/dev/null || true
    exit 1
fi

echo -e "${GREEN}✓ Frontend server started at http://localhost:$FRONTEND_PORT${NC}"
echo ""

# Display summary
echo -e "${GREEN}🚀 JOULE Web UI is running!${NC}"
echo "=================================="
echo -e "🌐 Frontend: ${BLUE}http://localhost:$FRONTEND_PORT${NC}"
echo -e "🔧 Backend API: ${BLUE}http://$HOST:$BACKEND_PORT${NC}"
echo -e "📚 API Docs: ${BLUE}http://$HOST:$BACKEND_PORT/docs${NC}"
echo ""
echo -e "${YELLOW}Press Ctrl+C to stop all servers${NC}"
echo ""

# Wait for processes
wait
