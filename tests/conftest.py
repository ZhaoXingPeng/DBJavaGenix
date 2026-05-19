"""
pytest 配置文件
为所有测试提供通用的 fixtures 和配置
"""
import pytest
import tempfile
import shutil
from pathlib import Path

from src.dbjavagenix.core.models import (
    TableInfo, ColumnInfo, GenerationConfig,
    CodeStyle, TemplateEngine, MappingTool
)


@pytest.fixture
def temp_output_dir():
    """创建临时输出目录"""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir)


@pytest.fixture
def standard_config(temp_output_dir):
    """标准测试配置"""
    return GenerationConfig(
        output_dir=temp_output_dir,
        package_name="com.example.test",
        code_style=CodeStyle.SPRING_BOOT,
        template_engine=TemplateEngine.MUSTACHE,
        mapping_tool=MappingTool.MAPSTRUCT,
        author="ZXP",
        use_lombok=True,
        use_jpa=True,
        use_swagger=True,
        generate_dto=True,
        generate_vo=True,
        generate_mappers=True
    )


@pytest.fixture
def simple_table():
    """简单测试表"""
    return TableInfo(
        name="test_table",
        schema="test_schema",
        comment="测试表",
        columns=[
            ColumnInfo(
                name="id",
                data_type="BIGINT",
                java_type="Long", 
                primary_key=True,
                nullable=False,
                comment="主键"
            ),
            ColumnInfo(
                name="name",
                data_type="VARCHAR(100)",
                java_type="String",
                nullable=False,
                comment="名称"
            )
        ]
    )


@pytest.fixture
def complex_table():
    """复杂测试表"""
    return TableInfo(
        name="complex_table",
        schema="test_schema", 
        comment="复杂测试表",
        columns=[
            ColumnInfo(
                name="id",
                data_type="BIGINT",
                java_type="Long",
                primary_key=True,
                nullable=False,
                comment="主键ID"
            ),
            ColumnInfo(
                name="title",
                data_type="VARCHAR(200)",
                java_type="String",
                nullable=False,
                comment="标题",
                max_length=200
            ),
            ColumnInfo(
                name="content",
                data_type="TEXT",
                java_type="String",
                nullable=True,
                comment="内容"
            ),
            ColumnInfo(
                name="price",
                data_type="DECIMAL(10,2)",
                java_type="BigDecimal",
                nullable=False,
                comment="价格"
            ),
            ColumnInfo(
                name="quantity",
                data_type="INT",
                java_type="Integer",
                nullable=False,
                comment="数量"
            ),
            ColumnInfo(
                name="is_published",
                data_type="TINYINT(1)",
                java_type="Boolean", 
                nullable=False,
                comment="是否发布",
                default_value=False
            ),
            ColumnInfo(
                name="publish_date",
                data_type="DATE",
                java_type="LocalDate",
                nullable=True,
                comment="发布日期"
            ),
            ColumnInfo(
                name="create_time",
                data_type="DATETIME",
                java_type="LocalDateTime",
                nullable=False,
                comment="创建时间"
            ),
            ColumnInfo(
                name="update_time",
                data_type="TIMESTAMP",
                java_type="LocalDateTime",
                nullable=True,
                comment="更新时间"
            )
        ]
    )


@pytest.fixture(params=["Default", "MybatisPlus", "MybatisPlus-Mixed"])
def template_category(request):
    """参数化的模板分类"""
    return request.param


# 测试标记定义
def pytest_configure(config):
    """配置pytest标记"""
    config.addinivalue_line(
        "markers", "unit: 单元测试"
    )
    config.addinivalue_line(
        "markers", "integration: 集成测试"
    )
    config.addinivalue_line(
        "markers", "e2e: 端到端测试"
    )
    config.addinivalue_line(
        "markers", "slow: 慢速测试"
    )
    config.addinivalue_line(
        "markers", "template_default: Default模板测试"
    )
    config.addinivalue_line(
        "markers", "template_mybatis_plus: MybatisPlus模板测试"
    )
    config.addinivalue_line(
        "markers", "template_mixed: MybatisPlus-Mixed模板测试"
    )