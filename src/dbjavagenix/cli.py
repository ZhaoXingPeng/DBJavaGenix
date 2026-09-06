"""
Command-line interface for DBJavaGenix
"""

import asyncio
import json
import typer
from rich.console import Console
from rich.table import Table
from rich.progress import track
from pathlib import Path
from typing import Optional, List
import os

from .config.config_manager import ConfigManager
from .core.exceptions import DBJavaGenixError
from .core.models import DatabaseConfig, DatabaseType
from .database.connection_manager import connection_manager
from .database.capabilities import supported_database_display_names
from .cli_helpers import (
    handle_db_connect_test,
    handle_db_query_databases,
    handle_db_query_tables,
    handle_db_codegen_analyze,
    handle_db_codegen_generate,
    handle_springboot_read_config,
)
from .utils.dependency_manager import DependencyManager
from .server.mcp_server import run_server
from .database.mcp_tools import (
    get_connection_tools,
    get_table_analysis_tools,
    get_codegen_tools,
    get_springboot_project_tools,
)

app = typer.Typer(
    name="dbjavagenix",
    help="AI-enhanced Java code generator",
    add_completion=False,
    no_args_is_help=True,
)
console = Console()


def _extract_table_name(table: object) -> Optional[str]:
    """Normalize table entries returned by current and legacy MCP adapters."""
    if isinstance(table, str):
        return table
    if isinstance(table, dict):
        name = table.get("table_name") or table.get("name")
        return str(name) if name else None
    return None


def _codegen_result_succeeded(result: Optional[dict]) -> bool:
    """Accept structured success and the legacy adapter's success report text."""
    if not result:
        return False
    return bool(result.get("success") or "Code Generation Complete:" in result.get("error", ""))


def show_ascii_icon():
    """Display the DBJavaGenix ASCII icon"""
    icon_path = Path(__file__).parent.parent / "config" / "ASCII_ICON.txt"
    try:
        if icon_path.exists():
            with open(icon_path, "r", encoding="utf-8") as f:
                icon_content = f.read()
            console.print(f"[bold cyan]{icon_content}[/bold cyan]")
            console.print("[dim]AI-Enhanced Java Code Generator v0.1.0[/dim]")
            console.print("[dim]Author: ZXP | Email: 2638265504@qq.com[/dim]\n")
        else:
            console.print("[bold cyan]DBJavaGenix - AI-Enhanced Java Code Generator[/bold cyan]")
    except Exception:
        console.print("[bold cyan]DBJavaGenix - AI-Enhanced Java Code Generator[/bold cyan]")


@app.command()
def version():
    """Show version information"""
    show_ascii_icon()
    console.print("[bold green]DBJavaGenix v0.1.0[/bold green]")
    console.print("\n[cyan]Features:[/cyan]")
    console.print("  - Database connection and analysis tools")
    console.print("  - AI-enhanced Java code generation")
    console.print("  - Multiple template architectures (MyBatis, MyBatis-Plus)")
    console.print("  - Java project dependency checking")
    console.print("  - MCP server for LLM integration")
    console.print("  - Spring Boot project validation and config reading")
    console.print(
        f"\n[cyan]Supported Databases:[/cyan] {', '.join(supported_database_display_names())}"
    )
    console.print("[cyan]Supported Build Tools:[/cyan] Maven, Gradle")


