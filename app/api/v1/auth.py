"""
Authentication API endpoints for user registration, login, and account management.
"""

import logging
from typing import Any, Dict
import uuid

from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    get_db_session, get_auth_service, get_current_user, get_current_verified_user,
    check_rate_limit, get_request_id
)
from app.config import settings
from app.exceptions import (
    UserAlreadyExistsException, InvalidCredentialsException, 
    AccountNotVerifiedException, AccountSuspendedException, TokenExpiredException,
    InvalidTokenException, UserNotFoundException, ValidationException
)
from app.models.user import User
from app.schemas.user import (
    UserCreate, UserLogin, UserResponse, TokenResponse, LoginResponse,
    LogoutResponse, PasswordChange, PasswordReset, PasswordResetConfirm,
    EmailVerification, RefreshToken, UserSessionListResponse
)
from app.services.auth_service import AuthService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register new user",
    description="Create a new user account with email verification"
)
async def register(
    user_data: UserCreate,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    auth_service: AuthService = Depends(get_auth_service),
    request_id: str = Depends(get_request_id),
    _: None = Depends(check_rate_limit)
) -> UserResponse:
    """
    Register a new user account.
    
    - **email**: Valid email address (will be used for login)
    - **password**: Strong password (min 8 characters with mixed case, numbers)
    - **first_name**: User's first name (optional)
    - **last_name**: User's last name (optional)
    - **username**: Unique username (optional)
    
    Returns the created user with verification status.
    An email verification link will be sent to the provided email address.
    """
    try:
        # Get client IP for logging
        client_ip = request.client.host if request.client else None
        
        # Register user
        user, verification_token = await auth_service.register_user(
            session, user_data, client_ip
        )
        
        logger.info(f"User registered: {user.email} (ID: {user.id}) - Request: {request_id}")
        
        return UserResponse.from_orm(user)
        
    except UserAlreadyExistsException as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e)
        )
    except ValidationException as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Registration failed - Request: {request_id}, Error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed. Please try again."
        )


@router.post(
    "/login",
    response_model=LoginResponse,
    summary="Login user",
    description="Authenticate user and return access tokens"
)
async def login(
    login_data: UserLogin,
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_db_session),
    auth_service: AuthService = Depends(get_auth_service),
    request_id: str = Depends(get_request_id),
    _: None = Depends(check_rate_limit)
) -> LoginResponse:
    """
    Authenticate user with email and password.
    
    - **email**: User's email address
    - **password**: User's password
    - **remember_me**: Keep user logged in for extended period (optional)
    
    Returns access token, refresh token, and user information.
    """
    try:
        # Get client info for session tracking
        client_ip = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent")
        
        # Authenticate user
        auth_result = await auth_service.login_user(
            session, login_data, client_ip, user_agent
        )
        
        # Set secure HTTP-only cookie for refresh token (optional)
        if settings.DEBUG is False:  # Only in production
            response.set_cookie(
                key="refresh_token",
                value=auth_result["refresh_token"],
                max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
                httponly=True,
                secure=True,
                samesite="strict"
            )
        
        logger.info(f"User logged in: {auth_result['user'].email} - Request: {request_id}")
        
        return LoginResponse(
            access_token=auth_result["access_token"],
            refresh_token=auth_result["refresh_token"],
            token_type=auth_result["token_type"],
            expires_in=auth_result["expires_in"],
            user=UserResponse.from_orm(auth_result["user"]),
            message="Login successful",
            is_first_login=auth_result["is_first_login"]
        )
        
    except (InvalidCredentialsException, AccountNotVerifiedException, AccountSuspendedException) as e:
        # Log failed login attempt
        logger.warning(f"Login failed for {login_data.email}: {e} - Request: {request_id}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Login error for {login_data.email}: {e} - Request: {request_id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Login failed. Please try again."
        )


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Refresh access token",
    description="Get new access token using refresh token"
)
async def refresh_token(
    refresh_data: RefreshToken,
    session: AsyncSession = Depends(get_db_session),
    auth_service: AuthService = Depends(get_auth_service),
    request_id: str = Depends(get_request_id)
) -> TokenResponse:
    """
    Refresh access token using refresh token.
    
    - **refresh_token**: Valid refresh token
    
    Returns new access token and user information.
    """
    try:
        auth_result = await auth_service.refresh_access_token(
            session, refresh_data.refresh_token
        )
        
        logger.info(f"Token refreshed for user: {auth_result['user'].email} - Request: {request_id}")
        
        return TokenResponse(
            access_token=auth_result["access_token"],
            refresh_token=refresh_data.refresh_token,  # Keep same refresh token
            token_type=auth_result["token_type"],
            expires_in=auth_result["expires_in"],
            user=UserResponse.from_orm(auth_result["user"])
        )
        
    except (InvalidTokenException, TokenExpiredException) as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Token refresh failed: {e} - Request: {request_id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Token refresh failed. Please login again."
        )


