"""
Test configuration for DBJavaGenix
"""
import pytest
from dbjavagenix.config.config_manager import ConfigManager
from dbjavagenix.core.models import DatabaseType, AIProvider, CodeStyle


def test_config_manager_initialization():
    """Test ConfigManager initialization"""
    config_manager = ConfigManager()
    assert config_manager is not None


def test_create_default_config():
    """Test creating default configuration"""
    config_manager = ConfigManager()
    config = config_manager.create_default_config()
    
    assert config.database.type == DatabaseType.MYSQL
    assert config.ai.provider == AIProvider.OPENAI
    assert config.generation.code_style == CodeStyle.SPRING_BOOT