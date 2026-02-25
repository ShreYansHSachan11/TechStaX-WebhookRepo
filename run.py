#!/usr/bin/env python3
"""
GitHub Webhook System - Main Entry Point

This script starts the Flask application for the GitHub Webhook System.
It handles environment configuration, database initialization, and starts the server.

Usage:
    python run.py

Environment Variables:
    MONGODB_URI: MongoDB connection string
    MONGODB_DATABASE: MongoDB database name
    SECRET_KEY: Flask secret key
    FLASK_DEBUG: Enable/disable debug mode (True/False)
    FLASK_PORT: Port number (default: 5000)
    LOG_LEVEL: Logging level (DEBUG, INFO, WARNING, ERROR)
"""

import os
from datetime import datetime
from flask import Flask, request, jsonify, render_template

# Import configuration module (loads and validates config on import)
from app.config import Config

# Import webhook system modules
from app.webhook import (
    setup_logging, get_logger, get_webhook_handler, 
    initialize_database, get_database_connection
)
from app.webhook.queue_processor import (
    initialize_webhook_queue, get_webhook_queue, shutdown_webhook_queue
)

def create_app():
    """
    Create and configure the Flask application.
    
    Returns:
        Flask: Configured Flask application instance
    """
    # Create Flask app
    app = Flask(__name__, 
                static_folder='app/static',
                template_folder='app/templates')
    
    # Configure the application
    configure_app(app)
    
    # Initialize logging using centralized config
    setup_logging()
    logger = get_logger(__name__)
    
    # Initialize database
    if not initialize_database():
        logger.error("Database initialization failed")
    
    # Initialize webhook queue with background workers using centralized config
    initialize_webhook_queue(max_size=Config.WEBHOOK_QUEUE_MAX_SIZE, num_workers=Config.WEBHOOK_QUEUE_WORKERS)
    logger.info(f"Webhook queue initialized with {Config.WEBHOOK_QUEUE_WORKERS} workers and max size {Config.WEBHOOK_QUEUE_MAX_SIZE}")
    
    # Register shutdown handler to drain queue on app termination
    import atexit
    atexit.register(lambda: shutdown_webhook_queue(timeout=30))
    logger.info("Registered shutdown handler for webhook queue")
    
    # Register routes
    register_routes(app)
    
    logger.info("Flask application created and configured successfully")
    return app

def configure_app(app):
    """Configure Flask application settings using centralized config."""
    # Configuration validation already done in Config.load()
    # Print configuration summary
    Config.print_summary()
    
    # Flask configuration using centralized config
    app.config['SECRET_KEY'] = Config.SECRET_KEY
    app.config['DEBUG'] = Config.FLASK_DEBUG
    
    # Optional configurations
    if Config.MAX_CONTENT_LENGTH:
        app.config['MAX_CONTENT_LENGTH'] = Config.MAX_CONTENT_LENGTH

