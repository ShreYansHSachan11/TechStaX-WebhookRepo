"""
Data models for the GitHub Webhook System.

This module defines the WebhookEvent data model with validation methods
and serialization for MongoDB storage.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Dict, Any, Optional
import re


class EventAction(Enum):
    """Enumeration of supported webhook event actions."""
    PUSH = "PUSH"
    PULL_REQUEST = "PULL_REQUEST"
    MERGE = "MERGE"


@dataclass
class WebhookEvent:
    """
    Data model for webhook events with validation and serialization methods.
    
    Attributes:
        request_id: Unique identifier for the request (commit SHA or PR number)
        author: GitHub username of the person who performed the action
        action: Type of action performed (PUSH, PULL_REQUEST, MERGE)
        from_branch: Source branch name (empty string for pushes)
        to_branch: Target branch name
        timestamp: When the event occurred
    """
    request_id: str
    author: str
    action: EventAction
    from_branch: str
    to_branch: str
    timestamp: datetime
    
    def __post_init__(self):
        """Validate the webhook event data after initialization."""
        self._validate()
    
    def _validate(self):
        """
        Validate webhook event data.
        
        Raises:
            ValueError: If any field contains invalid data
        """
        # Validate request_id
        if not self.request_id or not isinstance(self.request_id, str):
            raise ValueError("request_id must be a non-empty string")
        
        # Validate author
        if not self.author or not isinstance(self.author, str):
            raise ValueError("author must be a non-empty string")
        
        # Validate GitHub username format (basic validation)
        if not re.match(r'^[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?$', self.author):
            raise ValueError("author must be a valid GitHub username")
        
        # Validate action
        if not isinstance(self.action, EventAction):
            raise ValueError("action must be an EventAction enum value")
        
        # Validate branch names
        if not isinstance(self.from_branch, str):
            raise ValueError("from_branch must be a string")
        
        if not self.to_branch or not isinstance(self.to_branch, str):
            raise ValueError("to_branch must be a non-empty string")
        
        # Validate branch name format (basic validation)
        if self.to_branch and not re.match(r'^[a-zA-Z0-9._/-]+$', self.to_branch):
            raise ValueError("to_branch must be a valid branch name")
        
        if self.from_branch and not re.match(r'^[a-zA-Z0-9._/-]+$', self.from_branch):
            raise ValueError("from_branch must be a valid branch name")
        
        # Validate timestamp
        if not isinstance(self.timestamp, datetime):
            raise ValueError("timestamp must be a datetime object")
        
        # Validate action-specific rules
        if self.action == EventAction.PUSH and self.from_branch:
            # For pushes, from_branch should be empty or same as to_branch
            if self.from_branch != self.to_branch:
                raise ValueError("For PUSH events, from_branch should be empty or same as to_branch")
        
        if self.action in [EventAction.PULL_REQUEST, EventAction.MERGE]:
            # For PRs and merges, from_branch should not be empty
            if not self.from_branch:
                raise ValueError("For PULL_REQUEST and MERGE events, from_branch cannot be empty")
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the webhook event to a dictionary for MongoDB serialization.
        
        Returns:
            Dict[str, Any]: Dictionary representation with ISO 8601 UTC timestamp
        """
        return {
            "request_id": self.request_id,
            "author": self.author,
            "action": self.action.value,
            "from_branch": self.from_branch,
            "to_branch": self.to_branch,
            "timestamp": self._format_timestamp_iso8601()
        }
    
    def _format_timestamp_iso8601(self) -> str:
        """
        Format timestamp to ISO 8601 UTC format.
        
        Returns:
            str: Timestamp in ISO 8601 UTC format (e.g., "2021-04-01T21:30:00Z")
        """
        # Ensure timestamp is in UTC
        if self.timestamp.tzinfo is None:
            # Assume naive datetime is UTC
            utc_timestamp = self.timestamp
        else:
            # Convert to UTC if timezone-aware
            utc_timestamp = self.timestamp.utctimetuple()
            utc_timestamp = datetime(*utc_timestamp[:6])
        
        # Format to ISO 8601 with Z suffix for UTC
        return utc_timestamp.strftime("%Y-%m-%dT%H:%M:%SZ")
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'WebhookEvent':
        """
        Create a WebhookEvent instance from a dictionary.
        
        Args:
            data: Dictionary containing event data
            
        Returns:
            WebhookEvent: New instance created from dictionary data
            
        Raises:
            ValueError: If required fields are missing or invalid
        """
        required_fields = ['request_id', 'author', 'action', 'from_branch', 'to_branch', 'timestamp']
        
        # Check for required fields
        for field in required_fields:
            if field not in data:
                raise ValueError(f"Missing required field: {field}")
        
        # Parse action enum
        try:
            action = EventAction(data['action'])
        except ValueError:
            raise ValueError(f"Invalid action value: {data['action']}")
        
        # Parse timestamp
        timestamp = data['timestamp']
        if isinstance(timestamp, str):
            # Parse ISO 8601 timestamp string
            timestamp = cls._parse_iso8601_timestamp(timestamp)
        elif not isinstance(timestamp, datetime):
            raise ValueError("timestamp must be a datetime object or ISO 8601 string")
        
        return cls(
            request_id=data['request_id'],
            author=data['author'],
            action=action,
            from_branch=data['from_branch'],
            to_branch=data['to_branch'],
            timestamp=timestamp
        )
    
    @staticmethod
    def _parse_iso8601_timestamp(timestamp_str: str) -> datetime:
        """
        Parse ISO 8601 timestamp string to datetime object.
        
        Args:
            timestamp_str: ISO 8601 timestamp string
            
        Returns:
            datetime: Parsed datetime object
            
        Raises:
            ValueError: If timestamp string is invalid
        """
        # Handle various ISO 8601 formats
        formats = [
            "%Y-%m-%dT%H:%M:%SZ",           # 2021-04-01T21:30:00Z
            "%Y-%m-%dT%H:%M:%S.%fZ",        # 2021-04-01T21:30:00.123456Z
            "%Y-%m-%dT%H:%M:%S",            # 2021-04-01T21:30:00
            "%Y-%m-%dT%H:%M:%S.%f",         # 2021-04-01T21:30:00.123456
        ]
        
        for fmt in formats:
            try:
                return datetime.strptime(timestamp_str, fmt)
            except ValueError:
                continue
        
        raise ValueError(f"Invalid ISO 8601 timestamp format: {timestamp_str}")
    
    def __str__(self) -> str:
        """String representation of the webhook event."""
        return f"WebhookEvent(id={self.request_id}, author={self.author}, action={self.action.value}, {self.from_branch}->{self.to_branch})"
    
    def __repr__(self) -> str:
        """Detailed string representation of the webhook event."""
        return (f"WebhookEvent(request_id='{self.request_id}', author='{self.author}', "
                f"action={self.action}, from_branch='{self.from_branch}', "
                f"to_branch='{self.to_branch}', timestamp={self.timestamp})")


