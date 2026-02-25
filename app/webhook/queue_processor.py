"""
Thread-safe queue processor for asynchronous webhook processing.

This module implements a thread-safe queue with background worker threads
for processing webhook payloads asynchronously. It provides graceful shutdown
with queue draining and comprehensive exception handling.
"""

import queue
import threading
from typing import Dict, Any, Optional
from datetime import datetime
from .logging_config import get_logger
from .database import get_database_connection
from .webhook_handler import get_webhook_handler

# Get logger for this module
logger = get_logger(__name__)


class WebhookQueue:
    """
    Thread-safe queue for webhook payload processing with background workers.
    
    This class manages a thread-safe queue for webhook payloads and spawns
    background worker threads to process them asynchronously. It ensures
    graceful shutdown with queue draining and handles exceptions without
    crashing worker threads.
    """
    
    def __init__(self, max_size: int = 1000, num_workers: int = 4):
        """
        Initialize webhook queue with worker threads.
        
        Args:
            max_size: Maximum queue size before blocking (default: 1000)
            num_workers: Number of background worker threads (default: 4)
        """
        self._queue = queue.Queue(maxsize=max_size)
        self._num_workers = num_workers
        self._workers = []
        self._stop_flag = threading.Event()
        self._max_size = max_size
        
        logger.info(f"WebhookQueue initialized with max_size={max_size}, num_workers={num_workers}")
    
    def enqueue(self, payload: Dict[str, Any], event_type: str) -> bool:
        """
        Add webhook payload to processing queue.
        
        This method adds a webhook payload to the thread-safe queue for
        asynchronous processing by background workers. If the queue is full,
        it will block until space is available or return False on timeout.
        
        Args:
            payload: GitHub webhook payload dictionary
            event_type: Event type from X-GitHub-Event header
            
        Returns:
            bool: True if enqueued successfully, False if queue full or error
        """
        try:
            if not payload or not isinstance(payload, dict):
                logger.error("Cannot enqueue: payload is empty or not a dictionary")
                return False
            
            if not event_type or not isinstance(event_type, str):
                logger.error("Cannot enqueue: event_type is empty or not a string")
                return False
            
            # Create queue item with metadata
            queue_item = {
                'payload': payload,
                'event_type': event_type,
                'enqueued_at': datetime.utcnow()
            }
            
            # Try to add to queue with timeout
            try:
                self._queue.put(queue_item, block=True, timeout=1.0)
                logger.debug(f"Enqueued {event_type} event to processing queue")
                return True
            except queue.Full:
                logger.warning(f"Queue is full (max_size={self._max_size}), cannot enqueue {event_type} event")
                return False
                
        except Exception as e:
            logger.error(f"Error enqueuing payload: {e}", exc_info=True)
            return False
    
    def start_workers(self) -> None:
        """
        Start background worker threads.
        
        This method spawns the configured number of background worker threads
        that will continuously consume and process items from the queue until
        the stop flag is set.
        """
        try:
            if self._workers:
                logger.warning("Workers already started, ignoring start_workers() call")
                return
            
            logger.info(f"Starting {self._num_workers} background worker threads")
            
            for i in range(self._num_workers):
                worker = threading.Thread(
                    target=self._worker_loop,
                    name=f"WebhookWorker-{i+1}",
                    daemon=True
                )
                worker.start()
                self._workers.append(worker)
                logger.debug(f"Started worker thread: {worker.name}")
            
            logger.info(f"Successfully started {len(self._workers)} worker threads")
            
        except Exception as e:
            logger.error(f"Error starting worker threads: {e}", exc_info=True)
    
    def shutdown(self, timeout: int = 30) -> None:
        """
        Gracefully shutdown workers and drain queue.
        
        This method signals workers to stop, waits for the queue to be drained,
        and then joins all worker threads. It ensures no data loss during shutdown.
        
        Args:
            timeout: Maximum seconds to wait for queue to drain (default: 30)
        """
        try:
            logger.info(f"Initiating graceful shutdown (timeout={timeout}s)")
            
            # Set stop flag to signal workers
            self._stop_flag.set()
            
            # Wait for queue to be empty
            queue_size = self._queue.qsize()
            if queue_size > 0:
                logger.info(f"Waiting for {queue_size} items to be processed...")
                try:
                    self._queue.join()
                    logger.info("All queued items processed successfully")
                except Exception as e:
                    logger.warning(f"Error waiting for queue to drain: {e}")
            
            # Join all worker threads
            logger.info(f"Waiting for {len(self._workers)} worker threads to terminate...")
            for worker in self._workers:
                try:
                    worker.join(timeout=timeout / len(self._workers) if self._workers else timeout)
                    if worker.is_alive():
                        logger.warning(f"Worker {worker.name} did not terminate within timeout")
                    else:
                        logger.debug(f"Worker {worker.name} terminated successfully")
                except Exception as e:
                    logger.error(f"Error joining worker {worker.name}: {e}")
            
            logger.info("Graceful shutdown completed")
            
        except Exception as e:
            logger.error(f"Error during shutdown: {e}", exc_info=True)
    
    def _worker_loop(self) -> None:
        """
        Worker thread main loop - consumes and processes payloads.
        
        This method runs continuously in each worker thread, consuming items
        from the queue and processing them. It handles exceptions gracefully
        to prevent worker crashes and continues processing subsequent items.
        """
        worker_name = threading.current_thread().name
        logger.info(f"{worker_name} started")
        
        while not self._stop_flag.is_set():
            try:
                # Try to get item from queue with timeout
                try:
                    queue_item = self._queue.get(timeout=1.0)
                except queue.Empty:
                    # No items in queue, continue loop
                    continue
                
                # Process the queue item
                try:
                    self._process_item(queue_item)
                except Exception as e:
                    # Log exception but continue processing
                    logger.error(
                        f"{worker_name} error processing item: {e}",
                        exc_info=True
                    )
                finally:
                    # Always mark task as done
                    self._queue.task_done()
                    
            except Exception as e:
                # Catch any unexpected exceptions in the worker loop
                logger.error(
                    f"{worker_name} unexpected error in worker loop: {e}",
                    exc_info=True
                )
                # Continue running despite error
        
        logger.info(f"{worker_name} stopped")
    
    def _process_item(self, queue_item: Dict[str, Any]) -> None:
        """
        Process a single queue item.
        
        This method extracts the payload and event type from the queue item,
        processes the webhook using the webhook handler, and stores the
        resulting event in the database.
        
        Args:
            queue_item: Queue item containing payload, event_type, and metadata
            
        Raises:
            Exception: If processing fails (caught by worker loop)
        """
        try:
            payload = queue_item.get('payload')
            event_type = queue_item.get('event_type')
            enqueued_at = queue_item.get('enqueued_at')
            
            if not payload or not event_type:
                logger.error("Invalid queue item: missing payload or event_type")
                return
            
            # Calculate queue wait time
            if enqueued_at:
                wait_time = (datetime.utcnow() - enqueued_at).total_seconds()
                logger.debug(f"Processing {event_type} event (queue wait: {wait_time:.2f}s)")
            
            # Get webhook handler and database connection
            handler = get_webhook_handler()
            db = get_database_connection()
            
            # Create a mock request object for the handler
            # Since we're processing from queue, we need to simulate the request
            from flask import Request
            from werkzeug.datastructures import Headers
            from io import BytesIO
            import json
            
            # Create mock request with payload and headers
            headers = Headers([('X-GitHub-Event', event_type)])
            data = json.dumps(payload).encode('utf-8')
            environ = {
                'REQUEST_METHOD': 'POST',
                'CONTENT_TYPE': 'application/json',
                'CONTENT_LENGTH': str(len(data)),
                'wsgi.input': BytesIO(data)
            }
            
            mock_request = Request(environ)
            mock_request.headers = headers
            
            # Process webhook
            webhook_event, status_code, message = handler.process_webhook(mock_request)
            
            if webhook_event is None:
                logger.warning(f"Failed to process {event_type} event: {message}")
                return
            
            # Store event in database
            event_data = webhook_event.to_dict()
            event_id = db.insert_event(event_data)
            
            if event_id:
                logger.info(
                    f"Successfully processed and stored {event_type} event "
                    f"(event_id={event_id}, author={webhook_event.author})"
                )
            else:
                logger.error(f"Failed to store {event_type} event in database")
                
        except Exception as e:
            logger.error(f"Error processing queue item: {e}", exc_info=True)
            raise
    
    def size(self) -> int:
        """
        Get current queue size.
        
        Returns:
            int: Number of items currently in the queue
        """
        return self._queue.qsize()
    
    def is_running(self) -> bool:
        """
        Check if workers are running.
        
        Returns:
            bool: True if workers are running, False if stopped
        """
        return not self._stop_flag.is_set()
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get queue statistics.
        
        Returns:
            Dict[str, Any]: Dictionary containing queue statistics
        """
        return {
            'queue_size': self.size(),
            'max_size': self._max_size,
            'num_workers': self._num_workers,
            'workers_alive': sum(1 for w in self._workers if w.is_alive()),
            'is_running': self.is_running()
        }


# Global webhook queue instance
_webhook_queue: Optional[WebhookQueue] = None


def initialize_webhook_queue(max_size: int = 1000, num_workers: int = 4) -> WebhookQueue:
    """
    Initialize the global webhook queue instance.
    
    Args:
        max_size: Maximum queue size before blocking (default: 1000)
        num_workers: Number of background worker threads (default: 4)
        
    Returns:
        WebhookQueue: The initialized webhook queue instance
    """
    global _webhook_queue
    
    if _webhook_queue is not None:
        logger.warning("Webhook queue already initialized, returning existing instance")
        return _webhook_queue
    
    _webhook_queue = WebhookQueue(max_size=max_size, num_workers=num_workers)
    _webhook_queue.start_workers()
    
    logger.info("Global webhook queue initialized and workers started")
    return _webhook_queue


def get_webhook_queue() -> Optional[WebhookQueue]:
    """
    Get the global webhook queue instance.
    
    Returns:
        WebhookQueue: The webhook queue instance or None if not initialized
    """
    return _webhook_queue


def shutdown_webhook_queue(timeout: int = 30) -> None:
    """
    Shutdown the global webhook queue instance.
    
    Args:
        timeout: Maximum seconds to wait for queue to drain (default: 30)
    """
    global _webhook_queue
    
    if _webhook_queue is None:
        logger.warning("Webhook queue not initialized, nothing to shutdown")
        return
    
    _webhook_queue.shutdown(timeout=timeout)
    _webhook_queue = None
    logger.info("Global webhook queue shutdown completed")
