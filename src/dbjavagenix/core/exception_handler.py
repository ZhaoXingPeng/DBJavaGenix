"""
Exception handling utilities for DBJavaGenix

This module provides utilities for consistent error handling, logging,
and error response formatting throughout the application.
"""
import logging
import traceback
from typing import Dict, Any, Optional, Callable
from functools import wraps

from .exceptions import DBJavaGenixError


class ExceptionHandler:
    """Centralized exception handling utility"""
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        self.logger = logger or logging.getLogger(__name__)
    
    def handle_exception(self, exception: Exception, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Handle an exception and return a standardized error response
        
        Args:
            exception: The exception to handle
            context: Additional context information
            
        Returns:
            Standardized error response dictionary
        """
        error_response = {
            'success': False,
            'error_type': exception.__class__.__name__,
            'message': str(exception)
        }
        
        if isinstance(exception, DBJavaGenixError):
            # Enhanced handling for our custom exceptions
            error_response.update({
                'error_code': exception.error_code,
                'context': exception.context
            })
            
            # Log with appropriate level based on error type
            log_level = self._get_log_level_for_exception(exception)
            self.logger.log(log_level, f"DBJavaGenix Error: {exception}", extra={
                'error_code': exception.error_code,
                'context': exception.context,
                'additional_context': context
            })
        else:
            # Handle standard Python exceptions
            self.logger.error(f"Unexpected error: {exception}", exc_info=True)
            error_response['traceback'] = traceback.format_exc()
        
        if context:
            error_response['additional_context'] = context
        
        return error_response
    
    def _get_log_level_for_exception(self, exception: DBJavaGenixError) -> int:
        """Determine appropriate log level based on exception type"""
        from .exceptions import (
            ValidationError, ConfigurationError, DatabaseConnectionError,
            AIServiceError, TemplateError, CodeGenerationError
        )
        
        # Critical errors that need immediate attention
        critical_exceptions = (DatabaseConnectionError, ConfigurationError)
        
        # Errors that are expected in normal operation
        warning_exceptions = (ValidationError,)
        
        # Errors that indicate system issues
        error_exceptions = (AIServiceError, TemplateError, CodeGenerationError)
        
        if isinstance(exception, critical_exceptions):
            return logging.CRITICAL
        elif isinstance(exception, warning_exceptions):
            return logging.WARNING
        elif isinstance(exception, error_exceptions):
            return logging.ERROR
        else:
            return logging.INFO


def exception_handler(logger: Optional[logging.Logger] = None, 
                     return_none_on_error: bool = False,
                     reraise: bool = False):
    """
    Decorator for automatic exception handling in functions
    
    Args:
        logger: Logger instance to use
        return_none_on_error: Whether to return None on error instead of error dict
        reraise: Whether to re-raise the exception after handling
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            handler = ExceptionHandler(logger)
            try:
                return func(*args, **kwargs)
            except Exception as e:
                error_response = handler.handle_exception(e, {
                    'function': func.__name__,
                    'args': str(args)[:200],  # Limit length for logging
                    'kwargs': str(kwargs)[:200]
                })
                
                if reraise:
                    raise
                
                if return_none_on_error:
                    return None
                
                return error_response
        
        return wrapper
    return decorator


def safe_execute(func: Callable, *args, **kwargs) -> Dict[str, Any]:
    """
    Safely execute a function and return standardized response
    
    Args:
        func: Function to execute
        *args: Positional arguments
        **kwargs: Keyword arguments
        
    Returns:
        Standardized response with success/error information
    """
    handler = ExceptionHandler()
    
    try:
        result = func(*args, **kwargs)
        return {
            'success': True,
            'result': result
        }
    except Exception as e:
        return handler.handle_exception(e, {
            'function': func.__name__ if hasattr(func, '__name__') else str(func),
            'args': str(args)[:200],
            'kwargs': str(kwargs)[:200]
        })


class ErrorFormatter:
    """Utility for formatting error messages for different outputs"""
    
    @staticmethod
    def format_for_cli(error_dict: Dict[str, Any]) -> str:
        """Format error for CLI display"""
        if not error_dict.get('success', True):
            message = error_dict.get('message', 'Unknown error')
            error_code = error_dict.get('error_code')
            
            if error_code:
                return f"[{error_code}] {message}"
            return message
        return "No error"
    
    @staticmethod
    def format_for_api(error_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Format error for API response"""
        if not error_dict.get('success', True):
            return {
                'error': {
                    'type': error_dict.get('error_type', 'Unknown'),
                    'code': error_dict.get('error_code'),
                    'message': error_dict.get('message', 'Unknown error'),
                    'context': error_dict.get('context', {})
                }
            }
        return {'success': True}
    
    @staticmethod
    def format_for_log(error_dict: Dict[str, Any]) -> str:
        """Format error for logging"""
        if not error_dict.get('success', True):
            parts = [
                f"Error: {error_dict.get('error_type', 'Unknown')}",
                f"Message: {error_dict.get('message', 'Unknown error')}"
            ]
            
            if error_dict.get('error_code'):
                parts.insert(1, f"Code: {error_dict['error_code']}")
            
            if error_dict.get('context'):
                parts.append(f"Context: {error_dict['context']}")
            
            return " | ".join(parts)
        return "No error"


# Convenience functions for common error handling patterns
def handle_database_operation(operation: Callable, *args, **kwargs) -> Dict[str, Any]:
    """Handle database operations with appropriate error handling"""
    from .exceptions import DatabaseConnectionError, DatabaseQueryError, DatabaseAnalysisError
    
    try:
        result = operation(*args, **kwargs)
        return {'success': True, 'result': result}
    except (DatabaseConnectionError, DatabaseQueryError, DatabaseAnalysisError) as e:
        return ExceptionHandler().handle_exception(e)
    except Exception as e:
        # Wrap unexpected errors in DatabaseQueryError
        db_error = DatabaseQueryError(f"Unexpected database error: {str(e)}")
        return ExceptionHandler().handle_exception(db_error)


def handle_template_operation(operation: Callable, *args, **kwargs) -> Dict[str, Any]:
    """Handle template operations with appropriate error handling"""
    from .exceptions import TemplateError, TemplateNotFoundError, TemplateRenderError
    
    try:
        result = operation(*args, **kwargs)
        return {'success': True, 'result': result}
    except (TemplateError, TemplateNotFoundError, TemplateRenderError) as e:
        return ExceptionHandler().handle_exception(e)
    except Exception as e:
        # Wrap unexpected errors in TemplateError
        template_error = TemplateError(f"Unexpected template error: {str(e)}")
        return ExceptionHandler().handle_exception(template_error)


def handle_mcp_operation(operation: Callable, *args, **kwargs) -> Dict[str, Any]:
    """Handle MCP operations with appropriate error handling"""
    from .exceptions import MCPServiceError, MCPToolError, MCPConnectionError
    
    try:
        result = operation(*args, **kwargs)
        return {'success': True, 'result': result}
    except (MCPServiceError, MCPToolError, MCPConnectionError) as e:
        return ExceptionHandler().handle_exception(e)
    except Exception as e:
        # Wrap unexpected errors in MCPServiceError
        mcp_error = MCPServiceError(f"Unexpected MCP error: {str(e)}")
        return ExceptionHandler().handle_exception(mcp_error)