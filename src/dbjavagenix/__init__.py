"""
DBJavaGenix - AI-enhanced Java code generator based on MCP service architecture

A powerful tool for generating Java code from database schemas using AI analysis
and intelligent template processing.
"""

__version__ = "0.1.0"
__author__ = "ZXP"
__email__ = "2638265504@qq.com"

from .core.exceptions import DBJavaGenixError
from .core.models import DatabaseConfig, GenerationConfig

__all__ = [
    "DatabaseConfig",
    "GenerationConfig", 
    "DBJavaGenixError",
]