def create_push_event(request_id: str, author: str, to_branch: str, timestamp: datetime) -> WebhookEvent:
    """
    Create a WebhookEvent for a push action.
    
    Args:
        request_id: Commit SHA
        author: GitHub username who pushed
        to_branch: Branch that was pushed to
        timestamp: When the push occurred
        
    Returns:
        WebhookEvent: New push event instance
    """
    return WebhookEvent(
        request_id=request_id,
        author=author,
        action=EventAction.PUSH,
        from_branch="",  # Empty for pushes as per requirements
        to_branch=to_branch,
        timestamp=timestamp
    )


def create_pull_request_event(request_id: str, author: str, from_branch: str, 
                            to_branch: str, timestamp: datetime) -> WebhookEvent:
    """
    Create a WebhookEvent for a pull request action.
    
    Args:
        request_id: Pull request number
        author: GitHub username who created the PR
        from_branch: Source branch of the PR
        to_branch: Target branch of the PR
        timestamp: When the PR was created
        
    Returns:
        WebhookEvent: New pull request event instance
    """
    return WebhookEvent(
        request_id=request_id,
        author=author,
        action=EventAction.PULL_REQUEST,
        from_branch=from_branch,
        to_branch=to_branch,
        timestamp=timestamp
    )


def create_merge_event(request_id: str, author: str, from_branch: str, 
                      to_branch: str, timestamp: datetime) -> WebhookEvent:
    """
    Create a WebhookEvent for a merge action.
    
    Args:
        request_id: Pull request number that was merged
        author: GitHub username who performed the merge
        from_branch: Source branch that was merged
        to_branch: Target branch that received the merge
        timestamp: When the merge occurred
        
    Returns:
        WebhookEvent: New merge event instance
    """
    return WebhookEvent(
        request_id=request_id,
        author=author,
        action=EventAction.MERGE,
        from_branch=from_branch,
        to_branch=to_branch,
        timestamp=timestamp
    )