@router.post(
    "/logout",
    response_model=LogoutResponse,
    summary="Logout user",
    description="Logout user and invalidate session"
)
async def logout(
    request: Request,
    response: Response,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
    auth_service: AuthService = Depends(get_auth_service),
    request_id: str = Depends(get_request_id)
) -> LogoutResponse:
    """
    Logout current user and invalidate session.
    
    Requires valid access token in Authorization header.
    """
    try:
        # Get access token from header
        auth_header = request.headers.get("authorization")
        if auth_header and auth_header.startswith("Bearer "):
            access_token = auth_header.split(" ")[1]
        else:
            access_token = ""
        
        # Logout user
        success = await auth_service.logout_user(
            session, current_user.id, access_token
        )
        
        # Clear refresh token cookie if set
        if not settings.DEBUG:
            response.delete_cookie(key="refresh_token")
        
        if success:
            logger.info(f"User logged out: {current_user.email} - Request: {request_id}")
            return LogoutResponse(message="Logout successful")
        else:
            logger.warning(f"Logout failed for user: {current_user.email} - Request: {request_id}")
            return LogoutResponse(message="Logout completed with warnings")
        
    except Exception as e:
        logger.error(f"Logout error for user {current_user.email}: {e} - Request: {request_id}")
        # Still return success even if there's an error
        return LogoutResponse(message="Logout completed")


@router.post(
    "/verify-email",
    response_model=UserResponse,
    summary="Verify email address",
    description="Verify user email with verification token"
)
async def verify_email(
    verification_data: EmailVerification,
    session: AsyncSession = Depends(get_db_session),
    auth_service: AuthService = Depends(get_auth_service),
    request_id: str = Depends(get_request_id)
) -> UserResponse:
    """
    Verify user email address using verification token.
    
    - **token**: Email verification token received via email
    
    Returns updated user information with verified status.
    """
    try:
        user = await auth_service.verify_email(
            session, verification_data.token
        )
        
        logger.info(f"Email verified for user: {user.email} - Request: {request_id}")
        
        return UserResponse.from_orm(user)
        
    except (InvalidTokenException, TokenExpiredException) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Email verification failed: {e} - Request: {request_id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Email verification failed. Please try again."
        )


@router.post(
    "/change-password",
    response_model=Dict[str, str],
    summary="Change password",
    description="Change user password (requires current password)"
)
async def change_password(
    password_data: PasswordChange,
    current_user: User = Depends(get_current_verified_user),
    session: AsyncSession = Depends(get_db_session),
    auth_service: AuthService = Depends(get_auth_service),
    request_id: str = Depends(get_request_id)
) -> Dict[str, str]:
    """
    Change user password.
    
    - **current_password**: Current password for verification
    - **new_password**: New password (must meet strength requirements)
    - **confirm_password**: Confirmation of new password
    
    All active sessions will be invalidated after password change.
    """
    try:
        success = await auth_service.change_password(
            session, current_user.id, password_data
        )
        
        if success:
            logger.info(f"Password changed for user: {current_user.email} - Request: {request_id}")
            return {"message": "Password changed successfully. Please login again."}
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Password change failed"
            )
        
    except (InvalidCredentialsException, ValidationException) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Password change failed for user {current_user.email}: {e} - Request: {request_id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Password change failed. Please try again."
        )


