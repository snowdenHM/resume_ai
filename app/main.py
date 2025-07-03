"""
FastAPI application entry point.
Main application configuration and startup/shutdown event handlers.
"""

import logging
import time
from contextlib import asynccontextmanager
from typing import Any, Dict

import sentry_sdk
from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

from app.api.v1.router import api_router
from app.config import settings
from app.database import init_db, close_db, check_database_health
from app.core.security import rate_limiter
from app.exceptions import (
    CustomHTTPException,
    ValidationException,
    AuthenticationException,
    AuthorizationException
)

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper()),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Prometheus metrics
REQUEST_COUNT = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status_code']
)

REQUEST_DURATION = Histogram(
    'http_request_duration_seconds',
    'HTTP request duration in seconds',
    ['method', 'endpoint']
)

ERROR_COUNT = Counter(
    'http_errors_total',
    'Total HTTP errors',
    ['endpoint', 'error_type']
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management."""
    # Startup
    logger.info("Starting AI Resume Builder API...")
    
    try:
        # Initialize database
        await init_db()
        logger.info("Database initialized successfully")
        
        # Initialize Sentry for error tracking
        # if settings.SENTRY_DSN:
        #     sentry_sdk.init(
        #         dsn=settings.SENTRY_DSN,
        #         integrations=[
        #             FastApiIntegration(auto_enabling=True),
        #             SqlalchemyIntegration()
        #         ],
        #         traces_sample_rate=0.1,
        #         environment="production" if not settings.DEBUG else "development"
        #     )
        #     logger.info("Sentry initialized")
        
        logger.info("Application startup completed")
        
    except Exception as e:
        logger.error(f"Failed to start application: {e}")
        raise
    
    yield
    
    # Shutdown
    logger.info("Shutting down AI Resume Builder API...")
    
    try:
        await close_db()
        logger.info("Database connections closed")
        
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")
    
    logger.info("Application shutdown completed")


def create_application() -> FastAPI:
    """Create and configure FastAPI application."""
    
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description="AI-powered resume builder and optimization platform",
        docs_url="/docs" if settings.DEBUG else None,
        redoc_url="/redoc" if settings.DEBUG else None,
        openapi_url="/openapi.json" if settings.DEBUG else None,
        lifespan=lifespan
    )
    
    # Configure CORS
    if settings.BACKEND_CORS_ORIGINS:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=[str(origin) for origin in settings.BACKEND_CORS_ORIGINS],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    
    # Add security middleware
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["*"] if settings.DEBUG else ["localhost", "127.0.0.1"]
    )
    
    # Add custom middleware
    add_custom_middleware(app)
    
    # Include API routes
    app.include_router(api_router, prefix=settings.API_V1_STR)
    
    # Add exception handlers
    add_exception_handlers(app)
    
    # Add health check endpoints
    add_health_endpoints(app)
    
    return app


def add_custom_middleware(app: FastAPI) -> None:
    """Add custom middleware to the application."""
    
    @app.middleware("http")
    async def request_timing_middleware(request: Request, call_next):
        """Middleware for request timing and metrics."""
        start_time = time.time()
        method = request.method
        path = request.url.path
        
        # Rate limiting
        if settings.RATE_LIMIT_ENABLED:
            client_ip = request.client.host
            if not rate_limiter.is_allowed(client_ip):
                return JSONResponse(
                    status_code=429,
                    content={
                        "detail": "Rate limit exceeded",
                        "retry_after": settings.RATE_LIMIT_PERIOD
                    }
                )
        
        # Process request
        response = await call_next(request)
        
        # Calculate timing
        process_time = time.time() - start_time
        
        # Add timing header
        response.headers["X-Process-Time"] = str(process_time)
        
        # Record metrics
        if settings.ENABLE_METRICS:
            REQUEST_COUNT.labels(
                method=method,
                endpoint=path,
                status_code=response.status_code
            ).inc()
            
            REQUEST_DURATION.labels(
                method=method,
                endpoint=path
            ).observe(process_time)
            
            # Record errors
            if response.status_code >= 400:
                ERROR_COUNT.labels(
                    endpoint=path,
                    error_type=f"{response.status_code}"
                ).inc()
        
        return response
    
    @app.middleware("http")
    async def security_headers_middleware(request: Request, call_next):
        """Add security headers to responses."""
        response = await call_next(request)
        
        # Security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        
        if not settings.DEBUG:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        
        return response


def add_exception_handlers(app: FastAPI) -> None:
    """Add custom exception handlers."""
    
    @app.exception_handler(CustomHTTPException)
    async def custom_http_exception_handler(request: Request, exc: CustomHTTPException):
        """Handle custom HTTP exceptions."""
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "detail": exc.detail,
                "error_code": exc.error_code,
                "timestamp": time.time()
            }
        )
    
    @app.exception_handler(ValidationException)
    async def validation_exception_handler(request: Request, exc: ValidationException):
        """Handle validation exceptions."""
        return JSONResponse(
            status_code=422,
            content={
                "detail": "Validation error",
                "errors": exc.errors,
                "error_code": "VALIDATION_ERROR",
                "timestamp": time.time()
            }
        )
    
    @app.exception_handler(AuthenticationException)
    async def authentication_exception_handler(request: Request, exc: AuthenticationException):
        """Handle authentication exceptions."""
        return JSONResponse(
            status_code=401,
            content={
                "detail": exc.detail,
                "error_code": "AUTHENTICATION_ERROR",
                "timestamp": time.time()
            }
        )
    
    @app.exception_handler(AuthorizationException)
    async def authorization_exception_handler(request: Request, exc: AuthorizationException):
        """Handle authorization exceptions."""
        return JSONResponse(
            status_code=403,
            content={
                "detail": exc.detail,
                "error_code": "AUTHORIZATION_ERROR",
                "timestamp": time.time()
            }
        )
    
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        """Handle standard HTTP exceptions."""
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "detail": exc.detail,
                "error_code": f"HTTP_{exc.status_code}",
                "timestamp": time.time()
            }
        )
    
    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        """Handle unexpected exceptions."""
        logger.error(f"Unexpected error: {exc}", exc_info=True)
        
        if settings.DEBUG:
            return JSONResponse(
                status_code=500,
                content={
                    "detail": str(exc),
                    "error_code": "INTERNAL_SERVER_ERROR",
                    "timestamp": time.time()
                }
            )
        else:
            return JSONResponse(
                status_code=500,
                content={
                    "detail": "Internal server error",
                    "error_code": "INTERNAL_SERVER_ERROR",
                    "timestamp": time.time()
                }
            )


def add_health_endpoints(app: FastAPI) -> None:
    """Add health check and monitoring endpoints."""
    
    @app.get("/health")
    async def health_check():
        """Basic health check endpoint."""
        return {
            "status": "healthy",
            "timestamp": time.time(),
            "version": settings.APP_VERSION
        }
    
    @app.get("/health/detailed")
    async def detailed_health_check():
        """Detailed health check with service dependencies."""
        health_status = {
            "status": "healthy",
            "timestamp": time.time(),
            "version": settings.APP_VERSION,
            "services": {}
        }
        
        # Check database
        try:
            db_healthy = await check_database_health()
            health_status["services"]["database"] = {
                "status": "healthy" if db_healthy else "unhealthy",
                "response_time": None
            }
        except Exception as e:
            health_status["services"]["database"] = {
                "status": "unhealthy",
                "error": str(e)
            }
            health_status["status"] = "unhealthy"
        
        # Check AI service (basic connectivity)
        if settings.OPENAI_API_KEY:
            try:
                import openai
                openai.api_key = settings.OPENAI_API_KEY
                health_status["services"]["ai_service"] = {
                    "status": "configured",
                    "provider": "openai"
                }
            except Exception as e:
                health_status["services"]["ai_service"] = {
                    "status": "error",
                    "error": str(e)
                }
        else:
            health_status["services"]["ai_service"] = {
                "status": "not_configured"
            }
        
        return health_status
    
    @app.get("/metrics")
    async def metrics_endpoint():
        """Prometheus metrics endpoint."""
        if not settings.ENABLE_METRICS:
            raise HTTPException(status_code=404, detail="Metrics not enabled")
        
        return Response(
            content=generate_latest(),
            media_type=CONTENT_TYPE_LATEST
        )
    
    @app.get("/info")
    async def info_endpoint():
        """Application information endpoint."""
        return {
            "name": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "environment": "production" if not settings.DEBUG else "development",
            "features": {
                "debug": settings.DEBUG,
                "metrics": settings.ENABLE_METRICS,
                "rate_limiting": settings.RATE_LIMIT_ENABLED,
                "ai_service": bool(settings.OPENAI_API_KEY or settings.ANTHROPIC_API_KEY)
            }
        }


# Create application instance
app = create_application()


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "message": f"Welcome to {settings.APP_NAME} API",
        "version": settings.APP_VERSION,
        "docs_url": "/docs" if settings.DEBUG else None,
        "health_url": "/health"
    }


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        workers=1 if settings.DEBUG else settings.WORKERS,
        log_level=settings.LOG_LEVEL.lower(),
        access_log=True
    )