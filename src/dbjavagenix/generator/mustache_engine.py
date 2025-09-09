"""
Mustache template engine implementation for DBJavaGenix
"""
import os
from typing import Dict, Any, List
from pathlib import Path
import pystache

from ..core.exceptions import TemplateError
from ..core.models import TableInfo, GenerationConfig


class MustacheTemplateEngine:
    """Mustache template engine for code generation"""
    
    def __init__(self, template_dir: str = None):
        """Initialize Mustache template engine
        
        Args:
            template_dir: Directory containing Mustache templates (optional)
        """
        if template_dir:
            self.template_dir = Path(template_dir)
            if not self.template_dir.exists():
                raise TemplateError(f"Template directory not found: {template_dir}")
        else:
            self.template_dir = None
            
        self.renderer = pystache.Renderer(
            string_encoding='utf-8',
            file_encoding='utf-8',
            search_dirs=[str(self.template_dir)] if self.template_dir else []
        )
        
        # 模板缓存
        self._template_cache = {}
    
    def render_template(self, template_name: str, context: Dict[str, Any]) -> str:
        """Render Mustache template with context data
        
        Args:
            template_name: Name of template file (without .mustache extension)
            context: Template context data
            
        Returns:
            Rendered template content
        """
        try:
            template_path = self.template_dir / f"{template_name}.mustache"
            
            if not template_path.exists():
                raise TemplateError(f"Template not found: {template_path}")
            
            with open(template_path, 'r', encoding='utf-8') as f:
                template_content = f.read()
            
            return self.renderer.render(template_content, context)
            
        except Exception as e:
            raise TemplateError(f"Failed to render template {template_name}: {e}")
    
    def render_file(self, template_path: str, context: Dict[str, Any]) -> str:
        """Render Mustache template from file path
        
        Args:
            template_path: Absolute path to template file
            context: Template context data
            
        Returns:
            Rendered template content
        """
        try:
            template_path_obj = Path(template_path)
            
            if not template_path_obj.exists():
                raise TemplateError(f"Template file not found: {template_path}")
            
            # 检查缓存
            if template_path in self._template_cache:
                template_content = self._template_cache[template_path]
            else:
                with open(template_path_obj, 'r', encoding='utf-8') as f:
                    template_content = f.read()
                # 缓存模板内容
                self._template_cache[template_path] = template_content
            
            return self.renderer.render(template_content, context)
            
        except Exception as e:
            raise TemplateError(f"Failed to render template file {template_path}: {e}")
    
    def list_templates(self) -> List[str]:
        """List available templates
        
        Returns:
            List of template names (without .mustache extension)
        """
        templates = []
        for file_path in self.template_dir.rglob("*.mustache"):
            # Get relative path and remove .mustache extension
            rel_path = file_path.relative_to(self.template_dir)
            template_name = str(rel_path.with_suffix(''))
            templates.append(template_name)
        
        return sorted(templates)
    
    def validate_template(self, template_name: str) -> bool:
        """Validate template syntax
        
        Args:
            template_name: Template name to validate
            
        Returns:
            True if template is valid, False otherwise
        """
        try:
            # Try to parse template with empty context
            self.render_template(template_name, {})
            return True
        except Exception:
            return False


