#!/usr/bin/env python3
"""
Development server runner script.
Provides easy commands for running the application in development mode.
"""

import argparse
import asyncio
import logging
import os
import subprocess
import sys
from pathlib import Path

# Add the app directory to the Python path
sys.path.append(str(Path(__file__).resolve().parent))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def run_server(host: str = "0.0.0.0", port: int = 8001, reload: bool = True):
    """Run the FastAPI development server."""
    logger.info(f"Starting development server on {host}:{port}")
    
    cmd = [
        "uvicorn",
        "app.main:app",
        "--host", host,
        "--port", str(port),
    ]
    
    if reload:
        cmd.append("--reload")
    
    try:
        subprocess.run(cmd, check=True)
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except subprocess.CalledProcessError as e:
        logger.error(f"Server failed to start: {e}")
        sys.exit(1)


def run_worker():
    """Run Celery worker for background tasks."""
    logger.info("Starting Celery worker...")
    
    cmd = [
        "celery", "-A", "app.workers.celery_app",
        "worker", "--loglevel=info"
    ]
    
    try:
        subprocess.run(cmd, check=True)
    except KeyboardInterrupt:
        logger.info("Worker stopped by user")
    except subprocess.CalledProcessError as e:
        logger.error(f"Worker failed to start: {e}")
        sys.exit(1)


def run_scheduler():
    """Run Celery beat scheduler."""
    logger.info("Starting Celery beat scheduler...")
    
    cmd = [
        "celery", "-A", "app.workers.celery_app",
        "beat", "--loglevel=info"
    ]
    
    try:
        subprocess.run(cmd, check=True)
    except KeyboardInterrupt:
        logger.info("Scheduler stopped by user")
    except subprocess.CalledProcessError as e:
        logger.error(f"Scheduler failed to start: {e}")
        sys.exit(1)


async def init_database():
    """Initialize the database."""
    logger.info("Initializing database...")
    
    try:
        from scripts.init_db import main
        await main()
        logger.info("Database initialization completed")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        sys.exit(1)


def run_migrations():
    """Run database migrations."""
    logger.info("Running database migrations...")
    
    cmd = ["alembic", "upgrade", "head"]
    
    try:
        subprocess.run(cmd, check=True)
        logger.info("Migrations completed successfully")
    except subprocess.CalledProcessError as e:
        logger.error(f"Migrations failed: {e}")
        sys.exit(1)


def create_migration(message: str):
    """Create a new database migration."""
    logger.info(f"Creating migration: {message}")
    
    cmd = ["alembic", "revision", "--autogenerate", "-m", message]
    
    try:
        subprocess.run(cmd, check=True)
        logger.info("Migration created successfully")
    except subprocess.CalledProcessError as e:
        logger.error(f"Migration creation failed: {e}")
        sys.exit(1)


def run_tests():
    """Run the test suite."""
    logger.info("Running tests...")
    
    cmd = ["pytest", "-v", "--cov=app", "--cov-report=html"]
    
    try:
        subprocess.run(cmd, check=True)
        logger.info("Tests completed successfully")
    except subprocess.CalledProcessError as e:
        logger.error(f"Tests failed: {e}")
        sys.exit(1)


def format_code():
    """Format code using black and isort."""
    logger.info("Formatting code...")
    
    try:
        # Run black
        subprocess.run(["black", "app/", "scripts/", "tests/"], check=True)
        logger.info("Black formatting completed")
        
        # Run isort
        subprocess.run(["isort", "app/", "scripts/", "tests/"], check=True)
        logger.info("Import sorting completed")
        
    except subprocess.CalledProcessError as e:
        logger.error(f"Code formatting failed: {e}")
        sys.exit(1)


def lint_code():
    """Lint code using flake8."""
    logger.info("Linting code...")
    
    cmd = ["flake8", "app/", "scripts/", "tests/"]
    
    try:
        subprocess.run(cmd, check=True)
        logger.info("Linting completed successfully")
    except subprocess.CalledProcessError as e:
        logger.error(f"Linting failed: {e}")
        sys.exit(1)


def setup_dev_environment():
    """Set up development environment."""
    logger.info("Setting up development environment...")
    
    # Create .env file if it doesn't exist
    env_file = Path(".env")
    env_example = Path(".env.example")
    
    if not env_file.exists() and env_example.exists():
        env_file.write_text(env_example.read_text())
        logger.info("Created .env file from .env.example")
    
    # Create directories
    directories = ["static/uploads", "logs", "tests"]
    for directory in directories:
        Path(directory).mkdir(parents=True, exist_ok=True)
        logger.info(f"Created directory: {directory}")
    
    logger.info("Development environment setup completed")


def main():
    """Main CLI function."""
    parser = argparse.ArgumentParser(description="AI Resume Builder Development Tools")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Server command
    server_parser = subparsers.add_parser("server", help="Run development server")
    server_parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    server_parser.add_argument("--port", type=int, default=8000, help="Port to bind to")
    server_parser.add_argument("--no-reload", action="store_true", help="Disable auto-reload")
    
    # Worker command
    subparsers.add_parser("worker", help="Run Celery worker")
    
    # Scheduler command
    subparsers.add_parser("scheduler", help="Run Celery beat scheduler")
    
    # Database commands
    subparsers.add_parser("init-db", help="Initialize database")
    subparsers.add_parser("migrate", help="Run database migrations")
    
    # Migration command
    migration_parser = subparsers.add_parser("create-migration", help="Create new migration")
    migration_parser.add_argument("message", help="Migration message")
    
    # Development commands
    subparsers.add_parser("test", help="Run tests")
    subparsers.add_parser("format", help="Format code")
    subparsers.add_parser("lint", help="Lint code")
    subparsers.add_parser("setup", help="Setup development environment")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # Execute commands
    if args.command == "server":
        run_server(args.host, args.port, not args.no_reload)
    elif args.command == "worker":
        run_worker()
    elif args.command == "scheduler":
        run_scheduler()
    elif args.command == "init-db":
        asyncio.run(init_database())
    elif args.command == "migrate":
        run_migrations()
    elif args.command == "create-migration":
        create_migration(args.message)
    elif args.command == "test":
        run_tests()
    elif args.command == "format":
        format_code()
    elif args.command == "lint":
        lint_code()
    elif args.command == "setup":
        setup_dev_environment()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()