# GitHub Webhook System

A minimal event processing pipeline that captures GitHub repository events (Push, Pull Request, Merge) from a source repository, processes them through a Flask backend, stores essential data in MongoDB, and displays events in a clean UI with 15-second polling updates.

## Table of Contents

- [Project Structure](#project-structure)
- [Prerequisites](#prerequisites)
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
├── app.py                    # Flask application entry point
├── webhook_handler.py        # Webhook processing logic
├── database.py              # MongoDB connection and operations
├── models.py                # Data models and validation
├── logging_config.py        # Logging configuration
├── static/                  # CSS, JavaScript files
│   ├── css/
│   │   └── style.css
│   └── js/
│       └── app.js
├── templates/               # HTML templates
│   └── index.html
├── requirements.txt         # Python dependencies
├── .env.example            # Environment variables template
├── test_*.py               # Test files
└── README.md               # This file
```

## Prerequisites

- **Python 3.8 or higher**: Download from [python.org](https://www.python.org/downloads/)
- **MongoDB**: Choose one of the following:
  - Local installation: [MongoDB Community Server](https://www.mongodb.com/try/download/community)
  - Cloud: [MongoDB Atlas](https://www.mongodb.com/atlas) (free tier available)
- **ngrok**: For exposing local server to GitHub webhooks
  - Download from [ngrok.com](https://ngrok.com/download)
  - Create free account for authentication token
- **Git**: For version control and GitHub integration

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
python app.py

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
python app.py

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
python app.py

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

**2. Webhook Not Receiving Events**
```
GitHub shows webhook delivery failed
```
- Verify ngrok is running and URL is correct
- Check Flask application is running on correct port
- Verify webhook URL in GitHub settings
- Check ngrok web interface at http://127.0.0.1:4040

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
- Check file is in same directory as `app.py`
- Verify python-dotenv is installed

### Debug Mode

Enable debug logging by setting in `.env`:
```
FLASK_DEBUG=True
LOG_LEVEL=DEBUG
```

### Webhook Debugging

1. **Check ngrok requests**: Visit http://127.0.0.1:4040 for request inspection
2. **GitHub webhook deliveries**: Check Settings → Webhooks → Recent Deliveries
3. **Application logs**: Check console output or log files
4. **Database inspection**: Use MongoDB Compass or CLI to verify data storage

### Performance Issues

**High Memory Usage**
- Check for database connection leaks
- Monitor MongoDB connection pool
- Review log file sizes

**Slow Response Times**
- Check database query performance
- Verify MongoDB indexes
- Monitor network latency to MongoDB

### Getting Help

1. Check application logs for error details
2. Verify all environment variables are set correctly
3. Test individual components (database, webhook endpoint, UI)
4. Use GitHub webhook delivery logs for debugging
5. Check ngrok request logs for payload inspection

## Environment Variables

All environment variables should be defined in `.env` file:

### Required Variables

```bash
# MongoDB Configuration
MONGODB_URI=mongodb://localhost:27017/webhook_system
MONGODB_DATABASE=webhook_system

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
LOG_FILE=/path/to/logfile.log

# GitHub Webhook Security (recommended)
GITHUB_WEBHOOK_SECRET=your-webhook-secret-here
```

### Variable Descriptions

- **MONGODB_URI**: Full MongoDB connection string including credentials
- **MONGODB_DATABASE**: Database name for storing webhook events
- **FLASK_DEBUG**: Enable/disable Flask debug mode (True/False)
- **FLASK_PORT**: Port number for Flask application (default: 5000)
- **SECRET_KEY**: Flask secret key for session security (generate random string)
- **LOG_LEVEL**: Logging level (DEBUG, INFO, WARNING, ERROR)
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