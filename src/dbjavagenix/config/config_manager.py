"""
Configuration management for DBJavaGenix
"""

import os
import yaml
from pathlib import Path
from typing import Optional, Dict, Any
from urllib.parse import parse_qs, unquote, urlparse
from pydantic import BaseModel, Field

from ..core.models import DatabaseConfig, AIConfig, GenerationConfig
from ..core.exceptions import ConfigurationError


class AppConfig(BaseModel):
    """Main application configuration"""

    database: DatabaseConfig
    ai: AIConfig
    generation: GenerationConfig

    # Global settings
    debug: bool = Field(default=False, description="Enable debug mode")
    log_level: str = Field(default="INFO", description="Logging level")
    log_file: Optional[str] = Field(None, description="Log file path")


class ConfigManager:
    """Configuration manager"""

    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path or self._find_config_file()
        self._config: Optional[AppConfig] = None

    def _find_config_file(self) -> str:
        """Find configuration file"""
        # Priority order: env var -> current dir -> home dir -> default
        paths = [
            os.getenv("DBJAVAGENIX_CONFIG"),
            "./config.yaml",
            "./config.yml",
            os.path.expanduser("~/.dbjavagenix/config.yaml"),
            os.path.expanduser("~/.dbjavagenix/config.yml"),
        ]

        for path in paths:
            if path and Path(path).exists():
                return path

        # Return default path if none found
        return "./config.yaml"

    def load_config(self) -> AppConfig:
        """Load configuration from file"""
        if self._config is not None:
            return self._config

        try:
            if not Path(self.config_path).exists():
                raise ConfigurationError(f"Configuration file not found: {self.config_path}")

            with open(self.config_path, "r", encoding="utf-8") as f:
                config_data = yaml.safe_load(f)

            # Override with environment variables
            config_data = self._apply_env_overrides(config_data)

            self._config = AppConfig(**config_data)
            return self._config

        except Exception as e:
            raise ConfigurationError(f"Failed to load configuration: {e}")

    def _apply_env_overrides(self, config_data: Dict[str, Any]) -> Dict[str, Any]:
        """Apply environment variable overrides"""
        # Database overrides
        if db_url := os.getenv("DATABASE_URL"):
            config_data.setdefault("database", {})
            config_data["database"].update(self._parse_database_url(db_url))

        # AI service overrides
        if api_key := os.getenv("AI_API_KEY"):
            config_data.setdefault("ai", {})
            config_data["ai"]["api_key"] = api_key

        if ai_provider := os.getenv("AI_PROVIDER"):
            config_data.setdefault("ai", {})
            config_data["ai"]["provider"] = ai_provider

        # Generation overrides
        if output_dir := os.getenv("OUTPUT_DIR"):
            config_data.setdefault("generation", {})
            config_data["generation"]["output_dir"] = output_dir

        if package_name := os.getenv("PACKAGE_NAME"):
            config_data.setdefault("generation", {})
            config_data["generation"]["package_name"] = package_name

        return config_data

    @staticmethod
    def _parse_database_url(database_url: str) -> Dict[str, Any]:
        """Convert a conventional DATABASE_URL into ``DatabaseConfig`` fields."""
        parsed = urlparse(database_url)
        scheme = parsed.scheme.lower()
        scheme_aliases = {
            "mysql": ("mysql", 3306),
            "mysql+pymysql": ("mysql", 3306),
            "postgres": ("postgresql", 5432),
            "postgresql": ("postgresql", 5432),
            "sqlite": ("sqlite", 0),
        }
        if scheme not in scheme_aliases:
            raise ConfigurationError(
                "DATABASE_URL scheme must be mysql, postgresql, postgres, or sqlite"
            )

        database_type, default_port = scheme_aliases[scheme]
        query = parse_qs(parsed.query)
        if database_type == "sqlite":
            database = parsed.path or parsed.netloc
            if database == "/:memory:":
                database = ":memory:"
            elif database.startswith("/") and not database.startswith("//"):
                # sqlite:///relative.db is conventionally represented without the URL slash.
                database = database[1:]
            return {
                "type": database_type,
                "host": "",
                "port": 0,
                "database": database,
                "username": "",
                "password": "",
            }

        return {
            "type": database_type,
            "host": parsed.hostname or "",
            "port": parsed.port or default_port,
            "database": parsed.path.lstrip("/"),
            "username": unquote(parsed.username or ""),
            "password": unquote(parsed.password or ""),
            **({"charset": query["charset"][0]} if query.get("charset") else {}),
        }

    def save_config(self, config: AppConfig) -> None:
        """Save configuration to file"""
        try:
            # Ensure directory exists
            Path(self.config_path).parent.mkdir(parents=True, exist_ok=True)

            with open(self.config_path, "w", encoding="utf-8") as f:
                yaml.dump(config.model_dump(), f, default_flow_style=False, allow_unicode=True)

            self._config = config

        except Exception as e:
            raise ConfigurationError(f"Failed to save configuration: {e}")

    def create_default_config(self) -> AppConfig:
        """Create default configuration"""
        return AppConfig(
            database=DatabaseConfig(
                type="mysql",
                host="localhost",
                port=3306,
                database="test",
                username="root",
                password="password",
            ),
            ai=AIConfig(provider="openai", api_key="your-api-key-here"),
            generation=GenerationConfig(output_dir="./generated", package_name="com.example"),
        )
