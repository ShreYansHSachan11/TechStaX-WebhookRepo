"""
Celery application configuration and task definitions.

This module configures the Celery distributed task queue system for asynchronous
webhook processing. It defines the Celery app instance with Redis as the message
broker and result backend, and configures retry policies, task serialization,
and acknowledgment settings.

Requirements: 3.1, 3.2, 3.3
"""

from celery import Celery
from celery.signals import worker_process_init
from app.config import Config


@worker_process_init.connect
def setup_celery_worker_logging(**kwargs):
    """
    Initialize structured logging and database connection for Celery workers.
    
    This signal handler is called when a Celery worker process starts,
    ensuring that all Celery workers use the structured logging configuration
    and have their own database connection.
    """
    from .webhook.logging_config import setup_celery_logging, get_logger
    from .webhook.database import initialize_database
    
    # Setup logging first
    setup_celery_logging()
    logger = get_logger(__name__)
    
    # Initialize database connection for this worker process
    logger.info("Initializing database connection for Celery worker process")
    if initialize_database():
        logger.info("Celery worker database connection initialized successfully")
    else:
        logger.error("Failed to initialize database connection for Celery worker")

# Configure Celery application using centralized config
celery_app = Celery(
    'webhook_tasks',
    broker=Config.CELERY_BROKER_URL,
    backend=Config.CELERY_RESULT_BACKEND
)

# Celery configuration using centralized config
celery_app.conf.update(
    # Task serialization format
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    
    # Timezone configuration
    timezone='UTC',
    enable_utc=True,
    
    # Task acknowledgment - late acknowledgment (after task completes)
    task_acks_late=True,
    
    # Retry policy configuration from centralized config
    task_default_retry_delay=Config.CELERY_TASK_RETRY_DELAY,
    task_max_retries=Config.CELERY_TASK_MAX_RETRIES,
    
    # Worker configuration from centralized config
    worker_prefetch_multiplier=1,  # Fetch one task at a time for better distribution
    worker_max_tasks_per_child=1000,  # Restart worker after 1000 tasks to prevent memory leaks
    worker_concurrency=Config.CELERY_WORKER_CONCURRENCY,
    
    # Result backend configuration
    result_expires=3600,  # Results expire after 1 hour
    result_persistent=True,  # Persist results to disk
    
    # Task routing and execution
    task_track_started=True,  # Track when tasks start execution
    task_time_limit=300,  # Hard time limit: 5 minutes
    task_soft_time_limit=240,  # Soft time limit: 4 minutes
)


# Task definitions

