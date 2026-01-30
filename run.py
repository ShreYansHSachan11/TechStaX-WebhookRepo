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
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import webhook system modules
from app.webhook import (
    setup_logging, get_logger, get_webhook_handler, 
    initialize_database, get_database_connection
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
    
    # Initialize logging
    setup_logging()
    logger = get_logger(__name__)
    
    # Initialize database
    if not initialize_database():
        logger.error("Database initialization failed")
    
    # Register routes
    register_routes(app)
    
    logger.info("Flask application created and configured successfully")
    return app

def configure_app(app):
    """Configure Flask application settings."""
    # Validate required environment variables
    required_vars = ['MONGODB_URI', 'MONGODB_DATABASE', 'SECRET_KEY']
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        print("❌ Configuration Validation Failed")
        print("=" * 50)
        print()
        print("🚫 Missing Required Environment Variables:")
        for var in missing_vars:
            descriptions = {
                'MONGODB_URI': 'MongoDB connection string',
                'MONGODB_DATABASE': 'MongoDB database name', 
                'SECRET_KEY': 'Flask secret key for session security'
            }
            print(f"  - {var}: {descriptions.get(var, 'Required configuration')}")
        print()
        print("Please copy .env.example to .env and configure the required variables.")
        print()
        print("📖 See README.md for detailed setup instructions.")
        print("=" * 50)
        exit(1)
    
    # Configuration validation passed
    print("✅ Configuration validation passed")
    print("📋 Configuration Summary:")
    print(f"  - MONGODB_DATABASE: {os.getenv('MONGODB_DATABASE')}")
    print(f"  - FLASK_DEBUG: {os.getenv('FLASK_DEBUG', 'false').lower()}")
    print(f"  - FLASK_PORT: {os.getenv('FLASK_PORT', '5000')}")
    print(f"  - FLASK_ENV: {os.getenv('FLASK_ENV', 'development')}")
    print(f"  - LOG_LEVEL: {os.getenv('LOG_LEVEL', 'INFO')}")
    print(f"  - GITHUB_WEBHOOK_SECRET_SET: {'Yes' if os.getenv('GITHUB_WEBHOOK_SECRET') else 'No'}")
    print()
    
    # Flask configuration
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
    app.config['DEBUG'] = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    
    # Optional configurations
    max_content_length = os.getenv('MAX_CONTENT_LENGTH')
    if max_content_length:
        app.config['MAX_CONTENT_LENGTH'] = int(max_content_length)

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
            # Get database connection
            db_conn = get_database_connection()
            if not db_conn or not db_conn.is_connected():
                logger.error("Database connection unavailable")
                return jsonify({
                    "status": "error",
                    "message": "Database connection unavailable"
                }), 500
            
            # Process webhook using webhook handler
            webhook_handler = get_webhook_handler()
            event, status_code, message = webhook_handler.process_webhook(request)
            
            if event is None:
                logger.warning(f"Webhook processing failed: {message}")
                return jsonify({
                    "status": "error" if status_code >= 400 else "success",
                    "message": message
                }), status_code
            
            # Store event in database
            event_dict = event.to_dict()
            event_id = db_conn.insert_event(event_dict)
            
            if event_id is None:
                logger.error("Failed to store event in database")
                return jsonify({
                    "status": "error",
                    "message": "Failed to store event in database"
                }), 500
            
            logger.info(f"Successfully processed and stored {event.action.value} event")
            return jsonify({
                "status": "success",
                "message": "Webhook processed and stored successfully",
                "event_id": str(event_id)
            }), 200
            
        except Exception as e:
            logger.error(f"Unexpected error processing webhook: {e}")
            return jsonify({
                "status": "error",
                "message": "Internal server error"
            }), 500
    
    @app.route('/events', methods=['GET'])
    def events():
        """Get all webhook events for UI display."""
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
            
            # Retrieve events from database
            events_data = db_conn.get_all_events()
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
    
    # Get configuration from environment
    debug = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    port = int(os.getenv('FLASK_PORT', 5000))
    host = os.getenv('FLASK_HOST', '127.0.0.1')
    
    # Start the application
    print(f"🚀 Starting GitHub Webhook System on http://{host}:{port}")
    print(f"📊 Debug mode: {'enabled' if debug else 'disabled'}")
    print(f"🌐 Access the UI at: http://{host}:{port}")
    print(f"🔗 Webhook endpoint: http://{host}:{port}/webhook")
    print("Press Ctrl+C to stop the server")
    
    app.run(
        host=host,
        port=port,
        debug=debug,
        threaded=True
    )

if __name__ == '__main__':
    main()