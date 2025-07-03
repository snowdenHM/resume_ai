"""
Authentication service with business logic for user management and security.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple
import uuid

from sqlalchemy import select, update, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.core.security import (
    security, hash_password, verify_password, create_access_token,
    create_refresh_token, verify_token, generate_secure_token,
    generate_verification_code, hash_token
)
from app.exceptions import (
    UserNotFoundException, UserAlreadyExistsException, InvalidCredentialsException,
    AccountNotVerifiedException, AccountSuspendedException, TokenExpiredException,
    InvalidTokenException, ValidationException, DatabaseException
)
from app.models.user import User, UserSession, UserVerification, UserStatus, UserRole
from app.schemas.user import UserCreate, UserLogin, PasswordChange
from app.services.email_service import EmailService

logger = logging.getLogger(__name__)


class AuthService:
    """Authentication service for user management and security operations."""
    
    def __init__(self, email_service: EmailService):
        self.email_service = email_service
    
    # User Registration
    async def register_user(
        self, 
        session: AsyncSession, 
        user_data: UserCreate,
        request_ip: Optional[str] = None
    ) -> Tuple[User, str]:
        """
        Register a new user.
        
        Args:
            session: Database session
            user_data: User registration data
            request_ip: Request IP address
            
        Returns:
            Tuple of (User, verification_token)
            
        Raises:
            UserAlreadyExistsException: If email already exists
            ValidationException: If data is invalid
        """
        try:
            # Check if user already exists
            existing_user = await self._get_user_by_email(session, user_data.email)
            if existing_user:
                raise UserAlreadyExistsException(user_data.email)
            
            # Check username uniqueness if provided
            if user_data.username:
                existing_username = await self._get_user_by_username(session, user_data.username)
                if existing_username:
                    raise ValidationException("Username already taken")
            
            # Validate password strength
            password_validation = security.validate_password_strength(user_data.password)
            if not password_validation["is_valid"]:
                raise ValidationException(f"Password validation failed: {', '.join(password_validation['issues'])}")
            
            # Create user
            hashed_password = hash_password(user_data.password)
            user = User(
                email=user_data.email.lower(),
                username=user_data.username,
                hashed_password=hashed_password,
                first_name=user_data.first_name,
                last_name=user_data.last_name,
                phone_number=user_data.phone_number,
                job_title=user_data.job_title,
                company=user_data.company,
                industry=user_data.industry,
                experience_years=user_data.experience_years,
                timezone=user_data.timezone,
                language=user_data.language,
                email_notifications=user_data.email_notifications,
                marketing_emails=user_data.marketing_emails,
                role=UserRole.USER,
                status=UserStatus.PENDING_VERIFICATION,
                is_active=True,
                is_verified=False
            )
            
            session.add(user)
            await session.flush()  # Get user ID
            
            # Create verification token
            verification_token = await self._create_verification_token(
                session, user.id, "email_verification"
            )
            
            await session.commit()
            
            # Send verification email
            try:
                await self.email_service.send_verification_email(
                    user.email, user.first_name or "User", verification_token
                )
            except Exception as e:
                logger.error(f"Failed to send verification email to {user.email}: {e}")
                # Don't fail registration if email fails
            
            logger.info(f"User registered successfully: {user.email}")
            return user, verification_token
            
        except Exception as e:
            await session.rollback()
            if isinstance(e, (UserAlreadyExistsException, ValidationException)):
                raise
            logger.error(f"Registration failed for {user_data.email}: {e}")
            raise DatabaseException("Registration failed")
    
    # User Login
    async def login_user(
        self,
        session: AsyncSession,
        login_data: UserLogin,
        request_ip: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> Dict[str, any]:
        """
        Authenticate user and create session.
        
        Args:
            session: Database session
            login_data: Login credentials
            request_ip: Request IP address
            user_agent: User agent string
            
        Returns:
            Dictionary with tokens and user info
            
        Raises:
            InvalidCredentialsException: If credentials are invalid
            AccountNotVerifiedException: If account is not verified
            AccountSuspendedException: If account is suspended
        """
        try:
            # Get user by email
            user = await self._get_user_by_email(session, login_data.email)
            if not user:
                raise InvalidCredentialsException()
            
            # Verify password
            if not verify_password(login_data.password, user.hashed_password):
                # Log failed attempt
                logger.warning(f"Failed login attempt for {login_data.email} from {request_ip}")
                raise InvalidCredentialsException()
            
            # Check account status
            if user.status == UserStatus.SUSPENDED:
                raise AccountSuspendedException()
            
            if not user.is_verified and user.status == UserStatus.PENDING_VERIFICATION:
                raise AccountNotVerifiedException()
            
            if not user.is_active:
                raise InvalidCredentialsException()
            
            # Update login information
            user.update_login_info()
            
            # Create access and refresh tokens
            token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
            if login_data.remember_me:
                token_expires = timedelta(days=7)  # Extended for remember me
            
            access_token = create_access_token(
                subject=str(user.id),
                expires_delta=token_expires,
                additional_claims={
                    "role": user.role,
                    "email": user.email,
                    "is_verified": user.is_verified
                }
            )
            
            refresh_token = create_refresh_token(subject=str(user.id))
            
            # Create user session
            session_data = await self._create_user_session(
                session, user.id, access_token, refresh_token,
                request_ip, user_agent
            )
            
            await session.commit()
            
            logger.info(f"User logged in successfully: {user.email}")
            
            return {
                "access_token": access_token,
                "refresh_token": refresh_token,
                "token_type": "bearer",
                "expires_in": int(token_expires.total_seconds()),
                "user": user,
                "session_id": session_data.id,
                "is_first_login": user.login_count == 1
            }
            
        except Exception as e:
            await session.rollback()
            if isinstance(e, (InvalidCredentialsException, AccountNotVerifiedException, AccountSuspendedException)):
                raise
            logger.error(f"Login failed for {login_data.email}: {e}")
            raise DatabaseException("Login failed")
    
    # Token Management
    async def refresh_access_token(
        self,
        session: AsyncSession,
        refresh_token: str
    ) -> Dict[str, any]:
        """
        Refresh access token using refresh token.
        
        Args:
            session: Database session
            refresh_token: Refresh token
            
        Returns:
            Dictionary with new tokens
            
        Raises:
            InvalidTokenException: If refresh token is invalid
            TokenExpiredException: If refresh token is expired
        """
        try:
            # Verify refresh token
            payload = verify_token(refresh_token)
            if not payload or payload.get("type") != "refresh":
                raise InvalidTokenException("refresh token")
            
            user_id = payload.get("sub")
            if not user_id:
                raise InvalidTokenException("refresh token")
            
            # Get user and session
            user = await self._get_user_by_id(session, uuid.UUID(user_id))
            if not user or not user.is_active:
                raise InvalidTokenException("refresh token")
            
            # Find active session with this refresh token
            token_hash = hash_token(refresh_token)
            user_session = await session.execute(
                select(UserSession).where(
                    and_(
                        UserSession.user_id == user.id,
                        UserSession.refresh_token_hash == token_hash,
                        UserSession.is_active == True
                    )
                )
            )
            user_session = user_session.scalar_one_or_none()
            
            if not user_session or user_session.is_expired:
                raise TokenExpiredException("refresh token")
            
            # Create new access token
            access_token = create_access_token(
                subject=str(user.id),
                additional_claims={
                    "role": user.role,
                    "email": user.email,
                    "is_verified": user.is_verified
                }
            )
            
            # Update session with new access token
            user_session.token_hash = hash_token(access_token)
            user.update_last_activity()
            
            await session.commit()
            
            return {
                "access_token": access_token,
                "token_type": "bearer",
                "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
                "user": user
            }
            
        except Exception as e:
            await session.rollback()
            if isinstance(e, (InvalidTokenException, TokenExpiredException)):
                raise
            logger.error(f"Token refresh failed: {e}")
            raise DatabaseException("Token refresh failed")
    
    # Logout
    async def logout_user(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        access_token: str
    ) -> bool:
        """
        Logout user and deactivate session.
        
        Args:
            session: Database session
            user_id: User ID
            access_token: Access token to invalidate
            
        Returns:
            True if successful
        """
        try:
            token_hash = hash_token(access_token)
            
            # Deactivate user session
            await session.execute(
                update(UserSession)
                .where(
                    and_(
                        UserSession.user_id == user_id,
                        UserSession.token_hash == token_hash
                    )
                )
                .values(is_active=False)
            )
            
            await session.commit()
            logger.info(f"User logged out: {user_id}")
            return True
            
        except Exception as e:
            await session.rollback()
            logger.error(f"Logout failed for user {user_id}: {e}")
            return False
    
    # Email Verification
    async def verify_email(
        self,
        session: AsyncSession,
        verification_token: str
    ) -> User:
        """
        Verify user email with verification token.
        
        Args:
            session: Database session
            verification_token: Email verification token
            
        Returns:
            Verified user
            
        Raises:
            InvalidTokenException: If token is invalid
            TokenExpiredException: If token is expired
        """
        try:
            # Find verification record
            verification = await session.execute(
                select(UserVerification)
                .options(selectinload(UserVerification.user))
                .where(
                    and_(
                        UserVerification.verification_token == verification_token,
                        UserVerification.verification_type == "email_verification"
                    )
                )
            )
            verification = verification.scalar_one_or_none()
            
            if not verification:
                raise InvalidTokenException("verification token")
            
            if not verification.is_valid:
                if verification.is_expired:
                    raise TokenExpiredException("verification token")
                else:
                    raise InvalidTokenException("verification token")
            
            # Update user verification status
            user = verification.user
            user.is_verified = True
            user.status = UserStatus.ACTIVE
            
            # Mark verification as used
            verification.mark_as_used()
            
            await session.commit()
            
            logger.info(f"Email verified for user: {user.email}")
            return user
            
        except Exception as e:
            await session.rollback()
            if isinstance(e, (InvalidTokenException, TokenExpiredException)):
                raise
            logger.error(f"Email verification failed: {e}")
            raise DatabaseException("Email verification failed")
    
    # Password Management
    async def change_password(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        password_data: PasswordChange
    ) -> bool:
        """
        Change user password.
        
        Args:
            session: Database session
            user_id: User ID
            password_data: Password change data
            
        Returns:
            True if successful
            
        Raises:
            UserNotFoundException: If user not found
            InvalidCredentialsException: If current password is wrong
            ValidationException: If new password is invalid
        """
        try:
            user = await self._get_user_by_id(session, user_id)
            if not user:
                raise UserNotFoundException(str(user_id))
            
            # Verify current password
            if not verify_password(password_data.current_password, user.hashed_password):
                raise InvalidCredentialsException()
            
            # Validate new password
            password_validation = security.validate_password_strength(password_data.new_password)
            if not password_validation["is_valid"]:
                raise ValidationException(f"Password validation failed: {', '.join(password_validation['issues'])}")
            
            # Update password
            user.hashed_password = hash_password(password_data.new_password)
            
            # Deactivate all user sessions (force re-login)
            await session.execute(
                update(UserSession)
                .where(UserSession.user_id == user_id)
                .values(is_active=False)
            )
            
            await session.commit()
            
            logger.info(f"Password changed for user: {user.email}")
            return True
            
        except Exception as e:
            await session.rollback()
            if isinstance(e, (UserNotFoundException, InvalidCredentialsException, ValidationException)):
                raise
            logger.error(f"Password change failed for user {user_id}: {e}")
            raise DatabaseException("Password change failed")
    
    async def request_password_reset(
        self,
        session: AsyncSession,
        email: str
    ) -> bool:
        """
        Request password reset for user.
        
        Args:
            session: Database session
            email: User email
            
        Returns:
            True if successful (always returns True for security)
        """
        try:
            user = await self._get_user_by_email(session, email)
            if not user:
                # Don't reveal if email exists
                logger.warning(f"Password reset requested for non-existent email: {email}")
                return True
            
            # Create reset token
            reset_token = await self._create_verification_token(
                session, user.id, "password_reset", expires_hours=1
            )
            
            await session.commit()
            
            # Send reset email
            try:
                await self.email_service.send_password_reset_email(
                    user.email, user.first_name or "User", reset_token
                )
            except Exception as e:
                logger.error(f"Failed to send password reset email to {user.email}: {e}")
            
            logger.info(f"Password reset requested for: {user.email}")
            return True
            
        except Exception as e:
            await session.rollback()
            logger.error(f"Password reset request failed for {email}: {e}")
            # Always return True for security
            return True
    
    async def reset_password(
        self,
        session: AsyncSession,
        reset_token: str,
        new_password: str
    ) -> User:
        """
        Reset user password with reset token.
        
        Args:
            session: Database session
            reset_token: Password reset token
            new_password: New password
            
        Returns:
            User with reset password
            
        Raises:
            InvalidTokenException: If token is invalid
            TokenExpiredException: If token is expired
            ValidationException: If password is invalid
        """
        try:
            # Find reset verification record
            verification = await session.execute(
                select(UserVerification)
                .options(selectinload(UserVerification.user))
                .where(
                    and_(
                        UserVerification.verification_token == reset_token,
                        UserVerification.verification_type == "password_reset"
                    )
                )
            )
            verification = verification.scalar_one_or_none()
            
            if not verification:
                raise InvalidTokenException("reset token")
            
            if not verification.is_valid:
                if verification.is_expired:
                    raise TokenExpiredException("reset token")
                else:
                    raise InvalidTokenException("reset token")
            
            # Validate new password
            password_validation = security.validate_password_strength(new_password)
            if not password_validation["is_valid"]:
                raise ValidationException(f"Password validation failed: {', '.join(password_validation['issues'])}")
            
            # Update password
            user = verification.user
            user.hashed_password = hash_password(new_password)
            
            # Mark verification as used
            verification.mark_as_used()
            
            # Deactivate all user sessions
            await session.execute(
                update(UserSession)
                .where(UserSession.user_id == user.id)
                .values(is_active=False)
            )
            
            await session.commit()
            
            logger.info(f"Password reset for user: {user.email}")
            return user
            
        except Exception as e:
            await session.rollback()
            if isinstance(e, (InvalidTokenException, TokenExpiredException, ValidationException)):
                raise
            logger.error(f"Password reset failed: {e}")
            raise DatabaseException("Password reset failed")
    
    # Session Management
    async def get_user_sessions(
        self,
        session: AsyncSession,
        user_id: uuid.UUID
    ) -> list[UserSession]:
        """
        Get all active sessions for user.
        
        Args:
            session: Database session
            user_id: User ID
            
        Returns:
            List of active user sessions
        """
        try:
            result = await session.execute(
                select(UserSession)
                .where(
                    and_(
                        UserSession.user_id == user_id,
                        UserSession.is_active == True
                    )
                )
                .order_by(UserSession.created_at.desc())
            )
            return result.scalars().all()
            
        except Exception as e:
            logger.error(f"Failed to get user sessions for {user_id}: {e}")
            return []
    
    async def revoke_session(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        session_id: uuid.UUID
    ) -> bool:
        """
        Revoke a specific user session.
        
        Args:
            session: Database session
            user_id: User ID
            session_id: Session ID to revoke
            
        Returns:
            True if successful
        """
        try:
            await session.execute(
                update(UserSession)
                .where(
                    and_(
                        UserSession.id == session_id,
                        UserSession.user_id == user_id
                    )
                )
                .values(is_active=False)
            )
            
            await session.commit()
            return True
            
        except Exception as e:
            await session.rollback()
            logger.error(f"Failed to revoke session {session_id} for user {user_id}: {e}")
            return False
    
    async def revoke_all_sessions(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        except_session_id: Optional[uuid.UUID] = None
    ) -> bool:
        """
        Revoke all user sessions except optionally one.
        
        Args:
            session: Database session
            user_id: User ID
            except_session_id: Session ID to keep active
            
        Returns:
            True if successful
        """
        try:
            query = update(UserSession).where(UserSession.user_id == user_id)
            
            if except_session_id:
                query = query.where(UserSession.id != except_session_id)
            
            await session.execute(query.values(is_active=False))
            await session.commit()
            return True
            
        except Exception as e:
            await session.rollback()
            logger.error(f"Failed to revoke all sessions for user {user_id}: {e}")
            return False
    
    # Helper Methods
    async def _get_user_by_email(self, session: AsyncSession, email: str) -> Optional[User]:
        """Get user by email."""
        result = await session.execute(
            select(User).where(User.email == email.lower())
        )
        return result.scalar_one_or_none()
    
    async def _get_user_by_username(self, session: AsyncSession, username: str) -> Optional[User]:
        """Get user by username."""
        result = await session.execute(
            select(User).where(User.username == username)
        )
        return result.scalar_one_or_none()
    
    async def _get_user_by_id(self, session: AsyncSession, user_id: uuid.UUID) -> Optional[User]:
        """Get user by ID."""
        result = await session.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()
    
    async def _create_verification_token(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        verification_type: str,
        expires_hours: int = 24
    ) -> str:
        """Create verification token."""
        verification_token = generate_secure_token(32)
        expires_at = datetime.utcnow() + timedelta(hours=expires_hours)
        
        verification = UserVerification(
            user_id=user_id,
            verification_token=verification_token,
            verification_type=verification_type,
            expires_at=expires_at
        )
        
        session.add(verification)
        await session.flush()
        
        return verification_token
    
    async def _create_user_session(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        access_token: str,
        refresh_token: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> UserSession:
        """Create user session."""
        expires_at = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        
        user_session = UserSession(
            user_id=user_id,
            token_hash=hash_token(access_token),
            refresh_token_hash=hash_token(refresh_token),
            expires_at=expires_at,
            ip_address=ip_address,
            user_agent=user_agent,
            device_info={}  # Can be enhanced with device detection
        )
        
        session.add(user_session)
        await session.flush()
        
        return user_session
    
    # Admin Methods
    async def get_user_by_id_admin(
        self,
        session: AsyncSession,
        user_id: uuid.UUID
    ) -> Optional[User]:
        """Get user by ID (admin method with all details)."""
        return await self._get_user_by_id(session, user_id)
    
    async def update_user_status_admin(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        status: UserStatus,
        role: Optional[UserRole] = None
    ) -> Optional[User]:
        """Update user status and role (admin only)."""
        try:
            user = await self._get_user_by_id(session, user_id)
            if not user:
                return None
            
            user.status = status
            if role:
                user.role = role
            
            # If suspending user, deactivate all sessions
            if status == UserStatus.SUSPENDED:
                await session.execute(
                    update(UserSession)
                    .where(UserSession.user_id == user_id)
                    .values(is_active=False)
                )
            
            await session.commit()
            return user
            
        except Exception as e:
            await session.rollback()
            logger.error(f"Failed to update user status for {user_id}: {e}")
            return None


# Export service
__all__ = ["AuthService"]