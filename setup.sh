#!/bin/bash

# Song Rating Backend Setup Script
# This script sets up the entire development environment

set -e  # Exit on any error

echo "🎵 Song Rating Backend Setup Script"
echo "=================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
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

# Check if Python 3.8+ is installed
check_python() {
    print_status "Checking Python installation..."

    if ! command -v python3 &> /dev/null; then
        print_error "Python 3 is not installed. Please install Python 3.8 or higher."
        exit 1
    fi

    python_version=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
    required_version="3.8"

    if python3 -c "import sys; exit(0 if sys.version_info >= (3, 8) else 1)"; then
        print_success "Python $python_version found (>= 3.8 required)"
    else
        print_error "Python $python_version found. Please upgrade to Python 3.8 or higher."
        exit 1
    fi
}

# Check if PostgreSQL is installed
check_postgresql() {
    print_status "Checking PostgreSQL installation..."

    if ! command -v psql &> /dev/null; then
        print_warning "PostgreSQL client not found. Please install PostgreSQL."
        print_status "On macOS: brew install postgresql"
        print_status "On Ubuntu: sudo apt-get install postgresql postgresql-contrib"
        print_status "On Windows: Download from https://www.postgresql.org/download/"
        echo
        print_status "Continuing setup, but database setup will fail if PostgreSQL is not available..."
    else
        pg_version=$(psql --version | head -n1 | awk '{print $3}')
        print_success "PostgreSQL $pg_version found"
    fi
}

# Check if FFmpeg is installed
check_ffmpeg() {
    print_status "Checking FFmpeg installation..."

    if ! command -v ffmpeg &> /dev/null; then
        print_warning "FFmpeg not found. Please install FFmpeg for audio processing."
        print_status "On macOS: brew install ffmpeg"
        print_status "On Ubuntu: sudo apt-get install ffmpeg"
        print_status "On Windows: Download from https://ffmpeg.org/download.html"
        echo
        print_status "Continuing setup, but audio processing will fail without FFmpeg..."
    else
        ffmpeg_version=$(ffmpeg -version | head -n1 | awk '{print $3}')
        print_success "FFmpeg $ffmpeg_version found"
    fi
}

# Create Python virtual environment
create_venv() {
    print_status "Creating Python virtual environment..."

    if [ ! -d ".venv" ]; then
        python3 -m venv .venv
        print_success "Virtual environment created"
    else
        print_success "Virtual environment already exists"
    fi

    # Activate virtual environment
    print_status "Activating virtual environment..."
    source .venv/bin/activate

    # Upgrade pip
    pip install --upgrade pip
    print_success "Pip upgraded"
}

# Install Python dependencies
install_dependencies() {
    print_status "Installing Python dependencies..."

    # Activate virtual environment
    source .venv/bin/activate

    # Install requirements
    pip install -r requirements.txt
    print_success "Dependencies installed"
}

# Create .env file if it doesn't exist
setup_env() {
    print_status "Setting up environment configuration..."

    if [ ! -f ".env" ]; then
        cp .env.example .env
        print_success "Created .env file from .env.example"
        print_warning "Please edit .env file with your database URL and JWT secret key"
        print_status "Important: Change JWT_SECRET_KEY to a secure random string"
        print_status "Update DATABASE_URL with your PostgreSQL connection string"
    else
        print_success ".env file already exists"
    fi
}

# Create storage directories
create_storage_dirs() {
    print_status "Creating storage directories..."

    mkdir -p storage/segments
    mkdir -p storage/vocals
    mkdir -p storage/recordings
    mkdir -p storage/temp

    print_success "Storage directories created"
}

# Database setup
setup_database() {
    print_status "Setting up database..."

    # Activate virtual environment
    source .venv/bin/activate

    # Check if DATABASE_URL is set
    if grep -q "your-database-url-here" .env; then
        print_warning "Please update DATABASE_URL in .env file before running database migrations"
        print_status "Example: postgresql+asyncpg://username:password@localhost:5432/song_rating_db"
        print_status "After updating, run: alembic upgrade head"
    else
        # Generate initial migration
        print_status "Generating database migration..."
        alembic revision --autogenerate -m "Initial migration"

        # Run migrations
        print_status "Running database migrations..."
        alembic upgrade head

        print_success "Database setup completed"
    fi
}

# Run tests
run_tests() {
    print_status "Running tests..."

    # Activate virtual environment
    source .venv/bin/activate

    if python -m pytest tests/ -v; then
        print_success "All tests passed"
    else
        print_warning "Some tests failed. Check the output above."
    fi
}

# Main setup function
main() {
    print_status "Starting setup process..."
    echo

    # Change to project directory
    cd "$(dirname "$0")"

    # Run checks
    check_python
    check_postgresql
    check_ffmpeg
    echo

    # Setup environment
    create_venv
    echo

    # Install dependencies
    install_dependencies
    echo

    # Setup configuration
    setup_env
    echo

    # Create directories
    create_storage_dirs
    echo

    # Setup database
    setup_database
    echo

    # Run tests (optional)
    if [ "$1" == "--with-tests" ]; then
        run_tests
        echo
    fi

    print_success "Setup completed successfully!"
    echo
    print_status "Next steps:"
    print_status "1. Edit .env file with your database URL and JWT secret key"
    print_status "2. Run database migrations: alembic upgrade head"
    print_status "3. Start the server: ./run.sh"
    echo
    print_status "API Documentation will be available at: http://localhost:8000/docs"
}

# Run the script
main "$@"