class TemplateContext:
    """Helper class to build template context for Java code generation"""
    
    @staticmethod
    def build_entity_context(
        table: TableInfo, 
        config: GenerationConfig
    ) -> Dict[str, Any]:
        """Build context for entity template
        
        Args:
            table: Table information
            config: Generation configuration
            
        Returns:
            Template context dictionary
        """
        return {
            "package": config.package_name,
            "author": config.author,
            "className": table.entity_name,
            "tableName": table.name,
            "comment": table.comment or f"{table.entity_name} entity",
            "useLombok": config.use_lombok,
            "useJPA": config.use_jpa,
            "useSwagger": config.use_swagger,
            "columns": [
                {
                    "name": col.name,
                    "javaName": TemplateContext._to_camel_case(col.name),
                    "javaType": col.java_type,
                    "comment": col.comment or col.name,
                    "isPrimaryKey": col.primary_key,
                    "isNullable": col.nullable,
                    "maxLength": col.max_length,
                    "defaultValue": col.default_value
                }
                for col in table.columns
            ],
            "primaryKeys": table.primary_keys,
            "hasAutoIncrement": any(col.primary_key for col in table.columns),
            "imports": TemplateContext._get_entity_imports(table, config)
        }
    
    @staticmethod
    def build_mapper_context(
        table: TableInfo,
        config: GenerationConfig
    ) -> Dict[str, Any]:
        """Build context for MapStruct mapper template"""
        entity_name = table.entity_name
        dto_name = f"{entity_name}DTO"
        vo_name = f"{entity_name}VO"
        
        return {
            "package": config.package_name,
            "author": config.author,
            "entityName": entity_name,
            "dtoName": dto_name,
            "voName": vo_name,
            "mapperName": f"{entity_name}Mapper",
            "componentModel": config.mapstruct_component_model,
            "unmappedTargetPolicy": config.mapstruct_unmapped_target_policy,
            "columns": [
                {
                    "name": col.name,
                    "javaName": TemplateContext._to_camel_case(col.name),
                    "javaType": col.java_type,
                    "comment": col.comment,
                    "isPrimaryKey": col.primary_key
                }
                for col in table.columns
            ],
            "imports": [
                f"{config.package_name}.entity.{entity_name}",
                f"{config.package_name}.dto.{dto_name}",
                f"{config.package_name}.vo.{vo_name}",
                "org.mapstruct.Mapper",
                "org.mapstruct.factory.Mappers"
            ]
        }
    
    @staticmethod
    def build_dto_context(
        table: TableInfo,
        config: GenerationConfig
    ) -> Dict[str, Any]:
        """Build context for DTO template"""
        return {
            "package": f"{config.package_name}.dto",
            "author": config.author,
            "className": f"{table.entity_name}DTO",
            "comment": f"{table.entity_name} data transfer object",
            "useLombok": config.use_lombok,
            "useSwagger": config.use_swagger,
            "columns": [
                {
                    "name": col.name,
                    "javaName": TemplateContext._to_camel_case(col.name),
                    "javaType": col.java_type,
                    "comment": col.comment or col.name,
                    "isNullable": col.nullable,
                    "maxLength": col.max_length
                }
                for col in table.columns
                if not col.primary_key  # DTO typically excludes primary keys
            ],
            "imports": TemplateContext._get_dto_imports(table, config)
        }
    
    @staticmethod
    def _to_camel_case(snake_str: str) -> str:
        """Convert snake_case to camelCase"""
        components = snake_str.split('_')
        return components[0] + ''.join(word.capitalize() for word in components[1:])
    
    @staticmethod
    def _get_entity_imports(table: TableInfo, config: GenerationConfig) -> List[str]:
        """Get imports for entity class"""
        imports = []
        
        # Java standard imports
        java_types = {col.java_type for col in table.columns}
        if "LocalDateTime" in java_types:
            imports.append("java.time.LocalDateTime")
        if "LocalDate" in java_types:
            imports.append("java.time.LocalDate")
        if "BigDecimal" in java_types:
            imports.append("java.math.BigDecimal")
        
        # Lombok imports
        if config.use_lombok:
            imports.extend([
                "lombok.Data",
                "lombok.NoArgsConstructor",
                "lombok.AllArgsConstructor"
            ])
        
        # JPA imports
        if config.use_jpa:
            imports.extend([
                "javax.persistence.*"
            ])
        
        # Swagger imports
        if config.use_swagger:
            imports.extend([
                "io.swagger.annotations.ApiModel",
                "io.swagger.annotations.ApiModelProperty"
            ])
        
        return sorted(imports)
    
    @staticmethod
    def _get_dto_imports(table: TableInfo, config: GenerationConfig) -> List[str]:
        """Get imports for DTO class"""
        imports = []
        
        # Java standard imports
        java_types = {col.java_type for col in table.columns}
        if "LocalDateTime" in java_types:
            imports.append("java.time.LocalDateTime")
        if "LocalDate" in java_types:
            imports.append("java.time.LocalDate")
        if "BigDecimal" in java_types:
            imports.append("java.math.BigDecimal")
        
        # Lombok imports
        if config.use_lombok:
            imports.extend([
                "lombok.Data",
                "lombok.NoArgsConstructor",
                "lombok.AllArgsConstructor"
            ])
        
        # Validation imports
        imports.extend([
            "javax.validation.constraints.*"
        ])
        
        # Swagger imports
        if config.use_swagger:
            imports.extend([
                "io.swagger.annotations.ApiModel",
                "io.swagger.annotations.ApiModelProperty"
            ])
        
        return sorted(imports)