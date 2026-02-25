"""
Error handling module for webhook processing system.

This module provides decorators for automatic error handling, custom exception
classes for specific error scenarios, and utilities for logging exceptions with
stack traces.
"""

import logging
from functools import wraps
from typing import Callable, Any


def handle_errors(logger: logging.Logger) -> Callable:
    """
    Decorator for automatic error handling with logging.
    
    This decorator wraps functions to catch all exceptions, log them with full
    stack traces, and re-raise them for upstream handling. It ensures that all
    errors are properly logged before propagating.
    
    Args:
        logger: Logger instance to use for error logging
        
    Returns:
        Decorator function that wraps the target function with error handling
        
    Example:
        >>> logger = logging.getLogger(__name__)
        >>> @handle_errors(logger)
        ... def process_data(data):
        ...     return data['value']
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return func(*args, **kwargs)
            except Exception as e:
                logger.error(
                    f"Error in {func.__name__}: {e}",
                    exc_info=True  # Include stack trace
                )
                raise
        return wrapper
    return decorator


class WebhookProcessingError(Exception):
    """
    Custom exception for webhook processing errors.
    
    Raised when errors occur during webhook payload parsing, validation,
    or processing operations. This exception indicates issues specific to
    webhook handling logic.
    
    Example:
        >>> raise WebhookProcessingError("Invalid event type: unknown")
    """
    pass


class DatabaseOperationError(Exception):
    """
    Custom exception for database operation errors.
    
    Raised when database operations fail, including connection failures,
    query execution errors, or data integrity issues. This exception helps
    distinguish database-related errors from other types of failures.
    
    Example:
        >>> raise DatabaseOperationError("Failed to insert event: connection timeout")
    """
    pass


class QueueFullError(Exception):
    """
    Custom exception when queue is full.
    
    Raised when attempting to enqueue items to a full queue, indicating
    backpressure in the system. This exception allows callers to implement
    appropriate backoff or rejection strategies.
    
    Example:
        >>> raise QueueFullError("Cannot enqueue: queue at maximum capacity")
    """
    pass