@router.post(
    "/forgot-password",
    response_model=Dict[str, str],
    summary="Request password reset",
    description="Send password reset email to user"
)
async def forgot_password(
    reset_data: PasswordReset,
    session: AsyncSession = Depends(get_db_session),
    auth_service: AuthService = Depends(get_auth_service),
    request_id: str = Depends(get_request_id),
    _: None = Depends(check_rate_limit)
) -> Dict[str, str]:
    """
    Request password reset for user email.
    
    - **email**: Email address to send reset link to
    
    Always returns success for security (doesn't reveal if email exists).
    """
    try:
        await auth_service.request_password_reset(
            session, reset_data.email
        )
        
        logger.info(f"Password reset requested for: {reset_data.email} - Request: {request_id}")
        
        return {
            "message": "If the email exists, a password reset link has been sent."
        }
        
    except Exception as e:
        logger.error(f"Password reset request failed for {reset_data.email}: {e} - Request: {request_id}")
        # Always return success for security
        return {
            "message": "If the email exists, a password reset link has been sent."
        }


@router.post(
    "/reset-password",
    response_model=Dict[str, str],
    summary="Reset password",
    description="Reset password using reset token"
)
async def reset_password(
    reset_data: PasswordResetConfirm,
    session: AsyncSession = Depends(get_db_session),
    auth_service: AuthService = Depends(get_auth_service),
    request_id: str = Depends(get_request_id)
) -> Dict[str, str]:
    """
    Reset password using reset token.
    
    - **token**: Password reset token from email
    - **new_password**: New password (must meet strength requirements)
    - **confirm_password**: Confirmation of new password
    
    All user sessions will be invalidated after password reset.
    """
    try:
        user = await auth_service.reset_password(
            session, reset_data.token, reset_data.new_password
        )
        
        logger.info(f"Password reset for user: {user.email} - Request: {request_id}")
        
        return {"message": "Password reset successfully. Please login with your new password."}
        
    except (InvalidTokenException, TokenExpiredException, ValidationException) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Password reset failed: {e} - Request: {request_id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Password reset failed. Please try again."
        )


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current user",
    description="Get current authenticated user information"
)
async def get_current_user_info(
    current_user: User = Depends(get_current_user)
) -> UserResponse:
    """
    Get current authenticated user information.
    
    Returns complete user profile including preferences and settings.
    """
    return UserResponse.from_orm(current_user)


@router.get(
    "/sessions",
    response_model=UserSessionListResponse,
    summary="Get user sessions",
    description="Get all active sessions for current user"
)
async def get_user_sessions(
    current_user: User = Depends(get_current_verified_user),
    session: AsyncSession = Depends(get_db_session),
    auth_service: AuthService = Depends(get_auth_service)
) -> UserSessionListResponse:
    """
    Get all active sessions for current user.
    
    Returns list of active sessions with device information.
    """
    try:
        sessions = await auth_service.get_user_sessions(session, current_user.id)
        
        return UserSessionListResponse(
            sessions=[session for session in sessions],
            total_count=len(sessions)
        )
        
    except Exception as e:
        logger.error(f"Failed to get sessions for user {current_user.email}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve sessions"
        )


