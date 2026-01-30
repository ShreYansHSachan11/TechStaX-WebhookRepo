"""
Database connection and operations for the GitHub Webhook System.

This module handles MongoDB connection using PyMongo with connection pooling,
error handling, and database/collection initialization.
"""

import os
from typing import List, Dict, Any, Optional
from pymongo import MongoClient, DESCENDING
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError, PyMongoError
from pymongo.collection import Collection
from pymongo.database import Database
from .logging_config import get_logger, log_database_operation

# Get logger for this module
logger = get_logger(__name__)


class DatabaseConnection:
    """Manages MongoDB connection with connection pooling and error handling."""
    
    def __init__(self):
        self._client: Optional[MongoClient] = None
        self._database: Optional[Database] = None
        self._collection: Optional[Collection] = None
        self._connection_string = self._parse_connection_string()
        self._database_name = os.getenv('MONGODB_DATABASE', 'webhook_system')
        
    def _parse_connection_string(self) -> str:
        """Parse MongoDB connection string from environment variables."""
        connection_string = os.getenv('MONGODB_URI')
        
        if not connection_string:
            # Fallback to individual components if MONGODB_URI is not set
            host = os.getenv('MONGODB_HOST', 'localhost')
            port = os.getenv('MONGODB_PORT', '27017')
            database = os.getenv('MONGODB_DATABASE', 'webhook_system')
            username = os.getenv('MONGODB_USERNAME')
            password = os.getenv('MONGODB_PASSWORD')
            
            if username and password:
                connection_string = f"mongodb://{username}:{password}@{host}:{port}/{database}"
            else:
                connection_string = f"mongodb://{host}:{port}/{database}"
        
        return connection_string
    
    def connect(self) -> bool:
        """
        Establish connection to MongoDB with connection pooling.
        
        Returns:
            bool: True if connection successful, False otherwise
        """
        try:
            # Validate connection string
            if not self._connection_string:
                logger.error("MongoDB connection string is empty or invalid")
                log_database_operation("connect", "Connection string is empty or invalid", logger, success=False)
                return False
            
            logger.info(f"Attempting to connect to MongoDB database: {self._database_name}")
            log_database_operation("connect", f"Connecting to database: {self._database_name}", logger, success=True)
            
            # Create client with connection pooling settings
            self._client = MongoClient(
                self._connection_string,
                serverSelectionTimeoutMS=5000,  # 5 second timeout
                maxPoolSize=10,  # Maximum 10 connections in pool
                minPoolSize=1,   # Minimum 1 connection in pool
                maxIdleTimeMS=30000,  # Close connections after 30 seconds idle
                waitQueueTimeoutMS=5000  # Wait 5 seconds for connection from pool
            )
            
            # Test the connection
            self._client.admin.command('ping')
            logger.info("MongoDB ping successful")
            
            # Initialize database and collection
            self._database = self._client[self._database_name]
            self._collection = self._database['webhook_events']
            
            # Create indexes for efficient querying
            self._create_indexes()
            
            logger.info(f"Successfully connected to MongoDB database: {self._database_name}")
            log_database_operation("connect", f"Connection established to {self._database_name}", logger, success=True)
            return True
            
        except (ConnectionFailure, ServerSelectionTimeoutError) as e:
            logger.error(f"MongoDB connection failed - server unreachable or timeout: {e}")
            log_database_operation("connect", f"Connection failed - timeout/unreachable: {e}", logger, success=False)
            self._cleanup_failed_connection()
            return False
        except PyMongoError as e:
            logger.error(f"MongoDB error during connection: {e}")
            log_database_operation("connect", f"MongoDB error: {e}", logger, success=False)
            self._cleanup_failed_connection()
            return False
        except Exception as e:
            logger.error(f"Unexpected error during MongoDB connection: {e}")
            log_database_operation("connect", f"Unexpected error: {e}", logger, success=False)
            self._cleanup_failed_connection()
            return False
    
    def _cleanup_failed_connection(self):
        """Clean up resources after a failed connection attempt."""
        if self._client:
            try:
                self._client.close()
            except Exception as e:
                logger.warning(f"Error closing failed MongoDB client: {e}")
            finally:
                self._client = None
                self._database = None
                self._collection = None
    
    def _create_indexes(self):
        """Create database indexes for efficient querying."""
        try:
            if not self._collection:
                logger.error("Cannot create indexes: collection not initialized")
                return
                
            # Create index on timestamp field for efficient sorting
            self._collection.create_index([("timestamp", DESCENDING)])
            logger.info("Database indexes created successfully")
        except PyMongoError as e:
            logger.error(f"Failed to create database indexes: {e}")
            # Don't fail the connection for index creation errors
        except Exception as e:
            logger.error(f"Unexpected error creating indexes: {e}")
    
    def disconnect(self):
        """Close the MongoDB connection."""
        if self._client:
            try:
                self._client.close()
                logger.info("MongoDB connection closed successfully")
                log_database_operation("disconnect", "Connection closed", logger, success=True)
            except Exception as e:
                logger.error(f"Error closing MongoDB connection: {e}")
                log_database_operation("disconnect", f"Error closing connection: {e}", logger, success=False)
            finally:
                self._client = None
                self._database = None
                self._collection = None
    
    def is_connected(self) -> bool:
        """
        Check if the database connection is active.
        
        Returns:
            bool: True if connected, False otherwise
        """
        if not self._client:
            return False
        
        try:
            self._client.admin.command('ping')
            return True
        except Exception:
            return False
    
    def get_collection(self) -> Optional[Collection]:
        """
        Get the webhook_events collection.
        
        Returns:
            Collection: MongoDB collection object or None if not connected
        """
        if not self.is_connected():
            logger.warning("Attempting to get collection without active connection")
            return None
        
        return self._collection
    
    def insert_event(self, event_data: Dict[str, Any]) -> Optional[str]:
        """
        Insert a webhook event into the database.
        
        Args:
            event_data: Dictionary containing event data
            
        Returns:
            str: Inserted document ID or None if failed
        """
        if not event_data:
            logger.error("Cannot insert event: event_data is empty or None")
            return None
            
        if not self.is_connected():
            logger.error("Cannot insert event: No database connection")
            return None
        
        try:
            # Validate required fields before insertion
            required_fields = ['request_id', 'author', 'action', 'from_branch', 'to_branch', 'timestamp']
            missing_fields = [field for field in required_fields if field not in event_data]
            
            if missing_fields:
                logger.error(f"Cannot insert event: missing required fields: {missing_fields}")
                return None
            
            result = self._collection.insert_one(event_data)
            logger.info(f"Event inserted with ID: {result.inserted_id}")
            return str(result.inserted_id)
            
        except PyMongoError as e:
            logger.error(f"Database error inserting event: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error inserting event: {e}")
            return None
    
    def get_all_events(self) -> List[Dict[str, Any]]:
        """
        Retrieve all webhook events sorted by timestamp descending.
        
        Returns:
            List[Dict]: List of event documents
        """
        if not self.is_connected():
            logger.error("Cannot retrieve events: No database connection")
            return []
        
        try:
            # Query all events sorted by timestamp descending (latest first)
            events = list(self._collection.find({}, {'_id': 0}).sort("timestamp", DESCENDING))
            logger.info(f"Retrieved {len(events)} events from database")
            return events
            
        except PyMongoError as e:
            logger.error(f"Database error retrieving events: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error retrieving events: {e}")
            return []


# Global database connection instance
db_connection = DatabaseConnection()


def initialize_database() -> bool:
    """
    Initialize the database connection.
    
    Returns:
        bool: True if initialization successful, False otherwise
    """
    return db_connection.connect()


def get_database_connection() -> DatabaseConnection:
    """
    Get the global database connection instance.
    
    Returns:
        DatabaseConnection: The database connection instance
    """
    return db_connection