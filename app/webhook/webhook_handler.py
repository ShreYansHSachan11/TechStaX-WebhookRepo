"""
Webhook payload processing for the GitHub Webhook System.

This module handles GitHub webhook payloads, extracts event types from headers,
validates payloads, and processes different event types (push, pull_request).
"""

from typing import Dict, Any, Optional, Tuple
from datetime import datetime
from flask import Request
from .models import WebhookEvent, EventAction, create_push_event, create_pull_request_event, create_merge_event
from .logging_config import get_logger

# Get logger for this module
logger = get_logger(__name__)


class WebhookHandler:
    """Handles GitHub webhook payload processing and event extraction."""
    
    SUPPORTED_EVENTS = {'push', 'pull_request'}
    
    def __init__(self):
        """Initialize the webhook handler."""
        pass
    
    def process_webhook(self, request: Request) -> Tuple[Optional[WebhookEvent], int, str]:
        """
        Process a GitHub webhook request and extract event data.
        
        Args:
            request: Flask request object containing webhook payload
            
        Returns:
            Tuple[Optional[WebhookEvent], int, str]: 
                - WebhookEvent object if successful, None if failed
                - HTTP status code
                - Response message
        """
        try:
            logger.info("Starting webhook processing")
            
            # Extract event type from headers
            event_type = self._get_event_type(request)
            if not event_type:
                logger.warning("Missing or invalid X-GitHub-Event header")
                return None, 400, "Missing or invalid X-GitHub-Event header"
            
            logger.info(f"Processing webhook event type: {event_type}")
            
            # Check if event type is supported
            if event_type not in self.SUPPORTED_EVENTS:
                logger.info(f"Unsupported event type: {event_type} - ignoring")
                return None, 200, f"Event type '{event_type}' not supported, ignoring"
            
            # Validate and parse JSON payload
            payload = self._validate_payload(request)
            if payload is None:
                logger.error("Invalid or missing JSON payload")
                return None, 400, "Invalid or missing JSON payload"
            
            logger.debug(f"Payload validation successful for {event_type} event")
            
            # Process the event based on type
            webhook_event = self._process_event(event_type, payload)
            if webhook_event is None:
                logger.error(f"Failed to process {event_type} event")
                return None, 400, f"Failed to process {event_type} event"
            
            logger.info(f"Successfully processed {event_type} event: {webhook_event.action.value}")
            logger.debug(f"Event details: author={webhook_event.author}, "
                        f"from_branch={webhook_event.from_branch}, "
                        f"to_branch={webhook_event.to_branch}, "
                        f"request_id={webhook_event.request_id}")
            
            return webhook_event, 200, "Event processed successfully"
            
        except Exception as e:
            logger.error(f"Unexpected error processing webhook: {e}")
            return None, 500, "Internal server error"
    
    def _get_event_type(self, request: Request) -> Optional[str]:
        """
        Extract event type from X-GitHub-Event header.
        
        Args:
            request: Flask request object
            
        Returns:
            str: Event type or None if not found/invalid
        """
        event_type = request.headers.get('X-GitHub-Event')
        if not event_type or not isinstance(event_type, str):
            return None
        
        return event_type.lower().strip()
    
    def _validate_payload(self, request: Request) -> Optional[Dict[str, Any]]:
        """
        Validate and parse JSON payload from request.
        
        Args:
            request: Flask request object
            
        Returns:
            Dict[str, Any]: Parsed JSON payload or None if invalid
        """
        try:
            # Check if request has data
            if not hasattr(request, 'data') or not request.data:
                logger.warning("Request has no data")
                return None
            
            # Check content type
            if not request.is_json:
                content_type = getattr(request, 'content_type', 'unknown')
                logger.warning(f"Invalid content type: {content_type}, expected application/json")
                return None
            
            # Parse JSON payload
            payload = request.get_json(force=False, silent=False)
            
            if payload is None:
                logger.warning("Failed to parse JSON payload - payload is None")
                return None
                
            if not isinstance(payload, dict):
                logger.warning(f"Invalid JSON payload type: {type(payload)}, expected dict")
                return None
            
            if not payload:
                logger.warning("Empty JSON payload received")
                return None
            
            return payload
            
        except ValueError as e:
            logger.error(f"JSON parsing error: {e}")
            return None
        except UnicodeDecodeError as e:
            logger.error(f"Unicode decode error in payload: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error parsing JSON payload: {e}")
            return None
    
    def _process_event(self, event_type: str, payload: Dict[str, Any]) -> Optional[WebhookEvent]:
        """
        Process webhook event based on event type.
        
        Args:
            event_type: Type of GitHub event (push, pull_request)
            payload: Parsed JSON payload
            
        Returns:
            WebhookEvent: Processed event object or None if failed
        """
        try:
            if event_type == 'push':
                return self._process_push_event(payload)
            elif event_type == 'pull_request':
                return self._process_pull_request_event(payload)
            else:
                logger.warning(f"Unsupported event type: {event_type}")
                return None
                
        except Exception as e:
            logger.error(f"Error processing {event_type} event: {e}")
            return None
    
    def _process_push_event(self, payload: Dict[str, Any]) -> Optional[WebhookEvent]:
        """
        Process push event payload and extract required fields.
        
        Args:
            payload: GitHub push event payload
            
        Returns:
            WebhookEvent: Processed push event or None if failed
        """
        try:
            # Extract required fields for push events
            # pusher.name as author
            pusher = payload.get('pusher')
            if not pusher or not isinstance(pusher, dict):
                logger.error("Missing or invalid pusher object in push event")
                return None
                
            author = pusher.get('name')
            if not author or not isinstance(author, str) or not author.strip():
                logger.error("Missing or invalid pusher.name in push event")
                return None
            
            # ref field to get branch name (remove refs/heads/ prefix)
            ref = payload.get('ref')
            if not ref or not isinstance(ref, str):
                logger.error("Missing or invalid ref field in push event")
                return None
                
            if not ref.startswith('refs/heads/'):
                logger.error(f"Invalid ref format: {ref}, expected refs/heads/...")
                return None
            
            to_branch = ref.replace('refs/heads/', '', 1)
            if not to_branch.strip():
                logger.error("Empty branch name after removing refs/heads/ prefix")
                return None
            
            # commit SHA as request_id (use 'after' field)
            request_id = payload.get('after')
            if not request_id or not isinstance(request_id, str) or not request_id.strip():
                logger.error("Missing or invalid 'after' commit SHA in push event")
                return None
            
            # timestamp from head_commit.timestamp
            head_commit = payload.get('head_commit')
            if not head_commit or not isinstance(head_commit, dict):
                logger.error("Missing or invalid head_commit object in push event")
                return None
                
            timestamp_str = head_commit.get('timestamp')
            if not timestamp_str or not isinstance(timestamp_str, str):
                logger.error("Missing or invalid head_commit.timestamp in push event")
                return None
            
            # Parse timestamp
            timestamp = self._parse_github_timestamp(timestamp_str)
            if timestamp is None:
                logger.error(f"Invalid timestamp format: {timestamp_str}")
                return None
            
            # Create push event (from_branch is empty for pushes)
            return create_push_event(
                request_id=request_id.strip(),
                author=author.strip(),
                to_branch=to_branch.strip(),
                timestamp=timestamp
            )
            
        except KeyError as e:
            logger.error(f"Missing required field in push event: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error processing push event: {e}")
            return None
    
    def _process_pull_request_event(self, payload: Dict[str, Any]) -> Optional[WebhookEvent]:
        """
        Process pull request event payload and extract required fields.
        
        Args:
            payload: GitHub pull_request event payload
            
        Returns:
            WebhookEvent: Processed pull request or merge event or None if failed
        """
        try:
            # Extract pull request data
            pull_request = payload.get('pull_request')
            if not pull_request or not isinstance(pull_request, dict):
                logger.error("Missing or invalid pull_request object in payload")
                return None
            
            # PR creator username as author
            user = pull_request.get('user')
            if not user or not isinstance(user, dict):
                logger.error("Missing or invalid pull_request.user object")
                return None
                
            author = user.get('login')
            if not author or not isinstance(author, str) or not author.strip():
                logger.error("Missing or invalid pull_request.user.login")
                return None
            
            # Source and target branches
            head = pull_request.get('head')
            base = pull_request.get('base')
            
            if not head or not isinstance(head, dict):
                logger.error("Missing or invalid pull_request.head object")
                return None
                
            if not base or not isinstance(base, dict):
                logger.error("Missing or invalid pull_request.base object")
                return None
            
            from_branch = head.get('ref')
            to_branch = base.get('ref')
            
            if not from_branch or not isinstance(from_branch, str) or not from_branch.strip():
                logger.error("Missing or invalid head.ref in pull request")
                return None
                
            if not to_branch or not isinstance(to_branch, str) or not to_branch.strip():
                logger.error("Missing or invalid base.ref in pull request")
                return None
            
            # PR number as request_id
            pr_number = pull_request.get('number')
            if pr_number is None or not isinstance(pr_number, int):
                logger.error("Missing or invalid pull_request.number")
                return None
            
            request_id = str(pr_number)
            
            # Check if this is a merge event
            is_merged = pull_request.get('merged', False)
            
            if is_merged:
                # This is a merge event
                merged_at = pull_request.get('merged_at')
                if not merged_at or not isinstance(merged_at, str):
                    logger.error("Missing or invalid merged_at timestamp for merged PR")
                    return None
                
                timestamp = self._parse_github_timestamp(merged_at)
                if timestamp is None:
                    logger.error(f"Invalid merged_at timestamp: {merged_at}")
                    return None
                
                return create_merge_event(
                    request_id=request_id,
                    author=author.strip(),
                    from_branch=from_branch.strip(),
                    to_branch=to_branch.strip(),
                    timestamp=timestamp
                )
            else:
                # This is a regular pull request event
                created_at = pull_request.get('created_at')
                if not created_at or not isinstance(created_at, str):
                    logger.error("Missing or invalid created_at timestamp for PR")
                    return None
                
                timestamp = self._parse_github_timestamp(created_at)
                if timestamp is None:
                    logger.error(f"Invalid created_at timestamp: {created_at}")
                    return None
                
                return create_pull_request_event(
                    request_id=request_id,
                    author=author.strip(),
                    from_branch=from_branch.strip(),
                    to_branch=to_branch.strip(),
                    timestamp=timestamp
                )
                
        except KeyError as e:
            logger.error(f"Missing required field in pull request event: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error processing pull request event: {e}")
            return None
    
    def _parse_github_timestamp(self, timestamp_str: str) -> Optional[datetime]:
        """
        Parse GitHub timestamp string to datetime object.
        
        Args:
            timestamp_str: GitHub timestamp string (ISO 8601 format)
            
        Returns:
            datetime: Parsed datetime object or None if failed
        """
        try:
            # GitHub typically sends timestamps in ISO 8601 format
            # Handle various formats that GitHub might send
            formats = [
                "%Y-%m-%dT%H:%M:%SZ",           # 2021-04-01T21:30:00Z
                "%Y-%m-%dT%H:%M:%S.%fZ",        # 2021-04-01T21:30:00.123456Z
                "%Y-%m-%dT%H:%M:%S",            # 2021-04-01T21:30:00
                "%Y-%m-%dT%H:%M:%S.%f",         # 2021-04-01T21:30:00.123456
                "%Y-%m-%dT%H:%M:%S%z",          # 2026-01-30T17:40:47+05:30
                "%Y-%m-%dT%H:%M:%S.%f%z",       # 2026-01-30T17:40:47.123456+05:30
            ]
            
            for fmt in formats:
                try:
                    parsed_dt = datetime.strptime(timestamp_str, fmt)
                    # Convert timezone-aware datetime to UTC naive datetime
                    if parsed_dt.tzinfo is not None:
                        # Convert to UTC by subtracting the timezone offset
                        utc_dt = parsed_dt.utctimetuple()
                        return datetime(*utc_dt[:6])
                    return parsed_dt
                except ValueError:
                    continue
            
            logger.error(f"Unable to parse timestamp: {timestamp_str}")
            return None
            
        except Exception as e:
            logger.error(f"Error parsing timestamp {timestamp_str}: {e}")
            return None


# Global webhook handler instance
webhook_handler = WebhookHandler()


def get_webhook_handler() -> WebhookHandler:
    """
    Get the global webhook handler instance.
    
    Returns:
        WebhookHandler: The webhook handler instance
    """
    return webhook_handler