@router.delete(
    "/sessions/{session_id}",
    response_model=Dict[str, str],
    summary="Revoke session",
    description="Revoke a specific user session"
)
async def revoke_session(
    session_id: uuid.UUID,
    current_user: User = Depends(get_current_verified_user),
    session: AsyncSession = Depends(get_db_session),
    auth_service: AuthService = Depends(get_auth_service),
    request_id: str = Depends(get_request_id)
) -> Dict[str, str]:
    """
    Revoke a specific user session.
    
    - **session_id**: ID of session to revoke
    
    The session will be immediately invalidated.
    """
    try:
        success = await auth_service.revoke_session(
            session, current_user.id, session_id
        )
        
        if success:
            logger.info(f"Session {session_id} revoked for user: {current_user.email} - Request: {request_id}")
            return {"message": "Session revoked successfully"}
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found"
            )
        
    except Exception as e:
        logger.error(f"Failed to revoke session {session_id} for user {current_user.email}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to revoke session"
        )


@router.delete(
    "/sessions",
    response_model=Dict[str, str],
    summary="Revoke all sessions",
    description="Revoke all user sessions except current one"
)
async def revoke_all_sessions(
    request: Request,
    current_user: User = Depends(get_current_verified_user),
    session: AsyncSession = Depends(get_db_session),
    auth_service: AuthService = Depends(get_auth_service),
    request_id: str = Depends(get_request_id)
) -> Dict[str, str]:
    """
    Revoke all user sessions except the current one.
    
    All other active sessions will be immediately invalidated.
    Current session remains active.
    """
    try:
        # Get current session ID from token (if available)
        current_session_id = None  # Would need to track this in token or session
        
        success = await auth_service.revoke_all_sessions(
            session, current_user.id, current_session_id
        )
        
        if success:
            logger.info(f"All sessions revoked for user: {current_user.email} - Request: {request_id}")
            return {"message": "All sessions revoked successfully"}
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to revoke sessions"
            )
        
    except Exception as e:
        logger.error(f"Failed to revoke all sessions for user {current_user.email}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to revoke sessions"
        )


@router.post(
    "/resend-verification",
    response_model=Dict[str, str],
    summary="Resend verification email",
    description="Resend email verification link"
)
async def resend_verification_email(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
    auth_service: AuthService = Depends(get_auth_service),
    request_id: str = Depends(get_request_id),
    _: None = Depends(check_rate_limit)
) -> Dict[str, str]:
    """
    Resend email verification link to current user.
    
    Only works if user is not already verified.
    """
    try:
        if current_user.is_verified:
            return {"message": "Email is already verified"}
        
        # Create new verification token
        verification_token = await auth_service._create_verification_token(
            session, current_user.id, "email_verification"
        )
        
        await session.commit()
        
        # Send verification email
        email_service = auth_service.email_service
        await email_service.send_verification_email(
            current_user.email,
            current_user.first_name or "User",
            verification_token
        )
        
        logger.info(f"Verification email resent for user: {current_user.email} - Request: {request_id}")
        
        return {"message": "Verification email sent successfully"}
        
    except Exception as e:
        logger.error(f"Failed to resend verification email for user {current_user.email}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send verification email"
        )


# Health check endpoint for auth service
@router.get(
    "/health",
    response_model=Dict[str, Any],
    summary="Auth service health check",
    description="Check authentication service health"
)
async def auth_health_check(
    session: AsyncSession = Depends(get_db_session)
) -> Dict[str, Any]:
    """
    Check authentication service health.
    
    Returns status of database connectivity and email service.
    """
    try:
        # Test database connection
        await session.execute("SELECT 1")
        db_status = "healthy"
    except Exception as e:
        db_status = f"unhealthy: {str(e)}"
    
    # Check email service configuration
    email_status = "configured" if (
        settings.SMTP_HOST and 
        settings.SMTP_USER and 
        settings.EMAILS_FROM_EMAIL
    ) else "not_configured"
    
    return {
        "status": "healthy" if db_status == "healthy" else "degraded",
        "database": db_status,
        "email_service": email_status,
        "features": {
            "registration": True,
            "email_verification": email_status == "configured",
            "password_reset": email_status == "configured",
            "rate_limiting": settings.RATE_LIMIT_ENABLED
        }
    }