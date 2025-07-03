"""
API dependencies for authentication, database sessions, and common utilities.
"""

import logging
from typing import Optional, Generator
import uuid

from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.config import settings
from app.core.security import verify_token, get_token_subject
from app.database import get_session
from app.exceptions import (
    AuthenticationException, AuthorizationException, TokenExpiredException,
    InvalidTokenException, UserNotFoundException, AccountSuspendedException,
    RateLimitException
)
from app.models.user import User, UserRole, UserStatus
from app.services.auth_service import AuthService
from app.services.email_service import EmailService
from app.core.security import rate_limiter

logger = logging.getLogger(__name__)

# Security scheme
security = HTTPBearer(auto_error=False)


# Database dependency
async def get_db_session() -> AsyncSession:
    """Get database session dependency."""
    async for session in get_session():
        yield session


# Service dependencies
def get_email_service() -> EmailService:
    """Get email service dependency."""
    return EmailService()


def get_auth_service(
    email_service: EmailService = Depends(get_email_service)
) -> AuthService:
    """Get authentication service dependency."""
    return AuthService(email_service)


# Authentication dependencies
async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    session: AsyncSession = Depends(get_db_session)
) -> Optional[User]:
    """
    Get current user from token (optional).
    Returns None if no token or invalid token.
    """
    if not credentials:
        return None
    
    try:
        # Verify token
        payload = verify_token(credentials.credentials)
        if not payload:
            return None
        
        # Check token type
        if payload.get("type") != "access":
            return None
        
        # Get user ID from token
        user_id = payload.get("sub")
        if not user_id:
            return None
        
        # Get user from database
        result = await session.execute(
            select(User).where(User.id == uuid.UUID(user_id))
        )
        user = result.scalar_one_or_none()
        
        if not user or not user.is_active:
            return None
        
        # Update last activity
        user.update_last_activity()
        await session.commit()
        
        return user
        
    except Exception as e:
        logger.warning(f"Optional authentication failed: {e}")
        return None


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    session: AsyncSession = Depends(get_db_session)
) -> User:
    """
    Get current authenticated user from token.
    Raises exception if not authenticated.
    """
    if not credentials:
        raise AuthenticationException("Authentication required")
    
    try:
        # Verify token
        payload = verify_token(credentials.credentials)
        if not payload:
            raise InvalidTokenException("access token")
        
        # Check token type
        if payload.get("type") != "access":
            raise InvalidTokenException("access token")
        
        # Get user ID from token
        user_id = payload.get("sub")
        if not user_id:
            raise InvalidTokenException("access token")
        
        # Get user from database
        result = await session.execute(
            select(User).where(User.id == uuid.UUID(user_id))
        )
        user = result.scalar_one_or_none()
        
        if not user:
            raise UserNotFoundException()
        
        if not user.is_active:
            raise AccountSuspendedException()
        
        if user.status == UserStatus.SUSPENDED:
            raise AccountSuspendedException()
        
        # Update last activity
        user.update_last_activity()
        await session.commit()
        
        return user
        
    except Exception as e:
        if isinstance(e, (AuthenticationException, UserNotFoundException, AccountSuspendedException)):
            raise
        logger.error(f"Authentication failed: {e}")
        raise AuthenticationException("Invalid authentication credentials")


