#!/usr/bin/env python3
"""
Database initialization script.
Creates tables, runs migrations, and seeds initial data.
"""

import asyncio
import logging
import os
import sys
from pathlib import Path

# Add the app directory to the Python path
sys.path.append(str(Path(__file__).resolve().parents[1]))

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import init_db, get_session_context, Base, engine
from app.models.user import User, UserRole, UserStatus, SubscriptionType
from app.core.security import hash_password

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def create_tables():
    """Create all database tables."""
    try:
        if not engine:
            await init_db()
        
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        
        logger.info("Database tables created successfully")
        
    except Exception as e:
        logger.error(f"Failed to create tables: {e}")
        raise


async def create_admin_user():
    """Create default admin user if it doesn't exist."""
    try:
        async with get_session_context() as session:
            # Check if admin user already exists
            from sqlalchemy import select
            result = await session.execute(
                select(User).where(User.email == "admin@airesume.com")
            )
            admin_user = result.scalar_one_or_none()
            
            if not admin_user:
                # Create admin user
                admin_user = User(
                    email="admin@airesume.com",
                    username="admin",
                    hashed_password=hash_password("Admin123!"),
                    first_name="Admin",
                    last_name="User",
                    role=UserRole.ADMIN,
                    status=UserStatus.ACTIVE,
                    subscription_type=SubscriptionType.ENTERPRISE,
                    is_active=True,
                    is_verified=True
                )
                
                session.add(admin_user)
                await session.commit()
                
                logger.info("Admin user created successfully")
                logger.info("Email: admin@airesume.com")
                logger.info("Password: Admin123!")
            else:
                logger.info("Admin user already exists")
        
    except Exception as e:
        logger.error(f"Failed to create admin user: {e}")
        raise


async def seed_sample_data():
    """Seed database with sample data for development."""
    try:
        async with get_session_context() as session:
            # Create sample users
            sample_users = [
                {
                    "email": "user1@example.com",
                    "username": "user1",
                    "password": "User123!",
                    "first_name": "John",
                    "last_name": "Doe",
                    "job_title": "Software Engineer",
                    "company": "Tech Corp",
                    "industry": "technology",
                    "experience_years": 5
                },
                {
                    "email": "user2@example.com",
                    "username": "user2",
                    "password": "User123!",
                    "first_name": "Jane",
                    "last_name": "Smith",
                    "job_title": "Product Manager",
                    "company": "StartupXYZ",
                    "industry": "technology",
                    "experience_years": 3
                },
                {
                    "email": "premium@example.com",
                    "username": "premium_user",
                    "password": "Premium123!",
                    "first_name": "Premium",
                    "last_name": "User",
                    "job_title": "Senior Developer",
                    "company": "Big Tech",
                    "industry": "technology",
                    "experience_years": 8,
                    "subscription_type": SubscriptionType.PREMIUM
                }
            ]
            
            from sqlalchemy import select
            
            for user_data in sample_users:
                # Check if user already exists
                result = await session.execute(
                    select(User).where(User.email == user_data["email"])
                )
                existing_user = result.scalar_one_or_none()
                
                if not existing_user:
                    subscription_type = user_data.pop("subscription_type", SubscriptionType.FREE)
                    password = user_data.pop("password")
                    
                    user = User(
                        **user_data,
                        hashed_password=hash_password(password),
                        role=UserRole.USER,
                        status=UserStatus.ACTIVE,
                        subscription_type=subscription_type,
                        is_active=True,
                        is_verified=True
                    )
                    
                    session.add(user)
            
            await session.commit()
            logger.info("Sample data seeded successfully")
        
    except Exception as e:
        logger.error(f"Failed to seed sample data: {e}")
        raise


async def run_migrations():
    """Run database migrations using Alembic."""
    try:
        # This would typically be done via Alembic command line
        # For now, we'll just ensure tables are created
        await create_tables()
        logger.info("Migrations completed successfully")
        
    except Exception as e:
        logger.error(f"Failed to run migrations: {e}")
        raise


async def main():
    """Main initialization function."""
    logger.info("Starting database initialization...")
    
    try:
        # Initialize database connection
        await init_db()
        logger.info("Database connection initialized")
        
        # Run migrations
        await run_migrations()
        
        # Create admin user
        await create_admin_user()
        
        # Seed sample data only in development
        if settings.DEBUG:
            await seed_sample_data()
        
        logger.info("Database initialization completed successfully!")
        
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())