@app.command()
def init(
    config_path: Optional[str] = typer.Option(
        None, "--config", "-c", help="Configuration file path"
    ),
    force: bool = typer.Option(False, "--force", "-f", help="Overwrite existing configuration"),
):
    """Initialize DBJavaGenix configuration"""
    show_ascii_icon()
    try:
        config_manager = ConfigManager(config_path)

        if Path(config_manager.config_path).exists() and not force:
            console.print(
                f"[yellow]Configuration file already exists: {config_manager.config_path}[/yellow]"
            )
            console.print("Use --force to overwrite")
            return

        # Create default configuration
        config = config_manager.create_default_config()
        config_manager.save_config(config)

        console.print(f"[green]✓[/green] Configuration initialized: {config_manager.config_path}")
        console.print("\n[bold]Next steps:[/bold]")
        console.print("1. Edit the configuration file to set your database and AI service details")
        console.print("2. Run 'dbjavagenix generate' to start generating code")

    except Exception as e:
        console.print(f"[red]Error initializing configuration: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def generate(
    tables: Optional[List[str]] = typer.Option(
        None, "--tables", "-t", help="Tables to generate code for"
    ),
    config_path: Optional[str] = typer.Option(
        None, "--config", "-c", help="Configuration file path"
    ),
    schema: Optional[str] = typer.Option(None, "--schema", "-s", help="Database schema"),
    output_dir: Optional[str] = typer.Option(None, "--output", "-o", help="Output directory"),
    package_name: Optional[str] = typer.Option(None, "--package", "-p", help="Java package name"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview what would be generated"),
):
    """Generate Java code from database tables"""
    show_ascii_icon()
    try:
        console.print("[bold blue]Starting DBJavaGenix code generation...[/bold blue]")

        # Load configuration
        config_manager = ConfigManager(config_path)
        config = config_manager.load_config()

        # Override config with command line arguments
        if output_dir:
            config.generation.output_dir = output_dir
        if package_name:
            config.generation.package_name = package_name

        # Create database connection
        db_config = DatabaseConfig(
            type=DatabaseType(config.database.type),
            host=config.database.host,
            port=config.database.port,
            username=config.database.username,
            password=config.database.password,
            database=config.database.database if hasattr(config.database, "database") else "",
            charset="utf8mb4",
        )

        # Test connection
        result = handle_db_connect_test(
            {
                "host": db_config.host,
                "port": db_config.port,
                "username": db_config.username,
                "password": db_config.password,
                "database": db_config.database,
                "database_type": db_config.type.value,
                "charset": db_config.charset,
            }
        )

        if not result.get("success"):
            console.print(
                f"[red]Database connection failed: {result.get('error', 'Unknown error')}[/red]"
            )
            raise typer.Exit(1)

        connection_id = result["connection_id"]
        console.print(f"[green]✓[/green] Connected to database: {result.get('server_info', '')}")

        # Get available tables if no specific tables requested
        target_tables = []
        if tables:
            target_tables = tables
        else:
            table_query = {"connection_id": connection_id, "database": db_config.database}
            if schema:
                table_query["schema"] = schema
            tables_result = handle_db_query_tables(table_query)

            if tables_result.get("success"):
                all_tables = tables_result["tables"]
                target_tables = [
                    table_name for table in all_tables if (table_name := _extract_table_name(table))
                ]
                console.print(
                    f"[cyan]Found {len(target_tables)} tables to generate:[/cyan] {', '.join(target_tables)}"
                )

        if not target_tables:
            console.print("[yellow]No tables found to generate code[/yellow]")
            connection_manager.close_connection(connection_id)
            return

        if dry_run:
            console.print("[yellow]Dry run mode - would generate code for:[/yellow]")
            for table in target_tables:
                console.print(f"  - {table}")
            connection_manager.close_connection(connection_id)
            return

        # Generate code for each table
        generated_tables = []
        total_tables = len(target_tables)

        with console.status("[bold green]Generating code...") as status:
            for i, table_name in enumerate(target_tables, 1):
                status.update(
                    f"[bold green]Generating code for {table_name} ({i}/{total_tables})..."
                )

                try:
                    # Generate code
                    generation_args = {
                        "connection_id": connection_id,
                        "table_name": table_name,
                        "database": db_config.database,
                        "template_category": "Default",
                        "author": config.generation.author,
                        "package_name": config.generation.package_name,
                        "include_swagger": True,
                        "include_lombok": True,
                        "include_mapstruct": False,
                    }
                    if schema:
                        generation_args["schema"] = schema
                    generate_result = handle_db_codegen_generate(generation_args)

                    if _codegen_result_succeeded(generate_result):
                        generated_tables.append(table_name)
                        console.print(f"[green]✓[/green] Generated code for table {table_name}")
                    else:
                        console.print(
                            f"[red]✗[/red] Failed to generate code for table {table_name}: {generate_result.get('error')}"
                        )
                except Exception as e:
                    console.print(f"[red]✗[/red] Error processing table {table_name}: {e}")
                    continue

        # Clean up connection
        connection_manager.close_connection(connection_id)

        if generated_tables:
            console.print("\n[green]✓[/green] Code generation completed successfully!")
            console.print(f"[green]Generated code for {len(generated_tables)} tables[/green]")

            # Show generated tables
            console.print("\n[bold]Generated Tables:[/bold]")
            for generated_table in generated_tables[:10]:
                console.print(f"  - {generated_table}")
            if len(generated_tables) > 10:
                console.print(f"  ... and {len(generated_tables) - 10} more tables")
        else:
            console.print("[yellow]No files were generated[/yellow]")

    except DBJavaGenixError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Unexpected error: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def list_tables(
    config_path: Optional[str] = typer.Option(
        None, "--config", "-c", help="Configuration file path"
    ),
    schema: Optional[str] = typer.Option(None, "--schema", "-s", help="Database schema"),
):
    """List database tables"""
    show_ascii_icon()
    try:
        console.print("[bold blue]Listing database tables...[/bold blue]")

        # Load configuration
        config_manager = ConfigManager(config_path)
        config = config_manager.load_config()

        # Create database connection
        db_config = DatabaseConfig(
            type=DatabaseType(config.database.type),
            host=config.database.host,
            port=config.database.port,
            username=config.database.username,
            password=config.database.password,
            database=config.database.database if hasattr(config.database, "database") else "",
            charset="utf8mb4",
        )

        # Test connection
        result = handle_db_connect_test(
            {
                "host": db_config.host,
                "port": db_config.port,
                "username": db_config.username,
                "password": db_config.password,
                "database": db_config.database,
                "database_type": db_config.type.value,
                "charset": db_config.charset,
            }
        )

        if not result.get("success"):
            console.print(
                f"[red]Database connection failed: {result.get('error', 'Unknown error')}[/red]"
            )
            raise typer.Exit(1)

        connection_id = result["connection_id"]
        console.print(f"[green]✓[/green] Connected to database: {result.get('server_info', '')}")

        # Get database list first if no specific database
        if not db_config.database:
            db_list_result = handle_db_query_databases({"connection_id": connection_id})
            if db_list_result.get("success"):
                databases = db_list_result["databases"]
                console.print(f"[cyan]Available databases:[/cyan] {', '.join(databases)}")
                if databases:
                    db_config.database = databases[0]  # Use first database
                    console.print(f"[yellow]Using database:[/yellow] {db_config.database}")

        # Get table list
        if db_config.database:
            table_query = {"connection_id": connection_id, "database": db_config.database}
            if schema:
                table_query["schema"] = schema
            tables_result = handle_db_query_tables(table_query)

            if tables_result.get("success"):
                tables = tables_result["tables"]

                if tables:
                    table = Table(title=f"Database Tables in '{db_config.database}'")
                    table.add_column("Table Name", style="cyan")
                    table.add_column("Engine", style="magenta")
                    table.add_column("Comment", style="green")

                    for table_info in tables:
                        table.add_row(
                            table_info.get("table_name", ""),
                            table_info.get("engine", ""),
                            table_info.get("comment", ""),
                        )

                    console.print(table)
                    console.print(f"[green]Found {len(tables)} tables[/green]")
                else:
                    console.print("[yellow]No tables found in database[/yellow]")
            else:
                console.print(f"[red]Failed to list tables: {tables_result.get('error')}[/red]")

        # Clean up connection
        connection_manager.close_connection(connection_id)

    except DBJavaGenixError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Unexpected error: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def check_dependencies(
    project_path: Optional[str] = typer.Argument(
        None, help="Java project path to check (default: current directory)"
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Show detailed dependency information"
    ),
):
    """Check Java project dependencies for generated code compatibility"""
    show_ascii_icon()
    try:
        console.print("[bold blue]Checking Java project dependencies...[/bold blue]")

        # Use current directory if no path provided
        target_path = project_path or "."

        from .utils.dependency_manager import DependencyManager

        manager = DependencyManager()
        result = manager.get_dependency_health_report(target_path)

        if "error" in result:
            console.print(
                f"[red]Error checking dependencies: {result.get('error', 'Unknown error')}[/red]"
            )
            raise typer.Exit(1)

        console.print("\n[bold]Dependency Check Results[/bold]")
        console.print(f"Project Path: {target_path}")
        console.print(f"Build Tool: {result.get('build_tool', 'Unknown')}")
        console.print(
            f"Health Score: [{'green' if result.get('health_score', 0) >= 80 else 'yellow' if result.get('health_score', 0) >= 60 else 'red'}]{result.get('health_score', 0)}%[/]"
        )

        # Show summary
        console.print("\n[cyan]Summary:[/cyan]")
        console.print(f"  - Found Dependencies: {result.get('found_dependencies', 0)}")
        console.print(f"  - Missing Required: {result.get('missing_required', 0)}")
        console.print(f"  - Missing Optional: {result.get('missing_optional', 0)}")

        # Show issues
        issues = result.get("issues", [])
        if issues:
            console.print("\n[red]Issues Found:[/red]")
            for issue in issues:
                console.print(f"  - {issue['description']}: {issue['count']} items")

        # Overall result
        health_score = result.get("health_score", 0)
        if health_score >= 80:
            console.print(
                "\n[green]Project dependencies look good for DBJavaGenix code generation![/green]"
            )
        elif health_score >= 60:
            console.print(
                "\n[yellow]Project has some missing dependencies. Consider adding the suggested dependencies.[/yellow]"
            )
        else:
            console.print(
                "\n[red]Project is missing critical dependencies for proper code generation.[/red]"
            )

    except Exception as e:
        console.print(f"[red]Unexpected error: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def fix_dependencies(
    project_path: Optional[str] = typer.Argument(
        None, help="Java project path to fix (default: current directory)"
    ),
    template_category: str = typer.Option(
        "MybatisPlus-Mixed", "--template", "-t", help="Template category for dependency analysis"
    ),
    database_type: str = typer.Option(
        "mysql", "--database", "-d", help="Database type for driver dependencies"
    ),
):
    """Automatically fix Java project dependencies"""
    show_ascii_icon()
    try:
        console.print("[bold blue]Fixing Java project dependencies...[/bold blue]")

        # Use current directory if no path provided
        target_path = project_path or "."

        from .utils.dependency_manager import DependencyManager

        manager = DependencyManager()

        # Check and fix dependencies
        fix_result = manager.check_and_fix_dependencies(
            project_root=target_path,
            template_category=template_category,
            database_type=database_type,
        )

        console.print("\n[bold]Dependency Fix Results[/bold]")
        console.print(f"Project Path: {target_path}")
        console.print(f"Template Category: {template_category}")
        console.print(f"Database Type: {database_type}")

        # Show analysis results
        analysis_result = fix_result.get("analysis_result", {})
        if analysis_result:
            build_tool = analysis_result.get("build_tool", "Unknown")
            console.print(f"Build Tool: {build_tool}")

            summary = analysis_result.get("summary", {})
            console.print(f"Total Requirements: {summary.get('total_requirements', 0)}")
            console.print(f"Missing Dependencies: {summary.get('missing', 0)}")
            console.print(f"Outdated Dependencies: {summary.get('outdated', 0)}")
            console.print(f"Deprecated Dependencies: {summary.get('deprecated', 0)}")

        # Show auto-add results
        auto_add_result = fix_result.get("auto_add_result", {})
        if auto_add_result.get("success"):
            added_count = auto_add_result.get("added_count", 0)
            if added_count > 0:
                console.print(
                    f"[green]✓[/green] Successfully added {added_count} missing dependencies"
                )
            else:
                console.print("[green]✓[/green] No missing dependencies to add")
        else:
            console.print(
                f"[red]✗[/red] Failed to add dependencies: {auto_add_result.get('message', 'Unknown error')}"
            )

        # Show fix results
        fix_result_data = fix_result.get("fix_result", {})
        if fix_result_data.get("success"):
            if "修复" in fix_result_data.get("message", ""):
                console.print("[green]✓[/green] Successfully fixed deprecated dependencies")
            else:
                console.print("[green]✓[/green] No deprecated dependencies to fix")
        else:
            console.print(
                f"[red]✗[/red] Failed to fix dependencies: {fix_result_data.get('message', 'Unknown error')}"
            )

        # Show validation results
        validation_result = fix_result.get("validation_result", {})
        deprecated_deps = validation_result.get("deprecated", [])
        if deprecated_deps:
            console.print("\n[yellow]Deprecated Dependencies Found:[/yellow]")
            for dep in deprecated_deps:
                console.print(f"  - {dep['dependency']}: {dep['recommendation']}")

        console.print("\n[green]Dependency fixing completed![/green]")

    except Exception as e:
        console.print(f"[red]Unexpected error: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def migration_guide(
    project_path: Optional[str] = typer.Argument(
        None, help="Java project path to analyze (default: current directory)"
    ),
):
    """Generate migration guide for deprecated dependencies"""
    show_ascii_icon()
    try:
        console.print("[bold blue]Generating dependency migration guide...[/bold blue]")

        # Use current directory if no path provided
        target_path = project_path or "."

        from .utils.dependency_manager import DependencyManager

        manager = DependencyManager()

        # Generate migration guide
        guide_result = manager.generate_migration_guide(target_path)

        if not guide_result.get("success"):
            console.print(
                f"[red]Error generating migration guide: {guide_result.get('message', 'Unknown error')}[/red]"
            )
            raise typer.Exit(1)

        build_tool = guide_result.get("build_tool", "Unknown")
        suggestions = guide_result.get("migration_suggestions", [])

        console.print("\n[bold]Dependency Migration Guide[/bold]")
        console.print(f"Project Path: {target_path}")
        console.print(f"Build Tool: {build_tool}")
        console.print(f"Total Suggestions: {guide_result.get('total_suggestions', 0)}")

        if suggestions:
            console.print("\n[red]Migration Required:[/red]")
            for suggestion in suggestions:
                console.print(f"  - {suggestion['dependency']}")
                console.print(f"    → {suggestion['recommendation']}")
        else:
            console.print(
                "\n[green]No deprecated dependencies found. Your project is up to date![/green]"
            )

    except Exception as e:
        console.print(f"[red]Unexpected error: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def analyze(
    table_name: str = typer.Argument(..., help="Table name to analyze"),
    config_path: Optional[str] = typer.Option(
        None, "--config", "-c", help="Configuration file path"
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed analysis"),
):
    """Analyze a specific table for code generation"""
    show_ascii_icon()
    connection_id = None
    try:
        console.print(f"[bold blue]Analyzing table: {table_name}[/bold blue]")

        # Load configuration
        config_manager = ConfigManager(config_path)
        config = config_manager.load_config()
        db_config = DatabaseConfig(
            type=DatabaseType(config.database.type),
            host=config.database.host,
            port=config.database.port,
            username=config.database.username,
            password=config.database.password,
            database=config.database.database,
            charset=getattr(config.database, "charset", "utf8mb4"),
        )
        connection_result = handle_db_connect_test(
            {
                "host": db_config.host,
                "port": db_config.port,
                "username": db_config.username,
                "password": db_config.password,
                "database": db_config.database,
                "database_type": db_config.type.value,
                "charset": db_config.charset,
            }
        )
        if not connection_result.get("success"):
            console.print(
                f"[red]Database connection failed: "
                f"{connection_result.get('error', 'Unknown error')}[/red]"
            )
            raise typer.Exit(1)

        connection_id = connection_result.get("connection_id")
        if not connection_id:
            console.print("[red]Database connection failed: missing connection ID[/red]")
            raise typer.Exit(1)

        generation = config.generation
        template_category = "MybatisPlus-Mixed" if generation.use_mybatis_plus else "Default"
        analysis_result = handle_db_codegen_analyze(
            {
                "connection_id": connection_id,
                "table_name": table_name,
                "database": db_config.database,
                "template_category": template_category,
                "author": generation.author,
                "package_name": generation.package_name,
            }
        )
        if not analysis_result.get("success"):
            console.print(
                f"[red]Table analysis failed: {analysis_result.get('error', 'Unknown error')}[/red]"
            )
            raise typer.Exit(1)

        table_info = analysis_result.get("table_info", {})
        relationships = analysis_result.get("relationships", {})
        console.print(f"[green]✓[/green] Analysis completed for table: {table_name}")
        console.print(f"Columns: {len(table_info.get('columns', []))}")
        console.print(f"Java types: {', '.join(analysis_result.get('java_types', [])) or 'None'}")
        console.print(
            "Relationships: "
            f"{len(relationships.get('primary_keys', []))} primary key(s), "
            f"{len(relationships.get('foreign_keys', []))} foreign key(s), "
            f"{len(relationships.get('indexes', []))} index(es)"
        )
        if verbose:
            console.print("\n[bold]Column details[/bold]")
            for column in table_info.get("columns", []):
                console.print(
                    f"- {column.get('name')} ({column.get('type')}) -> "
                    f"{column.get('java_type', 'Unknown')}"
                )

    except DBJavaGenixError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)
    finally:
        if connection_id:
            connection_manager.close_connection(connection_id)


@app.command()
def read_config(
    project_path: Optional[str] = typer.Option(
        None, "--project", "-p", help="Project root to scan (defaults to CWD)"
    ),
    active_profile: Optional[str] = typer.Option(
        None, "--profile", "-r", help="Active profile to overlay (e.g., dev)"
    ),
    merge_strategy: str = typer.Option(
        "overlay", "--merge", "-m", help="Config merge strategy", case_sensitive=False
    ),
):
    """Read Spring Boot configuration and infer base package"""
    show_ascii_icon()
    try:
        console.print("[bold blue]Reading Spring Boot project configuration...[/bold blue]")
        args = {}
        if project_path:
            args["project_path"] = project_path
        if active_profile:
            args["active_profile"] = active_profile
        if merge_strategy:
            args["merge_strategy"] = merge_strategy

        res = handle_springboot_read_config(args)
        if not res.get("success"):
            console.print(f"[red]Failed: {res.get('error', 'Unknown error')}[/red]")
            raise typer.Exit(1)

        console.print("\n[bold]Project Info[/bold]")
        console.print(f"Project Root: {res.get('project_root')}")
        console.print(f"Build Tool: {res.get('build_tool')}")
        console.print(f"Spring Boot: {res.get('spring_boot_version')}")
        console.print(f"Base Package: {res.get('base_package')}")
        console.print(f"Profiles: {', '.join(res.get('profiles_available', []))}")
        if res.get("active_profile"):
            console.print(f"Active Profile: {res.get('active_profile')}")

        eff = res.get("effective", {})
        server = eff.get("server", {})
        spring = eff.get("spring", {})
        datasource = spring.get("datasource", {})

        console.print("\n[bold]Effective Config (selected)[/bold]")
        console.print(f"app.name: {spring.get('application', {}).get('name')}")
        console.print(f"server.port: {server.get('port')}")
        console.print(f"context-path: {server.get('servlet', {}).get('context-path')}")
        console.print(f"datasource.url: {datasource.get('url')}")

        console.print("\n[green]✓ Configuration read successfully[/green]")
    except Exception as e:
        console.print(f"[red]Unexpected error: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def server(
    config_path: Optional[str] = typer.Option(
        None, "--config", "-c", help="Configuration file path (optional)"
    ),
):
    """Start MCP server for LLM integration"""
    show_ascii_icon()
    try:
        console.print("[bold blue]Starting DBJavaGenix MCP Server...[/bold blue]")

        # MCP服务器无需配置文件即可启动
        if config_path:
            console.print(f"[dim]Using configuration file: {config_path}[/dim]")
            try:
                config_manager = ConfigManager(config_path)
                config = config_manager.load_config()
                console.print("[green]✓[/green] Configuration loaded")
            except Exception as e:
                console.print(f"[yellow]Warning: Failed to load config file: {e}[/yellow]")
                console.print("[yellow]Continuing with dynamic configuration mode...[/yellow]")
        else:
            console.print("[cyan]Running in zero-configuration mode![/cyan]")
            console.print("[dim]All configuration will be provided dynamically by LLM[/dim]")

        # Dynamically compute tool counts and show names for clarity
        try:
            conn_tools = get_connection_tools()
            table_tools = get_table_analysis_tools()
            code_tools = get_codegen_tools()
            spring_tools = get_springboot_project_tools()
            total = len(conn_tools) + len(table_tools) + len(code_tools) + len(spring_tools)

            console.print("\n[cyan]MCP Server Capabilities:[/cyan]")
            console.print(f"- Database connection tools ({len(conn_tools)} tools)")
            console.print(f"- Table structure analysis tools ({len(table_tools)} tools)")
            console.print(f"- Java code generation tools ({len(code_tools)} tools)")
            console.print(f"- Spring Boot project tools ({len(spring_tools)} tools)")
            # List Spring Boot tools explicitly (includes springboot_read_config)
            spring_names = ", ".join(t.name for t in spring_tools)
            console.print(f"  [dim]Spring Boot: {spring_names}[/dim]")
            console.print(f"\n[green]Total: {total} MCP tools available[/green]")
        except Exception:
            # Fallback to a generic message if dynamic loading fails
            console.print("\n[cyan]MCP Server Capabilities:[/cyan]")
            console.print("- Database connection tools")
            console.print("- Table structure analysis tools")
            console.print("- Java code generation tools")
            console.print("- Spring Boot project tools")

        console.print("\n[bold green]Starting MCP server in stdio mode...[/bold green]")
        console.print("[dim]Server ready for LLM integration (no manual interaction needed)[/dim]")
        console.print("[dim]Press Ctrl+C to stop the server[/dim]")

        # 启动 MCP 服务器
        try:
            asyncio.run(run_server())
        except KeyboardInterrupt:
            console.print("\n[yellow]Shutting down server...[/yellow]")
        except Exception as e:
            console.print(f"\n[red]Server error: {e}[/red]")
            raise typer.Exit(1)

    except Exception as e:
        console.print(f"[red]Unexpected error: {e}[/red]")
        raise typer.Exit(1)


def main():
    """Main entry point"""
    app()


if __name__ == "__main__":
    main()
