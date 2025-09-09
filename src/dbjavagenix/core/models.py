"""
Core data models for DBJavaGenix
"""
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
from pydantic import BaseModel, Field


class DatabaseType(str, Enum):
    """Supported database types"""
    MYSQL = "mysql"
    POSTGRESQL = "postgresql"
    SQLITE = "sqlite"
    ORACLE = "oracle"
    SQLSERVER = "sqlserver"


class AIProvider(str, Enum):
    """Supported AI providers"""
    OPENAI = "openai"
    QIANWEN = "qianwen"
    WENXIN = "wenxin"
    LOCAL = "local"


class TemplateEngine(str, Enum):
    """Supported template engines"""
    MUSTACHE = "mustache"
    VELOCITY = "velocity"  # For legacy support


class CodeStyle(str, Enum):
    """Code generation styles"""
    TRADITIONAL = "traditional"  # 传统三层架构
    DDD = "ddd"  # Domain-Driven Design
    SPRING_BOOT = "spring_boot"  # Spring Boot风格


class MappingTool(str, Enum):
    """Object mapping tools"""
    MAPSTRUCT = "mapstruct"  # MapStruct (推荐)
    DOZER = "dozer"  # Dozer (传统)
    MANUAL = "manual"  # 手动映射


@dataclass
class ColumnInfo:
    """Database column information"""
    name: str
    data_type: str
    java_type: str
    nullable: bool = True
    primary_key: bool = False
    foreign_key: Optional[str] = None
    comment: Optional[str] = None
    default_value: Optional[Any] = None
    max_length: Optional[int] = None
    precision: Optional[int] = None
    scale: Optional[int] = None


@dataclass
class TableInfo:
    """Database table information"""
    name: str
    schema: str
    columns: List[ColumnInfo] = field(default_factory=list)
    primary_keys: List[str] = field(default_factory=list)
    foreign_keys: Dict[str, str] = field(default_factory=dict)
    indexes: List[str] = field(default_factory=list)
    comment: Optional[str] = None
    
    @property
    def entity_name(self) -> str:
        """Convert table name to Java class name"""
        return self._to_pascal_case(self.name)
    
    @staticmethod
    def _to_pascal_case(snake_str: str) -> str:
        """Convert snake_case to PascalCase"""
        components = snake_str.split('_')
        return ''.join(word.capitalize() for word in components)


class DatabaseConfig(BaseModel):
    """Database connection configuration"""
    type: DatabaseType = Field(..., description="Database type")
    host: str = Field(..., description="Database host")
    port: int = Field(..., description="Database port")
    database: str = Field(..., description="Database name")
    username: str = Field(..., description="Database username")
    password: str = Field(..., description="Database password")
    charset: str = Field(default="utf8mb4", description="Character set")
    
    @property
    def connection_url(self) -> str:
        """Generate database connection URL"""
        if self.type == DatabaseType.MYSQL:
            return f"mysql+pymysql://{self.username}:{self.password}@{self.host}:{self.port}/{self.database}?charset={self.charset}"
        elif self.type == DatabaseType.POSTGRESQL:
            return f"postgresql://{self.username}:{self.password}@{self.host}:{self.port}/{self.database}"
        elif self.type == DatabaseType.SQLITE:
            return f"sqlite:///{self.database}"
        else:
            raise ValueError(f"Unsupported database type: {self.type}")


class AIConfig(BaseModel):
    """AI service configuration"""
    provider: AIProvider = Field(..., description="AI service provider")
    api_key: str = Field(..., description="API key for AI service")
    base_url: Optional[str] = Field(None, description="Custom base URL")
    model: str = Field(default="gpt-3.5-turbo", description="AI model name")
    temperature: float = Field(default=0.1, ge=0.0, le=2.0, description="Response randomness")
    max_tokens: int = Field(default=2000, ge=1, description="Maximum response tokens")


class GenerationConfig(BaseModel):
    """Code generation configuration"""
    output_dir: str = Field(..., description="Output directory")
    package_name: str = Field(..., description="Java package name")
    code_style: CodeStyle = Field(default=CodeStyle.SPRING_BOOT, description="Code generation style")
    template_engine: TemplateEngine = Field(default=TemplateEngine.MUSTACHE, description="Template engine")
    mapping_tool: MappingTool = Field(default=MappingTool.MAPSTRUCT, description="Object mapping tool")
    author: str = Field(default="ZXP", description="Author name")
    
    # Entity configuration
    entity_suffix: str = Field(default="", description="Entity class suffix")
    use_lombok: bool = Field(default=True, description="Use Lombok annotations")
    use_jpa: bool = Field(default=True, description="Use JPA annotations")
    
    # DAO configuration
    dao_suffix: str = Field(default="Mapper", description="DAO interface suffix")
    use_mybatis_plus: bool = Field(default=True, description="Use MyBatis-Plus")
    
    # Service configuration
    service_suffix: str = Field(default="Service", description="Service interface suffix")
    service_impl_suffix: str = Field(default="ServiceImpl", description="Service implementation suffix")
    
    # Controller configuration
    controller_suffix: str = Field(default="Controller", description="Controller class suffix")
    use_swagger: bool = Field(default=True, description="Use Swagger annotations")
    
    # Additional options
    generate_dto: bool = Field(default=True, description="Generate DTO classes")
    generate_vo: bool = Field(default=True, description="Generate VO classes")
    generate_tests: bool = Field(default=False, description="Generate unit tests")
    
    # MapStruct configuration
    mapstruct_component_model: str = Field(default="spring", description="MapStruct component model")
    mapstruct_unmapped_target_policy: str = Field(default="IGNORE", description="MapStruct unmapped target policy")
    generate_mappers: bool = Field(default=True, description="Generate MapStruct mappers")


@dataclass
class AIAnalysisResult:
    """AI analysis result for table structure"""
    business_domain: str
    entity_suggestions: Dict[str, str]  # table_name -> suggested_class_name
    column_meanings: Dict[str, Dict[str, str]]  # table_name -> {column_name -> meaning}
    relationships: Dict[str, List[str]]  # table_name -> related_tables
    generation_strategy: str
    confidence_score: float = 0.0