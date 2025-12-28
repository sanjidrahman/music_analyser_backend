# Song Rating Backend API

A comprehensive FastAPI backend for song rating and singing analysis that allows users to upload songs, extract segments, record themselves singing, and receive detailed performance analysis based on pitch accuracy, rhythm, tone similarity, and timing.

## Features

- **User Authentication**: JWT-based authentication with 7-day token expiry
- **Audio Upload & Processing**: Support for WAV, MP3, M4A, FLAC, OGG formats
- **Vocal Separation**: Automatic vocal separation using Spleeter
- **Segment Extraction**: Extract 10s-120s segments from uploaded songs
- **Recording Upload**: Upload user singing recordings
- **Audio Analysis**: Comprehensive analysis with detailed scoring:
  - Pitch Accuracy (40%): Compare pitch sequences using Dynamic Time Warping
  - Rhythm Accuracy (30%): Analyze tempo and beat alignment
  - Tone Similarity (20%): MFCC-based timbre comparison
  - Timing Accuracy (10%): Duration and timing match
- **User History**: View all past attempts with detailed analysis
- **File Management**: Automatic cleanup of expired files

## Tech Stack

- **Backend**: FastAPI with async/await
- **Database**: PostgreSQL with SQLAlchemy (async)
- **Authentication**: JWT tokens with bcrypt password hashing
- **Audio Processing**: librosa, Spleeter, pydub, fastdtw, crepe
- **File Storage**: Local filesystem with configurable paths
- **API Documentation**: OpenAPI/Swagger and ReDoc

## Requirements

- Python 3.8+
- PostgreSQL 12+
- FFmpeg (for audio processing)
- At least 2GB RAM for audio processing

## Quick Start

### 1. Clone and Setup

```bash
git clone <your-repo-url>
cd song-rating-backend
./setup.sh
```

### 2. Configure Environment

Edit the `.env` file:

```env
DATABASE_URL=postgresql+asyncpg://username:password@localhost:5432/song_rating_db
JWT_SECRET_KEY=your-super-secret-jwt-key-change-this
CORS_ORIGINS=http://localhost:3000,http://localhost:8080
```

### 3. Setup Database

```bash
# Create database
createdb song_rating_db

# Run migrations
alembic upgrade head
```

### 4. Start Server

```bash
./run.sh
```

The API will be available at:
- **API**: http://localhost:8000
- **Documentation**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## API Endpoints

### Authentication
- `POST /api/auth/register` - Register new user
- `POST /api/auth/login` - User login
- `GET /api/auth/me` - Get current user info
- `POST /api/auth/logout` - Logout

### Upload & Processing
- `POST /api/upload-and-process` - Upload song and extract segment (no auth required)
- `GET /api/formats/supported` - Get supported formats and limits

### Recording
- `POST /api/recording/upload` - Upload user recording (no auth required)
- `GET /api/recording/` - Get recordings (authenticated users only)
- `GET /api/recording/{id}` - Get specific recording

### Analysis
- `POST /api/analyze` - Analyze recording against original (requires auth)
- `GET /api/analysis-summary/{attempt_id}` - Get detailed analysis

### User History
- `GET /api/attempts/` - Get user attempts with filtering
- `GET /api/attempts/{id}` - Get specific attempt
- `DELETE /api/attempts/{id}` - Delete attempt
- `GET /api/attempts/stats/overview` - Get user statistics

## Project Structure

```
song-rating-backend/
├── app/
│   ├── main.py              # FastAPI application
│   ├── config.py            # Configuration settings
│   ├── database.py          # Database setup
│   ├── models/              # SQLAlchemy models
│   │   ├── user.py          # User model
│   │   ├── segment.py       # Song segment model
│   │   ├── recording.py     # User recording model
│   │   └── attempt.py       # Analysis attempt model
│   ├── schemas/             # Pydantic schemas
│   │   ├── user.py          # User schemas
│   │   ├── segment.py       # Segment schemas
│   │   ├── recording.py     # Recording schemas
│   │   ├── attempt.py       # Attempt schemas
│   │   └── common.py        # Common schemas
│   ├── api/                 # API routers
│   │   ├── auth.py          # Authentication endpoints
│   │   ├── upload.py        # File upload endpoints
│   │   ├── recording.py     # Recording endpoints
│   │   ├── analysis.py      # Analysis endpoints
│   │   └── attempts.py      # User history endpoints
│   ├── services/            # Business logic
│   │   ├── auth_service.py  # Authentication service
│   │   ├── file_service.py  # File management
│   │   ├── audio_processor.py # Audio processing
│   │   └── analyzer.py      # Audio analysis
│   └── utils/               # Utility functions
│       ├── security.py      # Security utilities
│       ├── dependencies.py  # FastAPI dependencies
│       └── exceptions.py    # Custom exceptions
├── alembic/                 # Database migrations
├── storage/                 # File storage
│   ├── segments/           # Song segments
│   ├── vocals/             # Separated vocals
│   └── recordings/         # User recordings
├── tests/                   # Test files
├── requirements.txt         # Python dependencies
├── .env.example            # Environment template
├── setup.sh                # Setup script
├── run.sh                  # Run script
└── README.md               # This file
```

