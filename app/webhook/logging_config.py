"""
Logging configuration for the GitHub Webhook System.

This module provides structured logging configuration with appropriate
log levels, formatters, and handlers for debugging and monitoring.
"""

import logging
import logging.handlers
import os
import sys
from datetime import datetime


def setup_logging():
    """
    Set up structured logging configuration for the application.
    
    Configures logging with:
    - Structured log format with timestamps, levels, and context
    - Console handler for development
    - File handler for production (optional)
    - Appropriate log levels based on environment
    """
    # Get log level from environment (default to INFO)
    log_level_str = os.getenv('LOG_LEVEL', 'INFO').upper()
    log_levels = {
        'DEBUG': logging.DEBUG,
        'INFO': logging.INFO,
        'WARNING': logging.WARNING,
        'ERROR': logging.ERROR,
        'CRITICAL': logging.CRITICAL
    }
    log_level = log_levels.get(log_level_str, logging.INFO)
    
    # Create structured log format
    log_format = (
        '%(asctime)s - %(name)s - %(levelname)s - '
        '[%(filename)s:%(lineno)d] - %(message)s'
    )
    
    # Create formatter
    formatter = logging.Formatter(
        fmt=log_format,
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # Remove existing handlers to avoid duplicates
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Console handler for all environments
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # File handler for production (optional)
    log_file = os.getenv('LOG_FILE')
    if log_file:
        try:
            # Create log directory if it doesn't exist
            log_dir = os.path.dirname(log_file)
            if log_dir and not os.path.exists(log_dir):
                os.makedirs(log_dir, exist_ok=True)
            
            # Rotating file handler to prevent large log files
            file_handler = logging.handlers.RotatingFileHandler(
                log_file,
                maxBytes=10 * 1024 * 1024,  # 10MB
                backupCount=5
            )
            file_handler.setLevel(log_level)
            file_handler.setFormatter(formatter)
            root_logger.addHandler(file_handler)
            
            logging.info(f"File logging enabled: {log_file}")
            
        except Exception as e:
            logging.error(f"Failed to set up file logging: {e}")
    
    # Set specific log levels for third-party libraries
    logging.getLogger('pymongo').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('werkzeug').setLevel(logging.WARNING)
    
    # Log startup information
    logging.info("=" * 50)
    logging.info("GitHub Webhook System - Logging Initialized")
    logging.info(f"Log Level: {log_level_str}")
    logging.info(f"Python Version: {sys.version}")
    logging.info(f"Startup Time: {datetime.now().isoformat()}")
    logging.info("=" * 50)


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance with the specified name.
    
    Args:
        name: Logger name (typically __name__)
        
    Returns:
        logging.Logger: Configured logger instance
    """
    return logging.getLogger(name)


def log_request_info(request, logger: logging.Logger):
    """
    Log detailed request information for debugging.
    
    Args:
        request: Flask request object
        logger: Logger instance to use
    """
    try:
        logger.info(f"Request Details:")
        logger.info(f"  Method: {request.method}")
        logger.info(f"  URL: {request.url}")
        logger.info(f"  Remote Address: {request.remote_addr}")
        logger.info(f"  User Agent: {request.headers.get('User-Agent', 'Unknown')}")
        logger.info(f"  Content Type: {request.headers.get('Content-Type', 'Unknown')}")
        logger.info(f"  Content Length: {request.headers.get('Content-Length', 'Unknown')}")
        
        # Log GitHub-specific headers
        github_event = request.headers.get('X-GitHub-Event')
        if github_event:
            logger.info(f"  GitHub Event: {github_event}")
            
        github_delivery = request.headers.get('X-GitHub-Delivery')
        if github_delivery:
            logger.info(f"  GitHub Delivery ID: {github_delivery}")
            
    except Exception as e:
        logger.error(f"Error logging request info: {e}")


def log_database_operation(operation: str, details: str, logger: logging.Logger, success: bool = True):
    """
    Log database operation with structured information.
    
    Args:
        operation: Type of database operation (insert, query, connect, etc.)
        details: Additional details about the operation
        logger: Logger instance to use
        success: Whether the operation was successful
    """
    level = logging.INFO if success else logging.ERROR
    status = "SUCCESS" if success else "FAILED"
    
    logger.log(level, f"Database Operation [{operation.upper()}] - {status}: {details}")


def log_webhook_event(event_type: str, event_data: dict, logger: logging.Logger):
    """
    Log webhook event processing with structured information.
    
    Args:
        event_type: Type of webhook event (push, pull_request, etc.)
        event_data: Processed event data
        logger: Logger instance to use
    """
    try:
        logger.info(f"Webhook Event Processed:")
        logger.info(f"  Event Type: {event_type}")
        logger.info(f"  Author: {event_data.get('author', 'Unknown')}")
        logger.info(f"  Action: {event_data.get('action', 'Unknown')}")
        logger.info(f"  From Branch: {event_data.get('from_branch', 'N/A')}")
        logger.info(f"  To Branch: {event_data.get('to_branch', 'Unknown')}")
        logger.info(f"  Request ID: {event_data.get('request_id', 'Unknown')}")
        logger.info(f"  Timestamp: {event_data.get('timestamp', 'Unknown')}")
        
    except Exception as e:
        logger.error(f"Error logging webhook event: {e}")