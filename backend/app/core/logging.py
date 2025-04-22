# C:\Users\feder\Desktop\MaritimeAPP\backend\app\core\logging.py

import logging
import json
import os
import sys
from datetime import datetime
from logging.handlers import RotatingFileHandler
from typing import Dict, Any, Optional

# Configure logging directory
LOG_DIR = os.getenv("LOG_DIR", "logs")
os.makedirs(LOG_DIR, exist_ok=True)

# Log format for file output
FILE_LOG_FORMAT = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Configure console formatter
CONSOLE_LOG_FORMAT = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Log levels map
LOG_LEVELS = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}


class StructuredLogRecord(logging.LogRecord):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.structured_data = {}


class StructuredLogger(logging.Logger):
    def _log(self, level, msg, args, exc_info=None, extra=None, stack_info=False, stacklevel=1):
        structured_extra = {}
        if extra is not None:
            structured_extra = extra.pop("structured", {}) if "structured" in extra else {}
        
        super()._log(level, msg, args, exc_info, extra, stack_info, stacklevel)
    
    def structured(
        self, 
        level: int, 
        msg: str, 
        structured_data: Dict[str, Any], 
        *args, 
        **kwargs
    ):
        """Log with structured data that can be easily parsed"""
        if self.isEnabledFor(level):
            if "extra" not in kwargs:
                kwargs["extra"] = {}
            kwargs["extra"]["structured"] = structured_data
            self._log(level, msg, args, **kwargs)


class JsonFormatter(logging.Formatter):
    """Format logs as JSON for better parsing"""
    
    def format(self, record):
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "name": record.name,
            "message": record.getMessage(),
        }
        
        # Add structured data if available
        if hasattr(record, "structured_data") and record.structured_data:
            log_data["data"] = record.structured_data
        
        # Add exception info if available
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        return json.dumps(log_data)


def setup_logger(
    name: str, 
    log_level: str = "INFO",
    log_to_file: bool = True,
    log_to_console: bool = True,
    json_format: bool = False
) -> StructuredLogger:
    """
    Set up a structured logger with file and console handlers
    
    Args:
        name: Logger name
        log_level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_to_file: Whether to log to file
        log_to_console: Whether to log to console
        json_format: Whether to format logs as JSON
        
    Returns:
        Configured logger
    """
    # Register the logger class
    logging.setLoggerClass(StructuredLogger)
    
    # Create logger
    logger = logging.getLogger(name)
    logger.setLevel(LOG_LEVELS.get(log_level.upper(), logging.INFO))
    logger.handlers = []  # Clear existing handlers
    
    # Add file handler if requested
    if log_to_file:
        file_handler = RotatingFileHandler(
            os.path.join(LOG_DIR, f"{name}.log"),
            maxBytes=10 * 1024 * 1024,  # 10 MB
            backupCount=5
        )
        
        if json_format:
            file_handler.setFormatter(JsonFormatter())
        else:
            file_handler.setFormatter(FILE_LOG_FORMAT)
            
        logger.addHandler(file_handler)
    
    # Add console handler if requested
    if log_to_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(CONSOLE_LOG_FORMAT)
        logger.addHandler(console_handler)
    
    return logger


# Create application loggers
api_logger = setup_logger("api", log_level=os.getenv("API_LOG_LEVEL", "INFO"))
auth_logger = setup_logger("auth", log_level=os.getenv("AUTH_LOG_LEVEL", "INFO"))
db_logger = setup_logger("db", log_level=os.getenv("DB_LOG_LEVEL", "INFO"))
ai_logger = setup_logger("ai", log_level=os.getenv("AI_LOG_LEVEL", "INFO"), json_format=True)


# Helper function to log API requests
def log_api_request(
    request_id: str,
    method: str,
    path: str,
    status_code: int,
    processing_time: float,
    user_id: Optional[int] = None,
    error: Optional[str] = None
):
    """Log an API request with structured data"""
    data = {
        "request_id": request_id,
        "method": method,
        "path": path,
        "status_code": status_code,
        "processing_time_ms": round(processing_time * 1000, 2),
        "user_id": user_id
    }
    
    if error:
        data["error"] = error
        api_logger.structured(
            logging.ERROR,
            f"API Request: {method} {path} - Status: {status_code}",
            data
        )
    else:
        api_logger.structured(
            logging.INFO,
            f"API Request: {method} {path} - Status: {status_code}",
            data
        )


# Helper function to log authentication events
def log_auth_event(
    event_type: str,
    user_id: Optional[int] = None,
    username: Optional[str] = None,
    success: bool = True,
    error: Optional[str] = None,
    ip_address: Optional[str] = None
):
    """Log an authentication event with structured data"""
    data = {
        "event_type": event_type,
        "user_id": user_id,
        "username": username,
        "success": success,
        "ip_address": ip_address
    }
    
    if error:
        data["error"] = error
        auth_logger.structured(
            logging.WARNING,
            f"Auth {event_type}: {'Success' if success else 'Failed'}",
            data
        )
    else:
        auth_logger.structured(
            logging.INFO,
            f"Auth {event_type}: {'Success' if success else 'Failed'}",
            data
        )


# Helper function to log AI requests
def log_ai_request(
    engine: str,
    prompt_type: str,
    tokens: int,
    processing_time: float,
    user_id: Optional[int] = None,
    error: Optional[str] = None
):
    """Log an AI request with structured data"""
    data = {
        "engine": engine,
        "prompt_type": prompt_type,
        "tokens": tokens,
        "processing_time_ms": round(processing_time * 1000, 2),
        "user_id": user_id
    }
    
    if error:
        data["error"] = error
        ai_logger.structured(
            logging.ERROR,
            f"AI Request: {engine} - Type: {prompt_type}",
            data
        )
    else:
        ai_logger.structured(
            logging.INFO,
            f"AI Request: {engine} - Type: {prompt_type}",
            data
        )