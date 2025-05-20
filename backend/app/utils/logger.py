import logging
import json
import sys
from typing import Any, Dict, Optional
from pathlib import Path
from datetime import datetime
from app.settings import get_settings

# Get settings instance
settings = get_settings()

class CustomFormatter(logging.Formatter):
    """Custom formatter that includes timestamp and module name"""
    
    def format(self, record):
        # Add timestamp if not present
        if not hasattr(record, 'timestamp'):
            record.timestamp = datetime.utcnow().isoformat()
        
        # Add module name if not present
        if not hasattr(record, 'module_name'):
            record.module_name = record.module
        
        return super().format(record)

def setup_logger(
    name: str,
    log_level: str = "INFO",
    log_file: Optional[str] = None,
    log_format: str = "%(timestamp)s - %(levelname)s - %(module_name)s - %(message)s"
) -> logging.Logger:
    """
    Set up a logger with the specified configuration
    
    Args:
        name: Name of the logger
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional path to log file
        log_format: Format string for log messages
    
    Returns:
        Configured logger instance
    """
    # Create logger
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, log_level.upper()))
    
    # Create formatter
    formatter = CustomFormatter(log_format)
    
    # Add console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # Add file handler if log file specified
    if log_file:
        # Create logs directory if it doesn't exist
        log_path = Path(log_file).parent
        log_path.mkdir(parents=True, exist_ok=True)
        
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    return logger

def log_request(logger: logging.Logger, endpoint: str, data: Dict[str, Any]) -> None:
    """
    Log API request data
    
    Args:
        logger: Logger instance
        endpoint: API endpoint being called
        data: Request data to log
    """
    logger.info(f"Request to {endpoint}: {json.dumps(data, default=str)}")

def log_response(logger: logging.Logger, endpoint: str, data: Dict[str, Any]) -> None:
    """
    Log API response data
    
    Args:
        logger: Logger instance
        endpoint: API endpoint that responded
        data: Response data to log
    """
    logger.info(f"Response from {endpoint}: {json.dumps(data, default=str)}")

def log_error(logger: logging.Logger, endpoint: str, error: Exception, data: Optional[Dict[str, Any]] = None) -> None:
    """
    Log API error
    
    Args:
        logger: Logger instance
        endpoint: API endpoint where error occurred
        error: Exception that was raised
        data: Optional request data that caused the error
    """
    error_msg = f"Error in {endpoint}: {str(error)}"
    if data:
        error_msg += f"\nRequest data: {json.dumps(data, default=str)}"
    logger.error(error_msg, exc_info=True)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

# Create logger
logger = logging.getLogger("genieml")

# Create default logger instance
logger = setup_logger("app") 