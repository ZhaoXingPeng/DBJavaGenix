"""
Custom exceptions for DBJavaGenix

This module provides comprehensive exception handling for the DBJavaGenix project,
with specific exception types for different error scenarios.
"""
from typing import Optional, Dict, Any


class DBJavaGenixError(Exception):
    """
    Base exception for DBJavaGenix
    
    All custom exceptions inherit from this base class to provide
    consistent error handling throughout the application.
    """
    
    def __init__(self, message: str, error_code: Optional[str] = None, context: Optional[Dict[str, Any]] = None):
        self.message = message
        self.error_code = error_code
        self.context = context or {}
        super().__init__(self.message)
    
    def __str__(self):
        if self.error_code:
            return f"[{self.error_code}] {self.message}"
        return self.message
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for JSON serialization"""
        return {
            'error': self.__class__.__name__,
            'message': self.message,
            'error_code': self.error_code,
            'context': self.context
        }


# Database-related exceptions
class DatabaseConnectionError(DBJavaGenixError):
    """Raised when database connection fails"""
    
    def __init__(self, message: str, host: Optional[str] = None, port: Optional[int] = None, 
                 database: Optional[str] = None, error_code: str = "DB_CONNECTION_FAILED"):
        context = {}
        if host:
            context['host'] = host
        if port:
            context['port'] = port
        if database:
            context['database'] = database
        super().__init__(message, error_code, context)


class DatabaseQueryError(DBJavaGenixError):
    """Raised when database query fails"""
    
    def __init__(self, message: str, query: Optional[str] = None, 
                 error_code: str = "DB_QUERY_FAILED"):
        context = {}
        if query:
            context['query'] = query[:500]  # Limit query length for logging
        super().__init__(message, error_code, context)


class DatabaseAnalysisError(DBJavaGenixError):
    """Raised when database analysis fails"""
    
    def __init__(self, message: str, table_name: Optional[str] = None, 
                 analysis_type: Optional[str] = None, error_code: str = "DB_ANALYSIS_FAILED"):
        context = {}
        if table_name:
            context['table_name'] = table_name
        if analysis_type:
            context['analysis_type'] = analysis_type
        super().__init__(message, error_code, context)


class TableNotFoundError(DatabaseAnalysisError):
    """Raised when specified table is not found"""
    
    def __init__(self, table_name: str, database: Optional[str] = None):
        message = f"Table '{table_name}' not found"
        if database:
            message += f" in database '{database}'"
        super().__init__(message, table_name, "table_lookup", "TABLE_NOT_FOUND")


class InvalidDatabaseTypeError(DatabaseConnectionError):
    """Raised when database type is not supported"""
    
    def __init__(self, database_type: str):
        message = f"Unsupported database type: {database_type}"
        super().__init__(message, error_code="INVALID_DB_TYPE")
        self.context['database_type'] = database_type


# AI Service exceptions
class AIServiceError(DBJavaGenixError):
    """Raised when AI service encounters an error"""
    
    def __init__(self, message: str, service_name: Optional[str] = None, 
                 error_code: str = "AI_SERVICE_ERROR"):
        context = {}
        if service_name:
            context['service_name'] = service_name
        super().__init__(message, error_code, context)


class AIServiceUnavailableError(AIServiceError):
    """Raised when AI service is not available"""
    
    def __init__(self, service_name: str):
        message = f"AI service '{service_name}' is not available"
        super().__init__(message, service_name, "AI_SERVICE_UNAVAILABLE")


class AIAnalysisError(AIServiceError):
    """Raised when AI analysis fails"""
    
    def __init__(self, message: str, analysis_type: Optional[str] = None):
        super().__init__(message, error_code="AI_ANALYSIS_FAILED")
        if analysis_type:
            self.context['analysis_type'] = analysis_type


# Template and Code Generation exceptions
class TemplateError(DBJavaGenixError):
    """Raised when template processing fails"""
    
    def __init__(self, message: str, template_name: Optional[str] = None, 
                 template_type: Optional[str] = None, error_code: str = "TEMPLATE_ERROR"):
        context = {}
        if template_name:
            context['template_name'] = template_name
        if template_type:
            context['template_type'] = template_type
        super().__init__(message, error_code, context)


class TemplateNotFoundError(TemplateError):
    """Raised when template file is not found"""
    
    def __init__(self, template_name: str, template_type: Optional[str] = None):
        message = f"Template '{template_name}' not found"
        if template_type:
            message += f" for template type '{template_type}'"
        super().__init__(message, template_name, template_type, "TEMPLATE_NOT_FOUND")


class TemplateRenderError(TemplateError):
    """Raised when template rendering fails"""
    
    def __init__(self, message: str, template_name: str, render_error: Optional[str] = None):
        super().__init__(message, template_name, error_code="TEMPLATE_RENDER_ERROR")
        if render_error:
            self.context['render_error'] = render_error


class CodeGenerationError(DBJavaGenixError):
    """Raised when code generation fails"""
    
    def __init__(self, message: str, table_name: Optional[str] = None, 
                 generation_stage: Optional[str] = None, error_code: str = "CODE_GENERATION_ERROR"):
        context = {}
        if table_name:
            context['table_name'] = table_name
        if generation_stage:
            context['generation_stage'] = generation_stage
        super().__init__(message, error_code, context)


class InvalidCodeGenerationOptionsError(CodeGenerationError):
    """Raised when code generation options are invalid"""
    
    def __init__(self, message: str, invalid_options: Optional[list] = None):
        super().__init__(message, error_code="INVALID_GENERATION_OPTIONS")
        if invalid_options:
            self.context['invalid_options'] = invalid_options


# Configuration exceptions
class ConfigurationError(DBJavaGenixError):
    """Raised when configuration is invalid"""
    
    def __init__(self, message: str, config_file: Optional[str] = None, 
                 config_section: Optional[str] = None, error_code: str = "CONFIGURATION_ERROR"):
        context = {}
        if config_file:
            context['config_file'] = config_file
        if config_section:
            context['config_section'] = config_section
        super().__init__(message, error_code, context)


class ConfigurationFileNotFoundError(ConfigurationError):
    """Raised when configuration file is not found"""
    
    def __init__(self, config_file: str):
        message = f"Configuration file not found: {config_file}"
        super().__init__(message, config_file, error_code="CONFIG_FILE_NOT_FOUND")


class InvalidConfigurationError(ConfigurationError):
    """Raised when configuration values are invalid"""
    
    def __init__(self, message: str, config_section: str, invalid_keys: Optional[list] = None):
        super().__init__(message, config_section=config_section, error_code="INVALID_CONFIGURATION")
        if invalid_keys:
            self.context['invalid_keys'] = invalid_keys


# MCP Service exceptions
class MCPServiceError(DBJavaGenixError):
    """Raised when MCP service encounters an error"""
    
    def __init__(self, message: str, tool_name: Optional[str] = None, 
                 error_code: str = "MCP_SERVICE_ERROR"):
        context = {}
        if tool_name:
            context['tool_name'] = tool_name
        super().__init__(message, error_code, context)


class MCPToolError(MCPServiceError):
    """Raised when MCP tool execution fails"""
    
    def __init__(self, message: str, tool_name: str, tool_arguments: Optional[Dict[str, Any]] = None):
        super().__init__(message, tool_name, "MCP_TOOL_ERROR")
        if tool_arguments:
            self.context['tool_arguments'] = tool_arguments


class MCPConnectionError(MCPServiceError):
    """Raised when MCP connection fails"""
    
    def __init__(self, message: str, connection_id: Optional[str] = None):
        super().__init__(message, error_code="MCP_CONNECTION_ERROR")
        if connection_id:
            self.context['connection_id'] = connection_id


# Dependency and Project Analysis exceptions
class DependencyCheckError(DBJavaGenixError):
    """Raised when dependency checking fails"""
    
    def __init__(self, message: str, project_path: Optional[str] = None, 
                 build_tool: Optional[str] = None, error_code: str = "DEPENDENCY_CHECK_ERROR"):
        context = {}
        if project_path:
            context['project_path'] = project_path
        if build_tool:
            context['build_tool'] = build_tool
        super().__init__(message, error_code, context)


class UnsupportedBuildToolError(DependencyCheckError):
    """Raised when build tool is not supported"""
    
    def __init__(self, project_path: str):
        message = f"No supported build tool (Maven/Gradle) found in: {project_path}"
        super().__init__(message, project_path, error_code="UNSUPPORTED_BUILD_TOOL")


class BuildFileParseError(DependencyCheckError):
    """Raised when build file parsing fails"""
    
    def __init__(self, message: str, build_file: str, build_tool: str):
        super().__init__(message, build_file, build_tool, "BUILD_FILE_PARSE_ERROR")
        self.context['build_file'] = build_file


# File and I/O exceptions
class FileOperationError(DBJavaGenixError):
    """Raised when file operations fail"""
    
    def __init__(self, message: str, file_path: Optional[str] = None, 
                 operation: Optional[str] = None, error_code: str = "FILE_OPERATION_ERROR"):
        context = {}
        if file_path:
            context['file_path'] = file_path
        if operation:
            context['operation'] = operation
        super().__init__(message, error_code, context)


class OutputDirectoryError(FileOperationError):
    """Raised when output directory operations fail"""
    
    def __init__(self, message: str, output_dir: str):
        super().__init__(message, output_dir, "directory_creation", "OUTPUT_DIRECTORY_ERROR")


# Validation exceptions
class ValidationError(DBJavaGenixError):
    """Raised when input validation fails"""
    
    def __init__(self, message: str, field_name: Optional[str] = None, 
                 field_value: Optional[str] = None, error_code: str = "VALIDATION_ERROR"):
        context = {}
        if field_name:
            context['field_name'] = field_name
        if field_value:
            context['field_value'] = str(field_value)[:100]  # Limit value length
        super().__init__(message, error_code, context)