"""
Centralized configuration module for the GitHub Webhook System.

This module provides a centralized configuration class that loads all
application settings from environment variables with validation and
clear error messages for missing required variables.

Requirements: 9.1, 9.3, 9.4, 9.5, 9.6, 9.7, 9.8
"""

import os
import sys
from typing import Optional
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class ConfigurationError(Exception):
    """Exception raised when required configuration is missing or invalid."""
    pass


class Config:
    """
    Centralized configuration class for the webhook system.
    
    This class loads all configuration from environment variables and validates
    that required variables are present. It provides clear error messages when
    configuration is missing or invalid.
    """
    
    # MongoDB Configuration
    MONGODB_URI: str
    MONGODB_DATABASE: str
    
    # Redis Configuration
    REDIS_URI: str
    
    # Flask Configuration
    SECRET_KEY: str
    FLASK_DEBUG: bool
    FLASK_PORT: int
    FLASK_HOST: str
    FLASK_ENV: str
    
    # Celery Configuration
    CELERY_BROKER_URL: str
    CELERY_RESULT_BACKEND: str
    CELERY_WORKER_CONCURRENCY: int
    CELERY_TASK_MAX_RETRIES: int
    CELERY_TASK_RETRY_DELAY: int
    
    # Logging Configuration
    LOG_LEVEL: str
    LOG_FILE_PATH: str
    LOG_MAX_BYTES: int
    LOG_BACKUP_COUNT: int
    CELERY_LOG_FILE_PATH: str
    
    # Thread Queue Configuration
    WEBHOOK_QUEUE_WORKERS: int
    WEBHOOK_QUEUE_MAX_SIZE: int
    
    # Optional Configuration
    GITHUB_WEBHOOK_SECRET: Optional[str]
    MAX_CONTENT_LENGTH: Optional[int]
    WEBHOOK_TIMEOUT: Optional[int]
    
    @classmethod
    def load(cls) -> None:
        """
        Load and validate all configuration from environment variables.
        
        Raises:
            ConfigurationError: If required environment variables are missing
        """
        # Track missing required variables
        missing_vars = []
        
        # MongoDB Configuration (Required)
        cls.MONGODB_URI = os.getenv('MONGODB_URI', '')
        if not cls.MONGODB_URI:
            missing_vars.append(('MONGODB_URI', 'MongoDB connection string'))
        
        cls.MONGODB_DATABASE = os.getenv('MONGODB_DATABASE', '')
        if not cls.MONGODB_DATABASE:
            missing_vars.append(('MONGODB_DATABASE', 'MongoDB database name'))
        
        # Redis Configuration (Required)
        cls.REDIS_URI = os.getenv('REDIS_URI', '')
        if not cls.REDIS_URI:
            missing_vars.append(('REDIS_URI', 'Redis connection string for Celery'))
        
        # Flask Configuration (Required)
        cls.SECRET_KEY = os.getenv('SECRET_KEY', '')
        if not cls.SECRET_KEY:
            missing_vars.append(('SECRET_KEY', 'Flask secret key for session security'))
        
        # If any required variables are missing, raise error with clear message
        if missing_vars:
            cls._raise_configuration_error(missing_vars)
        
        # Flask Configuration (Optional with defaults)
        cls.FLASK_DEBUG = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
        cls.FLASK_PORT = int(os.getenv('FLASK_PORT', '5000'))
        cls.FLASK_HOST = os.getenv('FLASK_HOST', '0.0.0.0')
        cls.FLASK_ENV = os.getenv('FLASK_ENV', 'development')
        
        # Celery Configuration (Optional with defaults)
        cls.CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL', f'{cls.REDIS_URI}/0')
        cls.CELERY_RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND', f'{cls.REDIS_URI}/1')
        cls.CELERY_WORKER_CONCURRENCY = int(os.getenv('CELERY_WORKER_CONCURRENCY', '4'))
        cls.CELERY_TASK_MAX_RETRIES = int(os.getenv('CELERY_TASK_MAX_RETRIES', '3'))
        cls.CELERY_TASK_RETRY_DELAY = int(os.getenv('CELERY_TASK_RETRY_DELAY', '60'))
        
        # Logging Configuration (Optional with defaults)
        cls.LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO').upper()
        cls.LOG_FILE_PATH = os.getenv('LOG_FILE_PATH', '/app/logs/app.log')
        cls.LOG_MAX_BYTES = int(os.getenv('LOG_MAX_BYTES', '10485760'))  # 10MB
        cls.LOG_BACKUP_COUNT = int(os.getenv('LOG_BACKUP_COUNT', '5'))
        cls.CELERY_LOG_FILE_PATH = os.getenv('CELERY_LOG_FILE_PATH', '/app/logs/celery.log')
        
        # Thread Queue Configuration (Optional with defaults)
        cls.WEBHOOK_QUEUE_WORKERS = int(os.getenv('WEBHOOK_QUEUE_WORKERS', '4'))
        cls.WEBHOOK_QUEUE_MAX_SIZE = int(os.getenv('WEBHOOK_QUEUE_MAX_SIZE', '1000'))
        
        # Optional Configuration
        cls.GITHUB_WEBHOOK_SECRET = os.getenv('GITHUB_WEBHOOK_SECRET')
        
        max_content_length = os.getenv('MAX_CONTENT_LENGTH')
        cls.MAX_CONTENT_LENGTH = int(max_content_length) if max_content_length else None
        
        webhook_timeout = os.getenv('WEBHOOK_TIMEOUT')
        cls.WEBHOOK_TIMEOUT = int(webhook_timeout) if webhook_timeout else None
        
        # Validate log level
        valid_log_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        if cls.LOG_LEVEL not in valid_log_levels:
            print(f"⚠️  Warning: Invalid LOG_LEVEL '{cls.LOG_LEVEL}', defaulting to 'INFO'", file=sys.stderr)
            cls.LOG_LEVEL = 'INFO'
    
    @classmethod
    def _raise_configuration_error(cls, missing_vars: list) -> None:
        """
        Raise a ConfigurationError with a clear, formatted error message.
        
        Args:
            missing_vars: List of tuples (variable_name, description)
            
        Raises:
            ConfigurationError: Always raises with formatted error message
        """
        print("❌ Configuration Validation Failed", file=sys.stderr)
        print("=" * 50, file=sys.stderr)
        print(file=sys.stderr)
        print("🚫 Missing Required Environment Variables:", file=sys.stderr)
        for var_name, description in missing_vars:
            print(f"  - {var_name}: {description}", file=sys.stderr)
        print(file=sys.stderr)
        print("Please copy .env.example to .env and configure the required variables.", file=sys.stderr)
        print(file=sys.stderr)
        print("📖 See README.md for detailed setup instructions.", file=sys.stderr)
        print("=" * 50, file=sys.stderr)
        
        raise ConfigurationError(
            f"Missing required environment variables: {', '.join(v[0] for v in missing_vars)}"
        )
    
    @classmethod
    def print_summary(cls) -> None:
        """Print a summary of the loaded configuration."""
        print("✅ Configuration validation passed", file=sys.stdout)
        print("📋 Configuration Summary:", file=sys.stdout)
        print(f"  - MONGODB_DATABASE: {cls.MONGODB_DATABASE}", file=sys.stdout)
        print(f"  - FLASK_DEBUG: {cls.FLASK_DEBUG}", file=sys.stdout)
        print(f"  - FLASK_PORT: {cls.FLASK_PORT}", file=sys.stdout)
        print(f"  - FLASK_ENV: {cls.FLASK_ENV}", file=sys.stdout)
        print(f"  - LOG_LEVEL: {cls.LOG_LEVEL}", file=sys.stdout)
        print(f"  - LOG_FILE_PATH: {cls.LOG_FILE_PATH}", file=sys.stdout)
        print(f"  - CELERY_WORKER_CONCURRENCY: {cls.CELERY_WORKER_CONCURRENCY}", file=sys.stdout)
        print(f"  - WEBHOOK_QUEUE_WORKERS: {cls.WEBHOOK_QUEUE_WORKERS}", file=sys.stdout)
        print(f"  - WEBHOOK_QUEUE_MAX_SIZE: {cls.WEBHOOK_QUEUE_MAX_SIZE}", file=sys.stdout)
        print(f"  - GITHUB_WEBHOOK_SECRET_SET: {'Yes' if cls.GITHUB_WEBHOOK_SECRET else 'No'}", file=sys.stdout)
        print(file=sys.stdout)


# Load configuration on module import
try:
    Config.load()
except ConfigurationError:
    # Exit with error code if configuration is invalid
    sys.exit(1)
