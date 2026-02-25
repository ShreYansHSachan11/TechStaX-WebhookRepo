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
from app.config import Config


class StructuredFormatter(logging.Formatter):
    """
    Custom formatter for structured log output.
    
    Formats log records with the structure:
    YYYY-MM-DD HH:MM:SS | LEVEL | module_name | message
    """
    
    def format(self, record: logging.LogRecord) -> str:
        """
        Format log record with structured format.
        
        Args:
            record: Log record to format
            
        Returns:
            str: Formatted log string in the format:
                 YYYY-MM-DD HH:MM:SS | LEVEL | module_name | message
        """
        # Format timestamp
        timestamp = datetime.fromtimestamp(record.created).strftime('%Y-%m-%d %H:%M:%S')
        
        # Get log level
        level = record.levelname
        
        # Get module name
        module = record.name
        
        # Get message
        message = record.getMessage()
        
        # Add exception info if present
        if record.exc_info:
            message += '\n' + self.formatException(record.exc_info)
        
        # Construct structured log line
        return f"{timestamp} | {level} | {module} | {message}"


def setup_logging(
    log_file: str = None,
    log_level: str = None,
    max_bytes: int = None,
    backup_count: int = None
) -> None:
    """
    Configure structured file-based logging for the application.
    
    Args:
        log_file: Path to log file (default: from Config.LOG_FILE_PATH)
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
                  (default: from Config.LOG_LEVEL)
        max_bytes: Max log file size before rotation in bytes (default: from Config.LOG_MAX_BYTES)
        backup_count: Number of backup log files to keep (default: from Config.LOG_BACKUP_COUNT)
    """
    # Get configuration from centralized config with fallbacks
    if log_file is None:
        log_file = Config.LOG_FILE_PATH
    
    if log_level is None:
        log_level = Config.LOG_LEVEL
    
    if max_bytes is None:
        max_bytes = Config.LOG_MAX_BYTES
    
    if backup_count is None:
        backup_count = Config.LOG_BACKUP_COUNT
    
    # Validate log level
    log_levels = {
        'DEBUG': logging.DEBUG,
        'INFO': logging.INFO,
        'WARNING': logging.WARNING,
        'ERROR': logging.ERROR,
        'CRITICAL': logging.CRITICAL
    }
    log_level_int = log_levels.get(log_level, logging.INFO)
    
    # Create structured formatter
    formatter = StructuredFormatter()
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level_int)
    
    # Remove existing handlers to avoid duplicates
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Create log directory if it doesn't exist
    log_dir = os.path.dirname(log_file)
    if log_dir and not os.path.exists(log_dir):
        try:
            os.makedirs(log_dir, exist_ok=True)
        except Exception as e:
            print(f"Failed to create log directory {log_dir}: {e}", file=sys.stderr)
            return
    
    # Rotating file handler for application logs
    try:
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=max_bytes,
            backupCount=backup_count
        )
        file_handler.setLevel(log_level_int)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
    except Exception as e:
        print(f"Failed to set up file logging: {e}", file=sys.stderr)
        return
    
    # Console handler for development/debugging
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level_int)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # Set specific log levels for third-party libraries
    logging.getLogger('pymongo').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('werkzeug').setLevel(logging.WARNING)
    
    # Log startup information
    logging.info("=" * 50)
    logging.info("GitHub Webhook System - Logging Initialized")
    logging.info(f"Log Level: {log_level}")
    logging.info(f"Log File: {log_file}")
    logging.info(f"Max Bytes: {max_bytes}")
    logging.info(f"Backup Count: {backup_count}")
    logging.info(f"Python Version: {sys.version}")
    logging.info(f"Startup Time: {datetime.now().isoformat()}")
    logging.info("=" * 50)


def setup_celery_logging(
    log_file: str = None,
    log_level: str = None,
    max_bytes: int = None,
    backup_count: int = None
) -> None:
    """
    Configure structured file-based logging for Celery workers.
    
    This function is similar to setup_logging() but uses a separate log file
    for Celery worker logs to keep them separate from Flask application logs.
    
    Args:
        log_file: Path to Celery log file (default: from Config.CELERY_LOG_FILE_PATH)
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
                  (default: from Config.LOG_LEVEL)
        max_bytes: Max log file size before rotation in bytes (default: from Config.LOG_MAX_BYTES)
        backup_count: Number of backup log files to keep (default: from Config.LOG_BACKUP_COUNT)
    """
    # Get configuration from centralized config with fallbacks
    if log_file is None:
        log_file = Config.CELERY_LOG_FILE_PATH
    
    # Use the same setup_logging function with Celery-specific log file
    setup_logging(log_file=log_file, log_level=log_level, max_bytes=max_bytes, backup_count=backup_count)


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