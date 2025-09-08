import logging 
from pathlib import Path
from typing import Optional
import sys

# Handle relative imports
try:
    from .setting_config import settings
except ImportError:
    from setting_config import settings
LOG_FORMAT_DETAILED: str = "%(asctime)s | %(name)s | %(levelname)s | %(filename)s:%(lineno)d | %(funcName)s | %(message)s"
LOG_FORMAT_SIMPLE: str = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
LOG_DATE_FORMAT: str = "%Y-%m-%d %H:%M:%S"

class LoggerConfig:
    """A robust logger configuration class for the Bio-Agent application."""
    
    def __init__(self, name: str = __name__, log_level: Optional[str] = None):
        self.name = name
        self.log_level = log_level or settings.LOG_LEVEL.upper()
        self.log_dir = Path(settings.LOG_DIR)
        self.log_file = self.log_dir / f"{name}.log"
        
        # Create logger
        self.logger = logging.getLogger(name)
        self.logger.setLevel(getattr(logging, self.log_level))
        
        # Prevent duplicate handlers
        if self.logger.handlers:
            return
            
        self._setup_handlers()
        self._setup_formatters()
    
    def _setup_handlers(self):
        """Setup console and file handlers."""
        # Console handler
        if settings.LOG_ENABLE_CONSOLE:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(logging.INFO)
            self.logger.addHandler(console_handler)
        
        # File handler with rotation
        if settings.LOG_ENABLE_FILE:
            try:
                # Ensure log directory exists
                self.log_dir.mkdir(parents=True, exist_ok=True)
                
                # Rotating file handler
                file_handler = logging.handlers.RotatingFileHandler(
                    filename=self.log_file,
                    maxBytes=settings.LOG_MAX_SIZE,
                    backupCount=settings.LOG_BACKUP_COUNT,
                    encoding='utf-8'
                )
                file_handler.setLevel(logging.DEBUG)
                self.logger.addHandler(file_handler)
                
            except Exception as e:
                # Fallback to basic file handler if rotation fails
                try:
                    file_handler = logging.FileHandler(
                        filename=self.log_file,
                        encoding='utf-8'
                    )
                    file_handler.setLevel(logging.DEBUG)
                    self.logger.addHandler(file_handler)
                except Exception as fallback_error:
                    self.logger.warning(f"Failed to setup file logging: {fallback_error}")
    
    def _setup_formatters(self):
        """Setup formatters for different handlers."""
        # Detailed format for file logging
        detailed_format = logging.Formatter(
            fmt=LOG_FORMAT_DETAILED,
            datefmt=LOG_DATE_FORMAT
        )
        
        # Simple format for console logging
        simple_format = logging.Formatter(
            fmt=LOG_FORMAT_SIMPLE,
            datefmt='%H:%M:%S'
        )
        
        # Apply formatters to handlers
        for handler in self.logger.handlers:
            if isinstance(handler, logging.StreamHandler) and handler.stream == sys.stdout:
                handler.setFormatter(simple_format)
            else:
                handler.setFormatter(detailed_format)
    
    def get_logger(self):
        """Get the configured logger instance."""
        return self.logger


# Create default logger instance
logger_config = LoggerConfig()
logger = logger_config.get_logger()


def get_logger(name: str = None, log_level: str = None) -> logging.Logger:
    """
    Get a logger instance with the specified name and log level.
    
    Args:
        name: Logger name (defaults to calling module name)
        log_level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    
    Returns:
        Configured logger instance
    """
    if name is None:
        # Get the calling module name
        import inspect
        frame = inspect.currentframe().f_back
        name = frame.f_globals.get('__name__', __name__)
    
    return LoggerConfig(name, log_level).get_logger()


# Convenience functions for common logging patterns
def log_function_entry(func_name: str, **kwargs):
    """Log function entry with parameters."""
    logger.debug(f"Entering {func_name} with params: {kwargs}")


def log_function_exit(func_name: str, result=None, duration=None):
    """Log function exit with result and duration."""
    if duration:
        logger.debug(f"Exiting {func_name} - Duration: {duration:.3f}s")
    else:
        logger.debug(f"Exiting {func_name}")


def log_error_with_context(error: Exception, context: str = ""):
    """Log error with additional context."""
    logger.error(f"{context}: {str(error)}", exc_info=True)


# Example usage decorator
def log_function_call(func):
    """Decorator to automatically log function entry and exit."""
    import functools
    import time
    
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        func_name = func.__name__
        start_time = time.time()
        
        log_function_entry(func_name, args=args, kwargs=kwargs)
        
        try:
            result = func(*args, **kwargs)
            duration = time.time() - start_time
            log_function_exit(func_name, result=result, duration=duration)
            return result
        except Exception as e:
            duration = time.time() - start_time
            log_error_with_context(e, f"Error in {func_name} after {duration:.3f}s")
            raise
    
    return wrapper


if __name__ == "__main__":
    # Test the logger configuration
    logger.info("Logger configuration initialized successfully")
    logger.debug("This is a debug message")
    logger.warning("This is a warning message")
    logger.error("This is an error message")
    
    # Test the convenience functions
    test_logger = get_logger("test_module")
    test_logger.info("Test logger created successfully")