@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def process_webhook_task(self, payload: dict, event_type: str) -> dict:
    """
    Celery task for processing webhook payload asynchronously.
    
    This task processes a GitHub webhook payload, extracts event data,
    and stores it in MongoDB. It includes automatic retry logic for
    transient failures and comprehensive error handling that distinguishes
    between transient errors (which should be retried) and permanent errors
    (which should not be retried).
    
    Args:
        self: Task instance (bound task)
        payload: GitHub webhook payload dictionary
        event_type: Event type from X-GitHub-Event header (e.g., 'push', 'pull_request')
        
    Returns:
        dict: Processing result with status and event_id
            - status: 'success' or 'error'
            - event_id: MongoDB document ID (if successful)
            - message: Error message (if failed)
            
    Raises:
        Retry: If processing fails with transient error and retries remain
        
    Requirements: 3.3, 3.7, 3.8, 3.9, 6.3, 6.7
    """
    from .webhook.logging_config import get_logger
    from .webhook.webhook_handler import get_webhook_handler
    from .webhook.database import get_database_connection
    from flask import Request
    from werkzeug.datastructures import Headers
    from pymongo.errors import PyMongoError, ServerSelectionTimeoutError, NetworkTimeout, AutoReconnect
    import json
    
    logger = get_logger(__name__)
    
    try:
        logger.info(f"Starting Celery task {self.request.id} for {event_type} event")
        
        # Create a mock Flask request object for webhook handler
        # This allows us to reuse the existing webhook processing logic
        class MockRequest:
            def __init__(self, payload_data, event_type_header):
                self.data = json.dumps(payload_data).encode('utf-8')
                self.headers = Headers([('X-GitHub-Event', event_type_header)])
                self.is_json = True
                self.content_type = 'application/json'
            
            def get_json(self, force=False, silent=False):
                return json.loads(self.data)
        
        mock_request = MockRequest(payload, event_type)
        
        # Process webhook using existing handler
        webhook_handler = get_webhook_handler()
        webhook_event, status_code, message = webhook_handler.process_webhook(mock_request)
        
        if webhook_event is None:
            # Permanent error - invalid data, don't retry
            error_msg = f"Failed to process webhook: {message}"
            logger.error(f"Task {self.request.id}: {error_msg} (permanent error - not retrying)", exc_info=True)
            return {
                "status": "error",
                "message": error_msg,
                "task_id": self.request.id,
                "error_type": "permanent"
            }
        
        # Store event in database
        db = get_database_connection()
        if not db.is_connected():
            # Transient error - database connection issue, retry
            error_msg = "Database connection not available"
            logger.warning(f"Task {self.request.id}: {error_msg} (transient error - will retry)", exc_info=True)
            raise self.retry(exc=Exception(error_msg))
        
        event_data = webhook_event.to_dict()
        event_id = db.insert_event(event_data)
        
        if event_id is None:
            # Transient error - database insertion failed, retry
            error_msg = "Failed to insert event into database"
            logger.warning(f"Task {self.request.id}: {error_msg} (transient error - will retry)", exc_info=True)
            raise self.retry(exc=Exception(error_msg))
        
        logger.info(f"Task {self.request.id} completed successfully: event_id={event_id}")
        
        return {
            "status": "success",
            "event_id": event_id,
            "task_id": self.request.id,
            "event_type": event_type,
            "author": webhook_event.author,
            "action": webhook_event.action.value
        }
    
    # Transient database errors - retry
    except (ServerSelectionTimeoutError, NetworkTimeout, AutoReconnect) as e:
        error_msg = f"Database timeout/network error in task {self.request.id}: {str(e)}"
        logger.warning(error_msg, exc_info=True)
        if self.request.retries < self.max_retries:
            logger.info(f"Task {self.request.id} will retry (attempt {self.request.retries + 1}/{self.max_retries})")
            raise self.retry(exc=e)
        else:
            logger.error(f"Task {self.request.id} failed after {self.request.retries} retries")
            return {
                "status": "error",
                "message": error_msg,
                "task_id": self.request.id,
                "error_type": "transient_max_retries"
            }
    
    # Permanent errors - invalid data, don't retry
    except (KeyError, ValueError, TypeError, json.JSONDecodeError) as e:
        error_msg = f"Invalid data in task {self.request.id}: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return {
            "status": "error",
            "message": error_msg,
            "task_id": self.request.id,
            "error_type": "permanent"
        }
        
    except self.MaxRetriesExceededError:
        error_msg = f"Max retries exceeded for task {self.request.id}"
        logger.error(f"{error_msg} - giving up", exc_info=True)
        return {
            "status": "error",
            "message": error_msg,
            "task_id": self.request.id,
            "error_type": "max_retries_exceeded"
        }
        
    except Exception as e:
        # Unknown error - log with stack trace and retry cautiously
        error_msg = f"Unexpected error in task {self.request.id}: {str(e)}"
        logger.error(error_msg, exc_info=True)
        
        # Check if we should retry
        if self.request.retries < self.max_retries:
            logger.info(f"Task {self.request.id} will retry (attempt {self.request.retries + 1}/{self.max_retries})")
            raise self.retry(exc=e)
        else:
            logger.error(f"Task {self.request.id} failed after {self.request.retries} retries")
            return {
                "status": "error",
                "message": str(e),
                "task_id": self.request.id,
                "error_type": "unknown"
            }


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def store_event_task(self, event_data: dict) -> str:
    """
    Celery task for storing event data in MongoDB.
    
    This task handles the database insertion of processed webhook events.
    It includes comprehensive error handling that distinguishes between
    transient errors (database timeouts) and permanent errors (invalid data),
    with automatic retry logic for transient failures.
    
    Args:
        self: Task instance (bound task)
        event_data: Processed event data dictionary with fields:
            - request_id: Unique identifier for the request
            - author: GitHub username
            - action: Event action (PUSH, PULL_REQUEST, MERGE)
            - from_branch: Source branch name
            - to_branch: Target branch name
            - timestamp: ISO 8601 UTC timestamp string
            
    Returns:
        str: MongoDB document ID if successful, empty string if failed
        
    Requirements: 3.3, 3.7, 3.8, 3.9, 6.3, 6.7
    """
    from .webhook.logging_config import get_logger
    from .webhook.database import get_database_connection
    from pymongo.errors import PyMongoError, ServerSelectionTimeoutError, NetworkTimeout, AutoReconnect
    
    logger = get_logger(__name__)
    
    try:
        logger.info(f"Starting store_event_task for event: {event_data.get('request_id', 'unknown')}")
        
        # Validate event data - permanent error if invalid
        required_fields = ['request_id', 'author', 'action', 'from_branch', 'to_branch', 'timestamp']
        missing_fields = [field for field in required_fields if field not in event_data]
        
        if missing_fields:
            # Permanent error - invalid data, don't retry
            error_msg = f"Missing required fields: {missing_fields}"
            logger.error(f"store_event_task failed: {error_msg} (permanent error - not retrying)", exc_info=True)
            return ""
        
        # Get database connection
        db = get_database_connection()
        if not db.is_connected():
            # Transient error - database connection issue, retry
            error_msg = "Database connection not available"
            logger.warning(f"store_event_task: {error_msg} (transient error - will retry)", exc_info=True)
            raise self.retry(exc=Exception(error_msg))
        
        # Insert event into database
        event_id = db.insert_event(event_data)
        
        if event_id is None:
            # Transient error - database insertion failed, retry
            error_msg = "Failed to insert event into database"
            logger.warning(f"store_event_task: {error_msg} (transient error - will retry)", exc_info=True)
            raise self.retry(exc=Exception(error_msg))
        
        logger.info(f"store_event_task completed successfully: event_id={event_id}")
        return event_id
    
    # Transient database errors - retry
    except (ServerSelectionTimeoutError, NetworkTimeout, AutoReconnect) as e:
        error_msg = f"Database timeout/network error in store_event_task: {str(e)}"
        logger.warning(error_msg, exc_info=True)
        if self.request.retries < self.max_retries:
            logger.info(f"store_event_task will retry (attempt {self.request.retries + 1}/{self.max_retries})")
            raise self.retry(exc=e)
        else:
            logger.error(f"store_event_task failed after {self.request.retries} retries")
            return ""
    
    # Permanent errors - invalid data, don't retry
    except (KeyError, ValueError, TypeError) as e:
        error_msg = f"Invalid data in store_event_task: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return ""
    
    except self.MaxRetriesExceededError:
        error_msg = "Max retries exceeded for store_event_task"
        logger.error(f"{error_msg} - giving up", exc_info=True)
        return ""
        
    except Exception as e:
        # Unknown error - log with stack trace
        error_msg = f"Unexpected error in store_event_task: {str(e)}"
        logger.error(error_msg, exc_info=True)
        
        # Retry cautiously for unknown errors
        if self.request.retries < self.max_retries:
            logger.info(f"store_event_task will retry (attempt {self.request.retries + 1}/{self.max_retries})")
            raise self.retry(exc=e)
        else:
            logger.error(f"store_event_task failed after {self.request.retries} retries")
            return ""


__all__ = ['celery_app', 'process_webhook_task', 'store_event_task']
