"""
Centralized logging configuration for agentic components.
This module provides functions to set up consistent logging across the application.
"""
import logging
import os
import sys
from datetime import datetime
from typing import Optional, Dict, Any, Union, List

# Default log format
DEFAULT_LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

# Default log directory
DEFAULT_LOG_DIR = "logs"

def setup_logger(
    name: str, 
    level: int = logging.INFO,
    log_format: str = DEFAULT_LOG_FORMAT,
    log_to_file: bool = True,
    log_to_console: bool = True,
    log_dir: str = DEFAULT_LOG_DIR,
    propagate: bool = False
) -> logging.Logger:
    """
    Set up a logger with consistent formatting and handlers.
    
    Args:
        name: Name of the logger
        level: Logging level (default: INFO)
        log_format: Format string for log messages
        log_to_file: Whether to log to a file
        log_to_console: Whether to log to console
        log_dir: Directory to store log files
        propagate: Whether the logger should propagate to parent loggers
        
    Returns:
        Configured logger instance
    """
    # Get or create the logger
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Clear any existing handlers to avoid duplication
    if logger.handlers:
        logger.handlers.clear()
    
    # Create formatter
    formatter = logging.Formatter(log_format)
    
    # Add console handler if requested
    if log_to_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        console_handler.setLevel(level)
        logger.addHandler(console_handler)
    
    # Add file handler if requested
    if log_to_file:
        # Create log directory if it doesn't exist
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
        
        # Create a log file with date and logger name
        log_file = os.path.join(log_dir, f"{name}_{datetime.now().strftime('%Y%m%d')}.log")
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        file_handler.setLevel(level)
        logger.addHandler(file_handler)
    
    # Set propagation
    logger.propagate = propagate
    
    logger.debug(f"=== {name} Logger Initialized ===")
    return logger

def setup_agent_logger(agent_name: str, level: int = logging.DEBUG) -> logging.Logger:
    """
    Set up a logger specifically for an agent.
    
    Args:
        agent_name: Name of the agent
        level: Logging level (default: DEBUG)
        
    Returns:
        Configured logger instance
    """
    return setup_logger(
        name=f"Agent.{agent_name}",
        level=level,
        log_to_file=True,
        log_to_console=True,
        propagate=False
    )

def setup_root_logger(
    level: int = logging.INFO,
    log_format: str = DEFAULT_LOG_FORMAT,
    log_dir: str = DEFAULT_LOG_DIR
) -> None:
    """
    Configure the root logger for the application.
    
    Args:
        level: Logging level (default: INFO)
        log_format: Format string for log messages
        log_dir: Directory to store log files
    """
    # Create log directory if it doesn't exist
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    # Create a log file with date
    log_file = os.path.join(log_dir, f"app_{datetime.now().strftime('%Y%m%d')}.log")
    
    # Configure root logger
    logging.basicConfig(
        level=level,
        format=log_format,
        handlers=[
            # Output to console
            logging.StreamHandler(sys.stdout),
            # Also log to a file for persistent records
            logging.FileHandler(log_file)
        ]
    )

def get_logger(name: str, level: Optional[int] = None) -> logging.Logger:
    """
    Get an existing logger or create a new one with default settings.
    
    Args:
        name: Name of the logger
        level: Optional logging level override
        
    Returns:
        Logger instance
    """
    logger = logging.getLogger(name)
    
    # If the logger doesn't have handlers, set it up
    if not logger.handlers:
        logger = setup_logger(name, level=level or logging.INFO)
    elif level is not None:
        logger.setLevel(level)
        
    return logger 