def register_routes(app):
    """Register all application routes."""
    logger = get_logger(__name__)
    
    @app.route('/')
    def index():
        """Serve the main UI page."""
        logger.info("Serving main UI page")
        return render_template('index.html')
    
    @app.route('/health')
    def health():
        """Health check endpoint."""
        logger.info("Health check requested")
        
        # Check database connection
        db_conn = get_database_connection()
        db_status = "connected" if db_conn and db_conn.is_connected() else "disconnected"
        
        health_data = {
            "status": "healthy" if db_status == "connected" else "degraded",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "database": db_status,
            "version": "1.0.0"
        }
        
        status_code = 200 if db_status == "connected" else 503
        logger.info(f"Health check completed - Status: {health_data['status']}")
        
        return jsonify(health_data), status_code
    
    @app.route('/webhook', methods=['POST'])
    def webhook():
        """Handle GitHub webhook requests."""
        logger.info("Received webhook request")
        
        try:
            # Get event type from header
            event_type = request.headers.get('X-GitHub-Event')
            if not event_type:
                logger.warning("Missing X-GitHub-Event header")
                return jsonify({
                    "status": "error",
                    "message": "Missing X-GitHub-Event header"
                }), 400
            
            # Wrap payload parsing in try-except block (Requirement 6.1)
            try:
                payload = request.get_json()
                if not payload:
                    logger.error("Invalid JSON payload")
                    return jsonify({
                        "status": "error",
                        "message": "Invalid or empty JSON payload"
                    }), 400
            except Exception as parse_error:
                logger.error(f"Error parsing webhook payload: {parse_error}", exc_info=True)
                return jsonify({
                    "status": "error",
                    "message": "Failed to parse JSON payload"
                }), 400
            
            # Get webhook queue
            webhook_queue = get_webhook_queue()
            if not webhook_queue:
                logger.error("Webhook queue not initialized")
                return jsonify({
                    "status": "error",
                    "message": "Webhook processing system unavailable"
                }), 503
            
            # Wrap queue operations in try-except block (Requirement 6.4)
            try:
                enqueued = webhook_queue.enqueue(payload, event_type)
                
                if not enqueued:
                    logger.warning(f"Failed to enqueue {event_type} event - queue may be full")
                    return jsonify({
                        "status": "error",
                        "message": "Webhook queue is full, please retry later"
                    }), 503
            except Exception as queue_error:
                logger.error(f"Error enqueuing to webhook queue: {queue_error}", exc_info=True)
                return jsonify({
                    "status": "error",
                    "message": "Failed to enqueue webhook for processing"
                }), 500
            
            # Wrap Celery task enqueuing in try-except block (Requirement 6.4)
            try:
                from app.celery_app import process_webhook_task
                task = process_webhook_task.delay(payload, event_type)
                logger.info(f"Successfully enqueued Celery task for {event_type} event - Task ID: {task.id}")
            except Exception as celery_error:
                # Log Celery connection error but don't fail the request
                # Thread queue processing will still handle the webhook
                logger.error(f"Failed to enqueue Celery task: {celery_error}", exc_info=True)
                logger.warning("Webhook will be processed via thread queue only")
            
            # Return immediate success response without blocking (Requirement 6.8)
            logger.info(f"Successfully enqueued {event_type} event for async processing")
            return jsonify({
                "status": "success",
                "message": "Webhook received and queued for processing"
            }), 200
            
        except Exception as e:
            # Return safe HTTP error response on exceptions (Requirement 6.8)
            logger.error(f"Unexpected error processing webhook: {e}", exc_info=True)
            return jsonify({
                "status": "error",
                "message": "Internal server error"
            }), 500
    
    @app.route('/events', methods=['GET'])
    def events():
        """Get webhook events from the last 15 seconds for UI display."""
        logger.info("Received request for events")
        
        try:
            # Get database connection
            db_conn = get_database_connection()
            if not db_conn or not db_conn.is_connected():
                logger.error("Database connection unavailable for events request")
                response = jsonify({
                    "status": "error",
                    "message": "Database connection unavailable",
                    "events": [],
                    "count": 0
                })
                # Add CORS headers even for error responses
                response.headers['Access-Control-Allow-Origin'] = '*'
                response.headers['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
                response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
                return response, 503
            
            # Retrieve events from last 15 seconds (time-windowed filtering)
            events_data = db_conn.get_recent_events(15)
            event_count = len(events_data)
            
            logger.info(f"Successfully returned {event_count} events")
            
            response = jsonify({
                "status": "success",
                "events": events_data,
                "count": event_count
            })
            
            # Add CORS headers for frontend access
            response.headers['Access-Control-Allow-Origin'] = '*'
            response.headers['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
            response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
            
            return response, 200
            
        except Exception as e:
            logger.error(f"Error retrieving events: {e}")
            response = jsonify({
                "status": "error", 
                "message": "Failed to retrieve events",
                "events": [],
                "count": 0
            })
            # Add CORS headers even for error responses
            response.headers['Access-Control-Allow-Origin'] = '*'
            response.headers['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
            response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
            return response, 500
    
    @app.route('/events', methods=['OPTIONS'])
    def events_options():
        """Handle CORS preflight requests for events endpoint."""
        response = jsonify({})
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
        return response, 200
    
    @app.route('/task/<task_id>', methods=['GET'])
    def task_status(task_id):
        """
        Get Celery task status and result.
        
        Query the Celery result backend for task status, result, and error information.
        
        Args:
            task_id: Celery task ID from the URL path
            
        Returns:
            JSON response with task status, result, and error information
            
        Requirements: 3.10
        """
        logger.info(f"Received request for task status: {task_id}")
        
        try:
            from app.celery_app import celery_app
            from celery.result import AsyncResult
            
            # Query Celery result backend for task status
            task_result = AsyncResult(task_id, app=celery_app)
            
            # Build response based on task state
            response_data = {
                "task_id": task_id,
                "status": task_result.state,
                "result": None,
                "error": None,
                "traceback": None
            }
            
            # Add result or error information based on state
            if task_result.state == 'PENDING':
                # Task is waiting to be executed
                response_data["message"] = "Task is pending execution"
                
            elif task_result.state == 'STARTED':
                # Task has been started
                response_data["message"] = "Task is currently executing"
                
            elif task_result.state == 'SUCCESS':
                # Task completed successfully
                response_data["result"] = task_result.result
                response_data["message"] = "Task completed successfully"
                
            elif task_result.state == 'FAILURE':
                # Task failed with an exception
                response_data["error"] = str(task_result.info)
                response_data["traceback"] = task_result.traceback
                response_data["message"] = "Task failed with an error"
                
            elif task_result.state == 'RETRY':
                # Task is being retried
                response_data["error"] = str(task_result.info)
                response_data["message"] = "Task is being retried after failure"
                
            elif task_result.state == 'REVOKED':
                # Task was revoked/cancelled
                response_data["message"] = "Task was revoked"
                
            else:
                # Unknown state
                response_data["message"] = f"Task is in state: {task_result.state}"
            
            logger.info(f"Task {task_id} status: {task_result.state}")
            
            return jsonify(response_data), 200
            
        except Exception as e:
            logger.error(f"Error retrieving task status for {task_id}: {e}", exc_info=True)
            return jsonify({
                "status": "error",
                "message": "Failed to retrieve task status",
                "task_id": task_id
            }), 500
    
    @app.errorhandler(404)
    def not_found(error):
        """Handle 404 errors."""
        logger.warning(f"404 error: {request.url}")
        return jsonify({
            "status": "error",
            "message": "Endpoint not found"
        }), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        """Handle 500 errors."""
        logger.error(f"500 error: {error}")
        return jsonify({
            "status": "error",
            "message": "Internal server error"
        }), 500

def main():
    """Main entry point for the application."""
    # Create Flask application
    app = create_app()
    
    # Get configuration from centralized config
    debug = Config.FLASK_DEBUG
    port = Config.FLASK_PORT
    host = Config.FLASK_HOST
    
    # Start the application
    print(f"🚀 Starting GitHub Webhook System on http://{host}:{port}")
    print(f"📊 Debug mode: {'enabled' if debug else 'disabled'}")
    print(f"🌐 Access the UI at: http://localhost:{port}")
    print(f"🔗 Webhook endpoint: http://localhost:{port}/webhook")
    print("Press Ctrl+C to stop the server")
    
    app.run(
        host=host,
        port=port,
        debug=debug,
        threaded=True
    )

if __name__ == '__main__':
    main()