#!/bin/bash

# Song Rating Backend Run Script
# This script starts the FastAPI server with proper configuration

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check if virtual environment exists
check_venv() {
    if [ ! -d ".venv" ]; then
        print_error "Virtual environment not found. Please run ./setup.sh first."
        exit 1
    fi
}

# Function to check if .env file exists
check_env() {
    if [ ! -f ".env" ]; then
        print_error ".env file not found. Please run ./setup.sh first."
        exit 1
    fi
}

# Function to activate virtual environment
activate_venv() {
    print_status "Activating virtual environment..."
    source .venv/bin/activate
    print_success "Virtual environment activated"
}

# Function to check database connection
check_database() {
    print_status "Checking database connection..."

    # Simple check using alembic
    if alembic current 2>/dev/null; then
        print_success "Database connection successful"
    else
        print_error "Database connection failed. Please check your DATABASE_URL in .env"
        print_status "Make sure PostgreSQL is running and the database exists"
        exit 1
    fi
}

# Function to start the server
start_server() {
    local host=${1:-0.0.0.0}
    local port=${2:-8000}
    local reload=${3:-true}

    print_status "Starting FastAPI server..."
    print_status "Host: $host"
    print_status "Port: $port"
    print_status "Auto-reload: $reload"
    echo

    # Set environment variables
    export PYTHONPATH="${PYTHONPATH}:$(pwd)"

    # Start the server
    if [ "$reload" = "true" ]; then
        uvicorn app.main:app --host $host --port $port --reload
    else
        uvicorn app.main:app --host $host --port $port
    fi
}

# Function to show help
show_help() {
    echo "Song Rating Backend Run Script"
    echo "=============================="
    echo
    echo "Usage: ./run.sh [OPTIONS]"
    echo
    echo "Options:"
    echo "  --host HOST          Server host (default: 0.0.0.0)"
    echo "  --port PORT          Server port (default: 8000)"
    echo "  --no-reload          Disable auto-reload"
    echo "  --dev                Development mode (default: auto-reload enabled)"
    echo "  --prod               Production mode (no auto-reload)"
    echo "  --check-only         Only check dependencies and database"
    echo "  --help               Show this help message"
    echo
    echo "Examples:"
    echo "  ./run.sh                    # Start in development mode"
    echo "  ./run.sh --prod             # Start in production mode"
    echo "  ./run.sh --port 8080        # Start on port 8080"
    echo "  ./run.sh --host 127.0.0.1  # Start on localhost only"
}

# Main function
main() {
    # Default values
    local host="0.0.0.0"
    local port="8000"
    local reload="true"
    local check_only=false

    # Parse command line arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --host)
                host="$2"
                shift 2
                ;;
            --port)
                port="$2"
                shift 2
                ;;
            --no-reload)
                reload="false"
                shift
                ;;
            --dev)
                reload="true"
                shift
                ;;
            --prod)
                reload="false"
                shift
                ;;
            --check-only)
                check_only="true"
                shift
                ;;
            --help)
                show_help
                exit 0
                ;;
            *)
                print_error "Unknown option: $1"
                show_help
                exit 1
                ;;
        esac
    done

    print_status "Song Rating Backend Server"
    print_status "==========================="
    echo

    # Change to script directory
    cd "$(dirname "$0")"

    # Run checks
    check_venv
    check_env
    activate_venv
    check_database

    if [ "$check_only" = "true" ]; then
        print_success "All checks passed!"
        exit 0
    fi

    echo
    print_success "Starting server..."
    echo
    print_status "API Documentation: http://$host:$port/docs"
    print_status "Health Check: http://$host:$port/health"
    echo

    # Start the server
    start_server $host $port $reload
}

# Handle script interruption
trap 'print_status "Server stopped"; exit 0' INT TERM

# Run the main function
main "$@"