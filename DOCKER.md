# Docker Setup Guide

This guide explains how to run the GitHub Webhook System using Docker and Docker Compose.

## Prerequisites

- Docker Engine 20.10 or higher
- Docker Compose 2.0 or higher

## Quick Start

1. **Clone the repository and navigate to the project directory**

```bash
cd webhook-repo
```

2. **Create environment configuration**

```bash
cp .env.example .env
```

Edit `.env` and configure the required variables. For Docker deployment, use these values:

```env
MONGODB_URI=mongodb://mongodb:27017/webhook_db
REDIS_URI=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/1
```

3. **Build and start all services**

```bash
docker-compose up --build
```

This will start:
- Flask application (port 5000)
- MongoDB database (port 27017)
- Redis message broker (port 6379)
- Celery worker
- Celery beat scheduler

4. **Access the application**

- Web UI: http://localhost:5000
- Webhook endpoint: http://localhost:5000/webhook
- Health check: http://localhost:5000/health

## Docker Services

### flask-app
- **Purpose**: Main Flask web application
- **Port**: 5000
- **Health Check**: HTTP GET to /health endpoint
- **Logs**: `./logs/app.log`

### mongodb
- **Purpose**: Database for storing webhook events
- **Port**: 27017
- **Data Volume**: `mongodb_data`
- **Health Check**: MongoDB ping command

### redis
- **Purpose**: Message broker for Celery tasks
- **Port**: 6379
- **Data Volume**: `redis_data`
- **Health Check**: Redis ping command

### celery-worker
- **Purpose**: Asynchronous task processing
- **Concurrency**: 4 workers (configurable)
- **Logs**: `./logs/celery.log`
- **Health Check**: Celery inspect ping

### celery-beat
- **Purpose**: Periodic task scheduler
- **Logs**: `./logs/celery_beat.log`

## Common Commands

### Start services in detached mode
```bash
docker-compose up -d
```

### Stop all services
```bash
docker-compose down
```

### Stop and remove volumes (clean slate)
```bash
docker-compose down -v
```

### View logs
```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f flask-app
docker-compose logs -f celery-worker
```

### Rebuild after code changes
```bash
docker-compose up --build
```

### Scale Celery workers
```bash
docker-compose up --scale celery-worker=3
```

### Check service health
```bash
docker-compose ps
```

## Volume Mounts

### Application Logs
- **Host**: `./logs`
- **Container**: `/app/logs`
- **Purpose**: Access logs from host system

### Application Code (Development)
- **Host**: `./app`
- **Container**: `/app/app`
- **Purpose**: Hot reload during development

### MongoDB Data
- **Volume**: `mongodb_data`
- **Purpose**: Persistent database storage

### Redis Data
- **Volume**: `redis_data`
- **Purpose**: Persistent message queue data

## Networking

All services communicate via the `webhook-network` bridge network:

```
flask-app <-> mongodb (mongodb:27017)
flask-app <-> redis (redis:6379)
celery-worker <-> mongodb (mongodb:27017)
celery-worker <-> redis (redis:6379)
celery-beat <-> redis (redis:6379)
```

## Environment Variables

Key environment variables for Docker deployment:

| Variable | Default | Description |
|----------|---------|-------------|
| FLASK_PORT | 5000 | Flask application port |
| MONGODB_URI | mongodb://mongodb:27017/webhook_db | MongoDB connection string |
| REDIS_URI | redis://redis:6379/0 | Redis connection string |
| CELERY_BROKER_URL | redis://redis:6379/0 | Celery message broker |
| CELERY_RESULT_BACKEND | redis://redis:6379/1 | Celery result storage |
| LOG_FILE_PATH | /app/logs/app.log | Application log file path |
| LOG_LEVEL | INFO | Logging level |
| WORKER_THREADS | 4 | Number of background worker threads |
| QUEUE_MAX_SIZE | 1000 | Maximum queue size |
| CELERY_WORKER_CONCURRENCY | 4 | Celery worker processes |

## Health Checks

All critical services have health checks configured:

- **Flask App**: HTTP GET to /health (30s interval)
- **MongoDB**: mongosh ping command (10s interval)
- **Redis**: redis-cli ping (10s interval)
- **Celery Worker**: celery inspect ping (30s interval)

Unhealthy containers will be automatically restarted by Docker.

## Troubleshooting

### Services won't start
```bash
# Check service status
docker-compose ps

# View logs for errors
docker-compose logs

# Ensure ports are not in use
netstat -an | grep -E "5000|27017|6379"
```

### Database connection errors
```bash
# Verify MongoDB is healthy
docker-compose exec mongodb mongosh --eval "db.adminCommand('ping')"

# Check MongoDB logs
docker-compose logs mongodb
```

### Celery tasks not processing
```bash
# Check Celery worker status
docker-compose exec celery-worker celery -A app.celery_app inspect active

# View Celery logs
docker-compose logs celery-worker
```

### Permission issues with logs
```bash
# Fix log directory permissions
chmod -R 777 logs/
```

### Clean rebuild
```bash
# Remove all containers, volumes, and images
docker-compose down -v --rmi all

# Rebuild from scratch
docker-compose up --build
```

## Production Deployment

For production deployment, consider:

1. **Use production WSGI server** (Gunicorn instead of Flask dev server)
2. **Enable authentication** for MongoDB and Redis
3. **Use secrets management** for sensitive environment variables
4. **Configure resource limits** in docker-compose.yml
5. **Set up log aggregation** (ELK stack, Splunk, etc.)
6. **Enable TLS/SSL** for external connections
7. **Use Docker Swarm or Kubernetes** for orchestration
8. **Set up monitoring** (Prometheus, Grafana)
9. **Configure backup strategy** for volumes

## Development Workflow

1. Make code changes in `./app` directory
2. Changes are automatically reflected (volume mount)
3. For dependency changes, rebuild: `docker-compose up --build`
4. View logs in `./logs` directory
5. Test with: `curl -X POST http://localhost:5000/webhook`

## Additional Resources

- [Docker Documentation](https://docs.docker.com/)
- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [Celery Documentation](https://docs.celeryproject.org/)
- [MongoDB Docker Hub](https://hub.docker.com/_/mongo)
- [Redis Docker Hub](https://hub.docker.com/_/redis)
