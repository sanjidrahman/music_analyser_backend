# Docker Setup Guide (Easiest Method)

This is the **easiest way** to get the Song Rating Backend running locally without installing Python, PostgreSQL, or FFmpeg manually.

## Prerequisites

- Docker Desktop installed ([Download](https://www.docker.com/products/docker-desktop/))
- Git installed

## Quick Start (3 minutes)

### 1. Clone the Repository

```bash
git clone <your-repository-url>
cd music-analyser-backend
```

### 2. Start the Application

```bash
docker-compose up -d
```

This will:
- Pull the PostgreSQL Docker image
- Build the FastAPI backend
- Start both services
- Automatically run database migrations
- Make the API available at http://localhost:8000

### 3. Verify Everything is Running

```bash
# Check containers are running
docker-compose ps

# Check logs
docker-compose logs -f api

# Test API
curl http://localhost:8000/health
```

### 4. Access the API

- **API Documentation**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **Health Check**: http://localhost:8000/health

## Docker Commands Reference

### Start Services

```bash
# Start in detached mode (background)
docker-compose up -d

# Start with logs visible
docker-compose up

# Build and start (if you made changes)
docker-compose up -d --build
```

### Stop Services

```bash
# Stop all services
docker-compose down

# Stop and remove volumes (deletes database data)
docker-compose down -v
```

### View Logs

```bash
# View all logs
docker-compose logs

# Follow API logs
docker-compose logs -f api

# Follow database logs
docker-compose logs -f db

# View last 100 lines
docker-compose logs --tail=100 api
```

### Run Commands in Container

```bash
# Open shell in API container
docker-compose exec api bash

# Run database migrations manually
docker-compose exec api alembic upgrade head

# Create a new migration
docker-compose exec api alembic revision --autogenerate -m "Description"

# Activate Python shell
docker-compose exec api python
```

### Database Access

```bash
# Connect to PostgreSQL
docker-compose exec db psql -U postgres -d song_rating_db

# Run SQL commands
docker-compose exec db psql -U postgres -d song_rating_db -c "SELECT * FROM users;"
```

## Environment Variables

You can customize the application by creating a `.env` file in the project root:

```env
# JWT Secret (change this!)
JWT_SECRET_KEY=your-super-secret-key-here

# Database (automatically configured by Docker)
DATABASE_URL=postgresql+asyncpg://postgres:postgres@db:5432/song_rating_db

# Application settings
DEBUG=True
CORS_ORIGINS=*
PORT=8000
```

## Troubleshooting

### Issue 1: Port Already in Use

If port 8000 or 5432 is already in use:

```bash
# Edit docker-compose.yml to use different ports
ports:
  - "8001:8000"  # Use port 8001 instead
  - "5433:5432"  # Use port 5433 instead
```

### Issue 2: Database Connection Error

```bash
# Restart services
docker-compose down
docker-compose up -d

# Check database is ready
docker-compose exec db pg_isready -U postgres
```

### Issue 3: Build Failures

```bash
# Clean rebuild
docker-compose down
docker system prune -af
docker-compose build --no-cache
docker-compose up -d
```

### Issue 4: Permission Issues

```bash
# Fix storage permissions on Linux/Mac
sudo chown -R $USER:$USER storage/

# Or run with user flag in docker-compose.yml
user: "${UID}:${GID}"
```

### Issue 5: Container Keeps Restarting

```bash
# Check logs
docker-compose logs api

# Common issues:
# - Database not ready: Increase sleep time in docker-compose.yml
# - Migration failures: Check database connection
# - Port conflicts: Change ports in docker-compose.yml
```

## Development Workflow with Docker

### 1. Making Code Changes

Since volumes are mounted, changes to your code are reflected immediately:

```bash
# Edit files in app/ directory
# Auto-reload is enabled, changes apply automatically
```

### 2. Viewing Real-time Logs

```bash
docker-compose logs -f api
```

### 3. Database Migrations

```bash
# After changing models, create migration
docker-compose exec api alembic revision --autogenerate -m "Description"

# Apply migration
docker-compose exec api alembic upgrade head
```

### 4. Reset Everything

```bash
# Stop and remove all containers and volumes
docker-compose down -v

# Start fresh
docker-compose up -d
```

## Docker File Structure

```
docker-compose.yml    # Main docker compose configuration
Dockerfile            # API container build instructions
.env                 # Environment variables (optional)
storage/             # Persisted storage (mounted as volume)
```

## Advantages of Docker Setup

✅ **No manual installation** - No need to install Python, PostgreSQL, or FFmpeg
✅ **Isolated environment** - Won't affect your system
✅ **Reproducible** - Same environment for everyone
✅ **Easy cleanup** - Just `docker-compose down` to remove everything
✅ **Hot reload** - Code changes apply automatically
✅ **Database included** - PostgreSQL is set up automatically

## When NOT to Use Docker

- If you need to debug Python code with an IDE
- If you want to understand the codebase structure better
- If you're on a machine with limited RAM
- If you prefer manual setup for learning purposes

## Performance Notes

- Docker setup uses more RAM (~1-2 GB)
- First-time build takes 2-5 minutes
- Subsequent starts are much faster (~10 seconds)
- Storage I/O may be slightly slower than native

## Next Steps

After Docker setup is running:

1. Test the API at http://localhost:8000/docs
2. Read the [LOCAL_SETUP.md](LOCAL_SETUP.md) for API usage
3. Explore the code in the `app/` directory
4. Check [README.md](README.md) for detailed API documentation

## Switching Between Docker and Native Setup

You can use both setups interchangeably:

```bash
# Use Docker (recommended for quick start)
docker-compose up -d

# Or use native setup (see LOCAL_SETUP.md)
./setup.sh
./run.sh
```

Just make sure only one is running at a time (both use port 8000 and 5432).

---

**Need Help?** Check [LOCAL_SETUP.md](LOCAL_SETUP.md) for manual setup or troubleshooting tips.