## Configuration

The application is configured through environment variables:

### Database
- `DATABASE_URL` - PostgreSQL connection string
- `DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/db`

### Authentication
- `JWT_SECRET_KEY` - Secret key for JWT signing
- `ACCESS_TOKEN_EXPIRE_DAYS` - Token expiry (default: 7)

### File Upload
- `MAX_UPLOAD_SIZE_MB` - Max file size (default: 50)
- `ALLOWED_AUDIO_FORMATS` - Supported formats (default: wav,mp3,m4a,flac,ogg)
- `MIN_SEGMENT_DURATION` - Min segment length in seconds (default: 10)
- `MAX_SEGMENT_DURATION` - Max segment length in seconds (default: 120)

### Storage
- `STORAGE_PATH` - Base storage path (default: ./storage)
- `SEGMENT_RETENTION_DAYS` - File retention period (default: 7)

### CORS
- `CORS_ORIGINS` - Allowed origins (comma-separated)

## Audio Analysis Algorithm

The analysis system uses a sophisticated multi-faceted approach:

1. **Pitch Extraction**: Uses pYIN algorithm for accurate pitch detection
2. **Pitch Comparison**: Dynamic Time Warping (fastdtw) aligns pitch sequences
3. **Rhythm Analysis**: Tempo detection and beat alignment comparison
4. **Timbre Analysis**: 13 MFCC coefficients for tone similarity
5. **Timing Analysis**: Duration match and timing accuracy

### Scoring Breakdown
- **Pitch Accuracy (40%)**: Note-by-note pitch comparison
- **Rhythm Accuracy (30%)**: Tempo and beat alignment
- **Tone Similarity (20%)**: MFCC cosine similarity
- **Timing Accuracy (10%)**: Duration and timing precision

## Development

### Setup Development Environment

```bash
# Clone repository
git clone <repository-url>
cd song-rating-backend

# Run setup script
./setup.sh --with-tests
```

### Running Tests

```bash
# Activate virtual environment
source venv/bin/activate

# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=app --cov-report=html
```

### Code Quality

```bash
# Format code
black app/ tests/

# Sort imports
isort app/ tests/

# Lint code
flake8 app/ tests/

# Type checking
mypy app/
```

### Database Migrations

```bash
# Generate new migration
alembic revision --autogenerate -m "Description of changes"

# Apply migrations
alembic upgrade head

# Downgrade migrations
alembic downgrade -1
```

## Production Deployment

### Environment Setup

1. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure Environment**:
   ```bash
   cp .env.example .env
   # Edit .env with production values
   ```

3. **Setup Database**:
   ```bash
   alembic upgrade head
   ```

4. **Run with Gunicorn**:
   ```bash
   gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker
   ```

### Docker Deployment

```dockerfile
# Dockerfile example
FROM python:3.9-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Run application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Environment Variables

For production, ensure these are set:

```bash
export DATABASE_URL="postgresql+asyncpg://user:pass@db:5432/song_rating_db"
export JWT_SECRET_KEY="your-production-secret-key"
export DEBUG=False
export CORS_ORIGINS="https://yourdomain.com"
```

## Security Considerations

1. **JWT Secret**: Use a strong, randomly generated secret key
2. **Database**: Use SSL connections in production
3. **File Upload**: Validate file types and sizes
4. **Rate Limiting**: Consider implementing rate limiting
5. **CORS**: Configure appropriate origins
6. **HTTPS**: Always use HTTPS in production

## Performance Optimization

1. **Audio Processing**: Consider using Redis for caching processed segments
2. **File Storage**: Use S3 or similar for scalable file storage
3. **Database**: Add indexes for frequently queried columns
4. **Load Balancing**: Use multiple worker processes
5. **Monitoring**: Add health checks and monitoring

## Troubleshooting

### Common Issues

1. **Audio Processing Fails**:
   - Ensure FFmpeg is installed
   - Check file format support
   - Verify sufficient disk space

2. **Database Connection Errors**:
   - Check DATABASE_URL format
   - Ensure PostgreSQL is running
   - Verify database exists

3. **Authentication Issues**:
   - Verify JWT_SECRET_KEY is set
   - Check token expiry
   - Ensure correct header format

4. **File Upload Issues**:
   - Check file size limits
   - Verify file formats
   - Ensure storage directories exist

### Logging

Enable debug logging by setting `DEBUG=True` in `.env`:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## API Examples

See [API_EXAMPLES.md](API_EXAMPLES.md) for detailed API usage examples with curl, Python, and JavaScript.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Run the test suite
6. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For support, please:
- Check the troubleshooting section
- Review the API documentation
- Open an issue on GitHub
- Contact the development team