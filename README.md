# GitHub Webhook System

A minimal event processing pipeline that captures GitHub repository events (Push, Pull Request, Merge) from a source repository, processes them through a Flask backend, stores essential data in MongoDB, and displays events in a clean UI with 15-second polling updates.

## Table of Contents

- [Project Structure](#project-structure)
- [Prerequisites](#prerequisites)
- [Quick Start with Docker](#quick-start-with-docker)
- [Celery Distributed Task Queue](#celery-distributed-task-queue)
- [Structured Logging](#structured-logging)
- [Local Development Setup](#local-development-setup)
- [GitHub Webhook Configuration](#github-webhook-configuration)
- [ngrok Setup and Usage](#ngrok-setup-and-usage)
- [Running the Application](#running-the-application)
- [Testing](#testing)
- [Troubleshooting](#troubleshooting)
- [Environment Variables](#environment-variables)
- [API Endpoints](#api-endpoints)

## Project Structure

```
webhook-repo/
├── run.py                   # Flask application entry point
├── app/                     # Application package
│   ├── static/              # CSS, JavaScript files
│   │   ├── css/
│   │   │   └── style.css
│   │   └── js/
│   │       └── app.js
│   ├── templates/           # HTML templates
│   │   └── index.html
│   └── webhook/             # Core webhook system modules
│       ├── __init__.py      # Module initialization
│       ├── webhook_handler.py  # Webhook processing logic
│       ├── database.py      # MongoDB connection and operations
│       ├── models.py        # Data models and validation
│       ├── logging_config.py   # Logging configuration
│       └── extensions.py    # Flask extensions
├── requirements.txt         # Python dependencies
├── .env.example            # Environment variables template
├── test_*.py               # Test files
└── README.md               # This file
```

### Architecture Overview

The application follows a modular Flask structure:

- **`run.py`**: Main entry point that creates and configures the Flask application
- **`app/static/`**: Frontend assets (CSS for styling, JavaScript for 15-second polling)
- **`app/templates/`**: HTML templates for the web interface
- **`app/webhook/`**: Core webhook processing modules:
  - `webhook_handler.py`: Processes GitHub webhook payloads
  - `database.py`: MongoDB operations and connection management
  - `models.py`: Data models for webhook events
  - `logging_config.py`: Centralized logging configuration
  - `extensions.py`: Flask extensions and utilities

### User Interface Components

The web interface provides real-time monitoring of GitHub webhook events:

- **`app/templates/index.html`**: Main UI template displaying webhook events in a clean, responsive layout
- **`app/static/css/style.css`**: Styling for the web interface with modern design and responsive layout
- **`app/static/js/app.js`**: JavaScript for automatic polling every 15 seconds to fetch and display new events without page refresh

The UI automatically updates to show new webhook events as they arrive, providing real-time visibility into repository activity.

## Prerequisites

### For Docker Deployment (Recommended)

- **Docker Engine 20.10+**: [Install Docker](https://docs.docker.com/get-docker/)
- **Docker Compose 2.0+**: [Install Docker Compose](https://docs.docker.com/compose/install/)
- **ngrok**: For exposing local server to GitHub webhooks
  - Download from [ngrok.com](https://ngrok.com/download)
  - Create free account for authentication token
- **Git**: For version control and GitHub integration

### For Local Development (Without Docker)

- **Python 3.8 or higher**: Download from [python.org](https://www.python.org/downloads/)
- **MongoDB**: Choose one of the following:
  - Local installation: [MongoDB Community Server](https://www.mongodb.com/try/download/community)
  - Cloud: [MongoDB Atlas](https://www.mongodb.com/atlas) (free tier available)
- **Redis**: For Celery message broker
  - Local installation: [Redis](https://redis.io/download)
  - Cloud: Redis Cloud or use Docker
- **ngrok**: For exposing local server to GitHub webhooks
  - Download from [ngrok.com](https://ngrok.com/download)
  - Create free account for authentication token
- **Git**: For version control and GitHub integration

## Quick Start with Docker

The fastest way to get started is using Docker, which handles all dependencies automatically.

### 1. Clone Repository

```bash
git clone <repository-url>
cd webhook-repo
```

### 2. Configure Environment

```bash
# Copy environment template
cp .env.example .env

# Edit .env if needed (Docker defaults work out of the box)
```

### 3. Start All Services

```bash
# Build and start all containers
docker-compose up --build

# Or run in detached mode
docker-compose up -d
```

This single command starts:
- Flask application (http://localhost:5000)
- MongoDB database
- Redis message broker
- Celery worker for async processing
- Celery beat scheduler

### 4. Verify Services

```bash
# Check service health
docker-compose ps

# View logs
docker-compose logs -f

# Test health endpoint
curl http://localhost:5000/health
```

### 5. Setup ngrok and GitHub Webhook

```bash
# In a new terminal, expose the Flask app
ngrok http 5000

# Use the ngrok HTTPS URL in GitHub webhook settings
# Example: https://abc123.ngrok.io/webhook
```

### Docker Management

```bash
# Stop all services
docker-compose down

# Stop and remove volumes (clean slate)
docker-compose down -v

# View logs for specific service
docker-compose logs -f flask-app
docker-compose logs -f celery-worker

# Restart a specific service
docker-compose restart flask-app

# Scale Celery workers
docker-compose up --scale celery-worker=3
```

### Viewing Logs

Docker containers write logs to both stdout (viewable via docker-compose) and mounted log files:

```bash
# View real-time logs from all services
docker-compose logs -f

# View logs from specific service
docker-compose logs -f flask-app
docker-compose logs -f celery-worker
docker-compose logs -f mongodb

# View last 100 lines
docker-compose logs --tail=100 flask-app

# Access log files on host system
# Logs are mounted to ./logs directory
cat logs/app.log
cat logs/celery.log

# Follow log files on host
tail -f logs/app.log
tail -f logs/celery.log
```

### Docker Troubleshooting

**Container Won't Start**
```bash
# Check container status
docker-compose ps

# View container logs for errors
docker-compose logs flask-app

# Rebuild containers from scratch
docker-compose down -v
docker-compose build --no-cache
docker-compose up
```

**Port Already in Use**
```
Error: Bind for 0.0.0.0:5000 failed: port is already allocated
```
- Stop other services using port 5000
- Or modify port in docker-compose.yml: `"5001:5000"`

**MongoDB Connection Issues**
```bash
# Verify MongoDB container is running
docker-compose ps mongodb

# Check MongoDB logs
docker-compose logs mongodb

# Test MongoDB connection from flask-app container
docker-compose exec flask-app ping mongodb
```

**Redis Connection Issues**
```bash
# Verify Redis container is running
docker-compose ps redis

# Check Redis logs
docker-compose logs redis

# Test Redis connection
docker-compose exec redis redis-cli ping
```

**Celery Worker Not Processing Tasks**
```bash
# Check Celery worker logs
docker-compose logs celery-worker

# Verify Redis connection
docker-compose exec celery-worker ping redis

# Restart Celery worker
docker-compose restart celery-worker
```

**Disk Space Issues**
```bash
# Check Docker disk usage
docker system df

# Clean up unused containers, images, volumes
docker system prune -a --volumes

# Remove only stopped containers and unused images
docker system prune
```

For detailed Docker documentation, see [DOCKER.md](DOCKER.md).

## Celery Distributed Task Queue

The application uses Celery for asynchronous webhook processing, enabling horizontal scalability and reliable task execution.

### Architecture Overview

The system implements a dual async processing architecture:

1. **Thread-based Queue**: Provides immediate response to webhook requests
2. **Celery Task Queue**: Enables distributed processing and horizontal scaling

```
GitHub Webhook → Flask App → Thread Queue → MongoDB
                     ↓
                Celery Task → Redis Broker → Celery Worker → MongoDB
```

**Key Components:**
- **Message Broker (Redis)**: Queues tasks for worker consumption
- **Celery Workers**: Process tasks asynchronously in separate containers
- **Result Backend (Redis)**: Stores task execution results and status
- **Celery Beat**: Scheduler for periodic tasks (optional)

For detailed architecture documentation, see [docs/CELERY_ARCHITECTURE.md](docs/CELERY_ARCHITECTURE.md).

### Scaling Celery Workers

Scale workers horizontally to handle increased load:

```bash
# Scale to 3 worker containers
docker-compose up --scale celery-worker=3 -d

# Scale to 5 workers
docker-compose up --scale celery-worker=5 -d

# Scale back to 1 worker
docker-compose up --scale celery-worker=1 -d
```

**Worker Concurrency:**

Each worker container runs multiple concurrent processes. Configure in `.env`:

```bash
# Number of concurrent processes per worker (default: 4)
CELERY_WORKER_CONCURRENCY=4
```

**Scaling Guidelines:**
- Start with 1-2 workers for development
- Scale to 3-5 workers for moderate production load
- Monitor CPU and memory usage to determine optimal worker count
- Each worker consumes ~200-500MB RAM depending on workload

### Monitoring Celery Tasks

**View Worker Status:**
```bash
# Check worker logs
docker-compose logs -f celery-worker

# View worker status from inside container
docker-compose exec celery-worker celery -A app.celery_app inspect active

# View registered tasks
docker-compose exec celery-worker celery -A app.celery_app inspect registered

# View worker statistics
docker-compose exec celery-worker celery -A app.celery_app inspect stats
```

**Monitor Task Queue:**
```bash
# Check Redis queue length
docker-compose exec redis redis-cli llen celery

# View queued tasks
docker-compose exec redis redis-cli keys "celery-task-meta-*"
```

**Task Status Tracking:**

Query task status via API (if implemented):
```bash
# Get task status by task ID
curl http://localhost:5000/task/<task_id>
```

**Celery Flower (Optional Monitoring UI):**

Add Flower to docker-compose.yml for web-based monitoring:
```yaml
flower:
  image: mher/flower
  command: celery flower --broker=redis://redis:6379/0
  ports:
    - "5555:5555"
  depends_on:
    - redis
```

Access Flower at http://localhost:5555 for real-time task monitoring.

### Celery Task Retry Behavior

Tasks automatically retry on failure:
- **Max Retries**: 3 attempts
- **Retry Delay**: 60 seconds between attempts
- **Retry Conditions**: Transient errors (database timeout, network issues)
- **No Retry**: Permanent errors (invalid data, validation failures)

View retry attempts in worker logs:
```bash
docker-compose logs celery-worker | grep "Retry"
```

### Celery Configuration

Key configuration options in `.env`:

```bash
# Redis broker URL
REDIS_URI=redis://redis:6379/0

# Worker concurrency (processes per worker)
CELERY_WORKER_CONCURRENCY=4

# Task retry settings
CELERY_MAX_RETRIES=3
CELERY_RETRY_DELAY=60

# Task timeout (seconds)
CELERY_TASK_TIMEOUT=300
```

For complete architecture details and concepts, see [docs/CELERY_ARCHITECTURE.md](docs/CELERY_ARCHITECTURE.md).

## Structured Logging

The application uses structured file-based logging for production observability and debugging.

### Log Format

All logs follow a consistent structured format:

```
YYYY-MM-DD HH:MM:SS | LEVEL | module_name | message
```

**Example Log Entries:**
```
2026-02-23 14:30:45 | INFO | webhook_handler | Webhook received: push event
2026-02-23 14:30:45 | INFO | queue_processor | Payload enqueued successfully
2026-02-23 14:30:46 | INFO | celery_tasks | Task process_webhook_task started
2026-02-23 14:30:46 | INFO | database | Event stored: 507f1f77bcf86cd799439011
2026-02-23 14:30:47 | ERROR | celery_tasks | Task failed: Connection timeout
```

**Log Levels:**
- **DEBUG**: Detailed diagnostic information
- **INFO**: General informational messages
- **WARNING**: Warning messages for potential issues
- **ERROR**: Error messages with stack traces

### Accessing Log Files

**Docker Deployment:**

Logs are mounted to the host filesystem in the `./logs` directory:

```bash
# View Flask application logs
cat logs/app.log
tail -f logs/app.log

# View Celery worker logs
cat logs/celery.log
tail -f logs/celery.log

# Search logs for errors
grep "ERROR" logs/app.log
grep "ERROR" logs/celery.log

# View logs with timestamps in specific range
grep "2026-02-23 14:" logs/app.log
```

**Local Development:**

Configure log file paths in `.env`:
```bash
LOG_FILE_PATH=/path/to/app.log
CELERY_LOG_FILE=/path/to/celery.log
```

### Log File Rotation

Logs automatically rotate to prevent disk space issues:

- **Max File Size**: 10MB per log file
- **Backup Count**: 5 backup files retained
- **Rotation Behavior**: When a log file reaches 10MB, it's renamed to `app.log.1`, and a new `app.log` is created
- **Old Logs**: Oldest backup (`app.log.5`) is deleted when rotation occurs

**Log Files:**
```
logs/
├── app.log          # Current Flask application log
├── app.log.1        # Previous Flask log (most recent backup)
├── app.log.2        # Older backup
├── celery.log       # Current Celery worker log
├── celery.log.1     # Previous Celery log
└── celery.log.2     # Older backup
```

### Configuring Log Levels

Set log level in `.env` to control verbosity:

```bash
# Production: minimal logging
LOG_LEVEL=INFO

# Development: detailed logging
LOG_LEVEL=DEBUG

# Troubleshooting: maximum detail
LOG_LEVEL=DEBUG
```

**Log Level Hierarchy:**
- `DEBUG`: Shows all messages (most verbose)
- `INFO`: Shows info, warning, and error messages
- `WARNING`: Shows warning and error messages
- `ERROR`: Shows only error messages (least verbose)

### Troubleshooting with Logs

**Common Debugging Scenarios:**

**1. Webhook Not Processing:**
```bash
# Check if webhook was received
grep "Webhook received" logs/app.log

# Check for validation errors
grep "ERROR" logs/app.log | grep "webhook"

# Check queue processing
grep "enqueued" logs/app.log
```

**2. Database Connection Issues:**
```bash
# Check database connection errors
grep "database" logs/app.log | grep "ERROR"

# Check MongoDB connection attempts
grep "MongoDB" logs/app.log
```

**3. Celery Task Failures:**
```bash
# View failed tasks
grep "Task failed" logs/celery.log

# View task retry attempts
grep "Retry" logs/celery.log

# Check for specific task errors
grep "process_webhook_task" logs/celery.log | grep "ERROR"
```

**4. Performance Issues:**
```bash
# Check for slow operations
grep "timeout" logs/app.log

# View task execution times
grep "Task.*completed" logs/celery.log
```

**5. Stack Traces for Errors:**

All errors include full stack traces for debugging:
```bash
# View complete error stack traces
grep -A 20 "ERROR" logs/app.log

# Find specific exception types
grep "Exception" logs/app.log
```

### Log Analysis Tips

**Real-time Monitoring:**
```bash
# Follow logs in real-time
tail -f logs/app.log logs/celery.log

# Follow only errors
tail -f logs/app.log | grep "ERROR"
```

**Log Aggregation:**
```bash
# Combine all logs chronologically
cat logs/app.log logs/celery.log | sort

# Count errors by type
grep "ERROR" logs/app.log | cut -d'|' -f4 | sort | uniq -c
```

**Time-based Analysis:**
```bash
# View logs from specific time period
grep "2026-02-23 14:" logs/app.log

# Count events per hour
grep "2026-02-23" logs/app.log | cut -d' ' -f2 | cut -d':' -f1 | sort | uniq -c
```

### Viewing Logs in Docker

```bash
# Stream logs from all containers
docker-compose logs -f

# Stream logs from specific service
docker-compose logs -f flask-app
docker-compose logs -f celery-worker

# View last 100 lines
docker-compose logs --tail=100 flask-app

# View logs since specific time
docker-compose logs --since 2026-02-23T14:00:00 flask-app
```


## Local Development Setup

### 1. Clone and Setup Repository

```bash
# Clone this repository
git clone <repository-url>
cd webhook-repo

# Create and activate virtual environment
python -m venv venv

# On Windows
venv\Scripts\activate

# On macOS/Linux
source venv/bin/activate
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Environment Configuration

```bash
# Copy environment template
cp .env.example .env

# Edit .env file with your configuration
# See Environment Variables section below for details
```

### 4. Database Setup

**Option A: Local MongoDB**
```bash
# Start MongoDB service
# On Windows (if installed as service):
net start MongoDB

# On macOS (with Homebrew):
brew services start mongodb-community

# On Linux:
sudo systemctl start mongod
```

**Option B: MongoDB Atlas (Cloud)**
1. Create account at [MongoDB Atlas](https://www.mongodb.com/atlas)
2. Create a new cluster (free tier available)
3. Create database user with read/write permissions
4. Get connection string and update `MONGODB_URI` in `.env`

### 5. Verify Setup

```bash
# Start the application
python run.py

# Check health endpoint
curl http://localhost:5000/health
```

## GitHub Webhook Configuration

### 1. Create Action Repository

Create a separate GitHub repository that will generate webhook events:

```bash
# Create a new repository on GitHub (action-repo)
git clone https://github.com/yourusername/action-repo.git
cd action-repo

# Add some initial content
echo "# Action Repository" > README.md
git add README.md
git commit -m "Initial commit"
git push origin main
```

### 2. Configure Webhook in Action Repository

1. Go to your action repository on GitHub
2. Navigate to **Settings** → **Webhooks**
3. Click **Add webhook**
4. Configure webhook settings:
   - **Payload URL**: `https://your-ngrok-url.ngrok.io/webhook`
   - **Content type**: `application/json`
   - **Secret**: (optional) Use value from `GITHUB_WEBHOOK_SECRET` in `.env`
   - **Events**: Select "Let me select individual events"
     - ✅ Pushes
     - ✅ Pull requests
   - **Active**: ✅ Checked

### 3. Test Webhook Delivery

After setup, test by:
- Pushing commits to action repository
- Creating pull requests
- Merging pull requests

Check webhook deliveries in GitHub Settings → Webhooks → Recent Deliveries

## ngrok Setup and Usage

### 1. Install and Setup ngrok

```bash
# Download ngrok from https://ngrok.com/download
# Extract and move to PATH, or install via package manager

# On macOS with Homebrew:
brew install ngrok/ngrok/ngrok

# On Windows with Chocolatey:
choco install ngrok

# Authenticate with your ngrok token
ngrok config add-authtoken YOUR_AUTHTOKEN_HERE
```

### 2. Expose Local Flask Application

```bash
# Start your Flask application first
python run.py

# In a new terminal, expose port 5000
ngrok http 5000
```

### 3. Use ngrok URL for Webhooks

ngrok will provide URLs like:
```
Forwarding  https://abc123.ngrok.io -> http://localhost:5000
```

Use the HTTPS URL (`https://abc123.ngrok.io/webhook`) as your GitHub webhook URL.

**Important Notes:**
- Free ngrok URLs change each time you restart ngrok
- Update GitHub webhook URL when ngrok URL changes
- Consider ngrok paid plans for stable URLs in production

## Running the Application

### Development Mode

```bash
# Ensure virtual environment is activated
source venv/bin/activate  # or venv\Scripts\activate on Windows

# Start Flask application
python run.py

# Application will be available at:
# - Main UI: http://localhost:5000
# - Health check: http://localhost:5000/health
# - Events API: http://localhost:5000/events
# - Webhook endpoint: http://localhost:5000/webhook
```

### Production Considerations

For production deployment, consider:
- Use WSGI server like Gunicorn instead of Flask dev server
- Set `FLASK_DEBUG=False` in environment
- Use proper MongoDB connection with authentication
- Implement proper logging and monitoring
- Use reverse proxy (nginx) for SSL termination

## Testing

### Running Tests

```bash
# Run all tests
python -m pytest

# Run specific test files
python -m pytest test_webhook_processing.py
python -m pytest test_database.py

# Run with verbose output
python -m pytest -v

# Run property-based tests with specific iterations
python -m pytest test_webhook_processing.py::test_property_* -v
```

### Test Categories

1. **Unit Tests**: Test individual components
   - Database operations
   - Webhook payload processing
   - API endpoints

2. **Property-Based Tests**: Test universal properties using Hypothesis
   - Event type detection across random payloads
   - Field extraction completeness
   - Timestamp format consistency

3. **Integration Tests**: Test end-to-end flows
   - Webhook to database storage
   - API endpoint responses
   - UI polling behavior

### Manual Testing

Test webhook processing manually:

```bash
# Send test webhook payload
curl -X POST http://localhost:5000/webhook \
  -H "Content-Type: application/json" \
  -H "X-GitHub-Event: push" \
  -d @test_payloads/push_event.json

# Check events API
curl http://localhost:5000/events

# Test the web interface
# Open http://localhost:5000 in your browser
```

## Troubleshooting

### Common Issues

**1. MongoDB Connection Failed**
```
Error: ServerSelectionTimeoutError
```
- Verify MongoDB is running: `mongod --version`
- Check connection string in `.env`
- For Atlas: verify network access and credentials
- Check logs: `grep "MongoDB" logs/app.log`

**2. Webhook Not Receiving Events**
```
GitHub shows webhook delivery failed
```
- Verify ngrok is running and URL is correct
- Check Flask application is running on correct port
- Verify webhook URL in GitHub settings
- Check ngrok web interface at http://127.0.0.1:4040
- Review logs: `grep "webhook" logs/app.log`

**3. Import Errors**
```
ModuleNotFoundError: No module named 'flask'
```
- Verify virtual environment is activated
- Reinstall dependencies: `pip install -r requirements.txt`

**4. Environment Variables Not Loading**
```
KeyError: 'MONGODB_URI'
```
- Verify `.env` file exists and contains required variables
- Check file is in same directory as `run.py`
- Verify python-dotenv is installed

**5. Celery Worker Not Processing Tasks**
```
Tasks queued but not executing
```
- Check Celery worker logs: `docker-compose logs celery-worker`
- Verify Redis connection: `docker-compose exec celery-worker ping redis`
- Restart worker: `docker-compose restart celery-worker`
- Check task queue: `docker-compose exec redis redis-cli llen celery`

**6. Log Files Not Created**
```
Logs directory empty or missing log files
```
- Verify logs directory exists: `mkdir -p logs`
- Check LOG_FILE_PATH in `.env`
- Verify Docker volume mount in docker-compose.yml
- Check file permissions on logs directory

### Debug Mode

Enable debug logging by setting in `.env`:
```
FLASK_DEBUG=True
LOG_LEVEL=DEBUG
```

### Webhook Debugging

1. **Check ngrok requests**: Visit http://127.0.0.1:4040 for request inspection
2. **GitHub webhook deliveries**: Check Settings → Webhooks → Recent Deliveries
3. **Application logs**: Check `logs/app.log` for webhook processing
4. **Database inspection**: Use MongoDB Compass or CLI to verify data storage
5. **Celery tasks**: Check `logs/celery.log` for task execution

### Performance Issues

**High Memory Usage**
- Check for database connection leaks
- Monitor MongoDB connection pool
- Review log file sizes: `du -sh logs/`
- Check Docker container stats: `docker stats`

**Slow Response Times**
- Check database query performance in logs
- Verify MongoDB indexes
- Monitor network latency to MongoDB
- Check Celery queue length: `docker-compose exec redis redis-cli llen celery`

### Log-Based Troubleshooting

For detailed log analysis and troubleshooting techniques, see the [Structured Logging](#structured-logging) section above.

**Quick Log Commands:**
```bash
# View recent errors
tail -100 logs/app.log | grep "ERROR"

# Monitor logs in real-time
tail -f logs/app.log logs/celery.log

# Search for specific issues
grep "Connection" logs/app.log
grep "timeout" logs/celery.log
```

### Getting Help

1. Check application logs for error details: `cat logs/app.log`
2. Verify all environment variables are set correctly
3. Test individual components (database, webhook endpoint, UI)
4. Use GitHub webhook delivery logs for debugging
5. Check ngrok request logs for payload inspection
6. Review Celery worker logs: `cat logs/celery.log`

## Environment Variables

All environment variables should be defined in `.env` file:

### Required Variables

```bash
# MongoDB Configuration
MONGODB_URI=mongodb://localhost:27017/webhook_system
MONGODB_DATABASE=webhook_system

# Redis Configuration (for Celery)
REDIS_URI=redis://localhost:6379/0

# Flask Configuration
FLASK_DEBUG=True
FLASK_PORT=5000
SECRET_KEY=your-secret-key-here
```

### Optional Variables

```bash
# Flask Environment
FLASK_ENV=development

# Logging Configuration
LOG_LEVEL=INFO
LOG_FILE_PATH=logs/app.log
CELERY_LOG_FILE=logs/celery.log

# Celery Configuration
CELERY_WORKER_CONCURRENCY=4
CELERY_MAX_RETRIES=3
CELERY_RETRY_DELAY=60
CELERY_TASK_TIMEOUT=300

# Queue Configuration
WORKER_THREADS=4
QUEUE_MAX_SIZE=1000

# GitHub Webhook Security (recommended)
GITHUB_WEBHOOK_SECRET=your-webhook-secret-here
```

### Variable Descriptions

**Database & Broker:**
- **MONGODB_URI**: Full MongoDB connection string including credentials
- **MONGODB_DATABASE**: Database name for storing webhook events
- **REDIS_URI**: Redis connection string for Celery message broker

**Flask:**
- **FLASK_DEBUG**: Enable/disable Flask debug mode (True/False)
- **FLASK_PORT**: Port number for Flask application (default: 5000)
- **SECRET_KEY**: Flask secret key for session security (generate random string)

**Logging:**
- **LOG_LEVEL**: Logging level (DEBUG, INFO, WARNING, ERROR)
- **LOG_FILE_PATH**: Path to Flask application log file
- **CELERY_LOG_FILE**: Path to Celery worker log file

**Celery:**
- **CELERY_WORKER_CONCURRENCY**: Number of concurrent processes per worker (default: 4)
- **CELERY_MAX_RETRIES**: Maximum task retry attempts (default: 3)
- **CELERY_RETRY_DELAY**: Seconds between retry attempts (default: 60)
- **CELERY_TASK_TIMEOUT**: Task execution timeout in seconds (default: 300)

**Queue:**
- **WORKER_THREADS**: Number of background worker threads (default: 4)
- **QUEUE_MAX_SIZE**: Maximum queue size before blocking (default: 1000)

**Security:**
- **GITHUB_WEBHOOK_SECRET**: Optional secret for webhook payload validation

## API Endpoints

### GET /health
Health check endpoint for monitoring application status.

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2021-04-01T21:30:00Z",
  "database": "connected"
}
```

### POST /webhook
Receives GitHub webhook payloads for processing.

**Headers:**
- `X-GitHub-Event`: Event type (push, pull_request)
- `Content-Type`: application/json

**Response:**
- `200 OK`: Event processed successfully
- `400 Bad Request`: Invalid payload format
- `500 Internal Server Error`: Processing error

### GET /events
Returns processed webhook events for UI display.

**Response:**
```json
[
  {
    "request_id": "abc123",
    "author": "username",
    "action": "PUSH",
    "from_branch": "",
    "to_branch": "main",
    "timestamp": "2021-04-01T21:30:00Z"
  }
]
```

Events are sorted by timestamp in descending order (latest first).