async def get_current_verified_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Get current user that must be verified.
    """
    if not current_user.is_verified:
        raise AuthenticationException("Email verification required")
    
    return current_user


async def get_current_premium_user(
    current_user: User = Depends(get_current_verified_user)
) -> User:
    """
    Get current user that must have premium subscription.
    """
    if not current_user.is_premium:
        raise AuthorizationException("Premium subscription required")
    
    return current_user


async def get_current_admin_user(
    current_user: User = Depends(get_current_verified_user)
) -> User:
    """
    Get current user that must be admin.
    """
    if current_user.role != UserRole.ADMIN:
        raise AuthorizationException("Admin privileges required")
    
    return current_user


# Rate limiting dependency
async def check_rate_limit(
    request: Request,
    max_requests: int = settings.RATE_LIMIT_REQUESTS,
    window_seconds: int = settings.RATE_LIMIT_PERIOD
):
    """
    Check rate limiting for endpoints.
    """
    if not settings.RATE_LIMIT_ENABLED:
        return
    
    # Get client identifier
    client_ip = request.client.host
    
    # Check if user is authenticated for user-based rate limiting
    try:
        credentials = await security(request)
        if credentials:
            payload = verify_token(credentials.credentials)
            if payload and payload.get("sub"):
                client_ip = f"user:{payload.get('sub')}"
    except:
        pass  # Use IP-based rate limiting
    
    if not rate_limiter.is_allowed(client_ip, max_requests, window_seconds):
        raise RateLimitException(window_seconds)


# Pagination dependency
class PaginationParams:
    """Pagination parameters for list endpoints."""
    
    def __init__(
        self,
        page: int = 1,
        page_size: int = settings.DEFAULT_PAGE_SIZE,
        sort_by: str = "created_at",
        sort_order: str = "desc"
    ):
        self.page = max(1, page)
        self.page_size = min(max(1, page_size), settings.MAX_PAGE_SIZE)
        self.sort_by = sort_by
        self.sort_order = sort_order.lower() if sort_order.lower() in ["asc", "desc"] else "desc"
        
        # Calculate offset
        self.offset = (self.page - 1) * self.page_size
    
    @property
    def limit(self) -> int:
        return self.page_size


def get_pagination_params(
    page: int = 1,
    page_size: int = settings.DEFAULT_PAGE_SIZE,
    sort_by: str = "created_at",
    sort_order: str = "desc"
) -> PaginationParams:
    """Get pagination parameters dependency."""
    return PaginationParams(page, page_size, sort_by, sort_order)


# Request validation dependencies
async def validate_content_type(request: Request):
    """Validate request content type for POST/PUT requests."""
    if request.method in ["POST", "PUT", "PATCH"]:
        content_type = request.headers.get("content-type", "")
        if not content_type.startswith("application/json") and not content_type.startswith("multipart/form-data"):
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail="Content-Type must be application/json or multipart/form-data"
            )


# File upload dependencies
class FileUploadParams:
    """File upload parameters and validation."""
    
    def __init__(self, max_size: int = settings.MAX_FILE_SIZE):
        self.max_size = max_size
        self.allowed_types = settings.ALLOWED_FILE_TYPES


def get_file_upload_params() -> FileUploadParams:
    """Get file upload parameters dependency."""
    return FileUploadParams()


# Security headers dependency
async def add_security_headers(request: Request):
    """Add security headers to response."""
    # This is handled in middleware, but can be used for specific endpoints
    pass


# API key validation (for future API access)
async def validate_api_key(
    request: Request,
    api_key: Optional[str] = None
) -> Optional[str]:
    """
    Validate API key for API access.
    Currently not implemented but prepared for future use.
    """
    # Future implementation for API key authentication
    return api_key


# Feature flag dependencies
class FeatureFlags:
    """Feature flags for enabling/disabling features."""
    
    def __init__(self):
        self.ai_analysis_enabled = bool(settings.OPENAI_API_KEY or settings.ANTHROPIC_API_KEY)
        self.email_notifications_enabled = bool(settings.SMTP_HOST and settings.SMTP_USER)
        self.file_upload_enabled = True
        self.premium_features_enabled = True
        self.admin_features_enabled = True


def get_feature_flags() -> FeatureFlags:
    """Get feature flags dependency."""
    return FeatureFlags()


# Request logging dependency
async def log_request(request: Request):
    """Log request for debugging and monitoring."""
    if settings.DEBUG:
        logger.debug(f"{request.method} {request.url.path} - {request.client.host}")


# CORS preflight dependency
async def handle_cors_preflight(request: Request):
    """Handle CORS preflight requests."""
    if request.method == "OPTIONS":
        return {
            "message": "CORS preflight handled",
            "methods": ["GET", "POST", "PUT", "DELETE", "PATCH"],
            "headers": ["Content-Type", "Authorization"]
        }


# Database transaction dependency
class DatabaseTransaction:
    """Database transaction context manager."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self._in_transaction = False
    
    async def __aenter__(self):
        if not self._in_transaction:
            await self.session.begin()
            self._in_transaction = True
        return self.session
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._in_transaction:
            if exc_type:
                await self.session.rollback()
            else:
                await self.session.commit()
            self._in_transaction = False


async def get_db_transaction(
    session: AsyncSession = Depends(get_db_session)
) -> DatabaseTransaction:
    """Get database transaction dependency."""
    return DatabaseTransaction(session)


# Custom error handling dependency
async def handle_validation_errors(request: Request):
    """Handle validation errors in a consistent way."""
    # This will be used in endpoint error handling
    pass


# Request ID dependency for tracing
async def get_request_id(request: Request) -> str:
    """Get or generate request ID for tracing."""
    request_id = request.headers.get("X-Request-ID")
    if not request_id:
        request_id = str(uuid.uuid4())
    return request_id


# Health check dependency
async def check_service_health():
    """Check if all required services are healthy."""
    health_status = {
        "database": True,  # Will be checked in endpoint
        "email_service": bool(settings.SMTP_HOST),
        "ai_service": bool(settings.OPENAI_API_KEY or settings.ANTHROPIC_API_KEY)
    }
    return health_status


# Export all dependencies
__all__ = [
    # Database
    "get_db_session",
    "get_db_transaction",
    "DatabaseTransaction",
    
    # Services
    "get_email_service",
    "get_auth_service",
    
    # Authentication
    "get_current_user_optional",
    "get_current_user",
    "get_current_verified_user",
    "get_current_premium_user",
    "get_current_admin_user",
    
    # Rate limiting
    "check_rate_limit",
    
    # Pagination
    "get_pagination_params",
    "PaginationParams",
    
    # File upload
    "get_file_upload_params",
    "FileUploadParams",
    
    # Feature flags
    "get_feature_flags",
    "FeatureFlags",
    
    # Utilities
    "validate_content_type",
    "validate_api_key",
    "log_request",
    "handle_cors_preflight",
    "get_request_id",
    "check_service_health"
]