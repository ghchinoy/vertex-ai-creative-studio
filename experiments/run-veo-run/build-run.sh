#!/bin/bash
# Local Build & Run for Run, Veo, Run
set -e

# Default mode
DEV_MODE=false

# Check for flags
for arg in "$@"; do
  case $arg in
    --dev)
      DEV_MODE=true
      shift
      ;;
  esac
done

# Load .env if it exists
if [ -f .env ]; then
    set -a
    source .env
    set +a
fi

# Ensure public dir exists
mkdir -p frontend/public

# Copy Changelog if it exists
if [ -f CHANGELOG.md ]; then
    cp CHANGELOG.md frontend/public/
fi

if [ "$DEV_MODE" = true ]; then
    echo "🔧 Starting in DEV MODE (Hot Reload)..."
    
    # Function to cleanup background process
    cleanup() {
        echo "🛑 Stopping Backend..."
        kill $BACKEND_PID
        exit
    }
    
    # Trap Ctrl+C (SIGINT) and cleanup
    trap cleanup SIGINT

    echo "🚀 Starting Backend (Background)..."
    cd server && PORT=8080 go run . &
    BACKEND_PID=$!
    
    # Wait for backend to be ready (simple sleep)
    sleep 2

    echo "🎨 Starting Frontend (Vite)..."
    cd ../frontend && npm run dev
    
    # If npm run dev exits, cleanup
    cleanup

else
    echo "🏗️  Building Frontend..."
    cd frontend && npm run build

    echo "🚀 Starting Server..."
    cd ../server && PORT=8080 go run .
fi
