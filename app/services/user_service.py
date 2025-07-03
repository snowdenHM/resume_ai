"""
User service for managing user profiles, preferences, and account operations.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
import uuid

from sqlalchemy import select, update, and_, desc, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, joinedload

from app.config import settings
from app.exceptions import (
    UserNotFoundException, ValidationException, DatabaseException,
    PermissionDeniedException
)
from app.models.user import (
    User, UserSession, UserVerification, UserRole, UserStatus, SubscriptionType
)
from app.models.resume import Resume
from app.models.job_description import JobDescription
from app.schemas.user import (
    UserUpdate, UserResponse, UserStatsResponse, UserPreferencesUpdate,
    UserPreferencesResponse, UserAdminUpdate, UserListResponse,
    UserSearchRequest, UserSessionResponse, UserSessionListResponse
)
from app.services.email_service import EmailService

logger = logging.getLogger(__name__)


class UserService:
    """Service for user management and profile operations."""
    
    def __init__(self, email_service: EmailService):
        self.email_service = email_service
    
    async def get_user_profile(
        self,
        session: AsyncSession,
        user_id: uuid.UUID
    ) -> User:
        """
        Get user profile by ID.
        
        Args:
            session: Database session
            user_id: User ID
            
        Returns:
            User profile
        """
        try:
            result = await session.execute(
                select(User).where(User.id == user_id)
            )
            user = result.scalar_one_or_none()
            
            if not user:
                raise UserNotFoundException(str(user_id))
            
            # Update last activity
            user.update_last_activity()
            await session.commit()
            
            return user
            
        except Exception as e:
            if isinstance(e, UserNotFoundException):
                raise
            logger.error(f"Failed to get user profile {user_id}: {e}")
            raise DatabaseException(f"Failed to retrieve user profile: {str(e)}")
    
    async def update_user_profile(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        user_data: UserUpdate
    ) -> User:
        """
        Update user profile.
        
        Args:
            session: Database session
            user_id: User ID
            user_data: Updated user data
            
        Returns:
            Updated user
        """
        try:
            user = await self.get_user_profile(session, user_id)
            
            # Update fields that are provided
            for field, value in user_data.dict(exclude_unset=True).items():
                if hasattr(user, field):
                    setattr(user, field, value)
            
            await session.commit()
            
            logger.info(f"User profile updated: {user_id}")
            return user
            
        except Exception as e:
            await session.rollback()
            if isinstance(e, UserNotFoundException):
                raise
            logger.error(f"User profile update failed: {user_id}, error: {e}")
            raise DatabaseException(f"Profile update failed: {str(e)}")
    
    async def delete_user_account(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        hard_delete: bool = False
    ) -> bool:
        """
        Delete user account (soft delete by default).
        
        Args:
            session: Database session
            user_id: User ID
            hard_delete: Whether to permanently delete
            
        Returns:
            True if successful
        """
        try:
            user = await self.get_user_profile(session, user_id)
            
            if hard_delete:
                # Hard delete - remove all user data
                await session.delete(user)
            else:
                # Soft delete - deactivate account
                user.is_active = False
                user.status = UserStatus.DELETED
                user.deleted_at = datetime.utcnow()
            
            await session.commit()
            
            logger.info(f"User account deleted: {user_id} (hard={hard_delete})")
            return True
            
        except Exception as e:
            await session.rollback()
            if isinstance(e, UserNotFoundException):
                raise
            logger.error(f"User deletion failed: {user_id}, error: {e}")
            return False
    
    async def get_user_statistics(
        self,
        session: AsyncSession,
        user_id: uuid.UUID
    ) -> UserStatsResponse:
        """
        Get user activity statistics.
        
        Args:
            session: Database session
            user_id: User ID
            
        Returns:
            User statistics
        """
        try:
            # Get resume count
            resume_count = await session.execute(
                select(func.count(Resume.id))
                .where(
                    and_(
                        Resume.user_id == user_id,
                        Resume.is_deleted == False
                    )
                )
            )
            resume_count = resume_count.scalar()
            
            # Get job applications count (simplified - would need job applications table)
            job_applications_count = 0
            
            # Get analyses count
            from app.models.resume import ResumeAnalysis
            analyses_count = await session.execute(
                select(func.count(ResumeAnalysis.id))
                .join(Resume, ResumeAnalysis.resume_id == Resume.id)
                .where(Resume.user_id == user_id)
            )
            analyses_count = analyses_count.scalar()
            
            # Get user for subscription info
            user = await self.get_user_profile(session, user_id)
            
            # Calculate subscription days remaining
            subscription_days_remaining = None
            if user.subscription_expires_at:
                remaining = user.subscription_expires_at - datetime.utcnow()
                subscription_days_remaining = max(0, remaining.days)
            
            return UserStatsResponse(
                resume_count=resume_count,
                job_applications_count=job_applications_count,
                analyses_count=analyses_count,
                last_activity=user.last_activity_at,
                subscription_days_remaining=subscription_days_remaining
            )
            
        except Exception as e:
            if isinstance(e, UserNotFoundException):
                raise
            logger.error(f"Failed to get user stats for {user_id}: {e}")
            raise DatabaseException(f"Failed to retrieve statistics: {str(e)}")
    
    async def update_user_preferences(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        preferences_data: UserPreferencesUpdate
    ) -> UserPreferencesResponse:
        """
        Update user preferences.
        
        Args:
            session: Database session
            user_id: User ID
            preferences_data: Updated preferences
            
        Returns:
            Updated preferences
        """
        try:
            user = await self.get_user_profile(session, user_id)
            
            # Get current preferences or create new
            current_preferences = user.preferences or {}
            
            # Update preferences
            for field, value in preferences_data.dict(exclude_unset=True).items():
                current_preferences[field] = value
            
            user.preferences = current_preferences
            await session.commit()
            
            # Return structured preferences
            preferences = UserPreferencesResponse(
                theme=current_preferences.get("theme", "light"),
                default_template_id=current_preferences.get("default_template_id"),
                auto_save=current_preferences.get("auto_save", True),
                ai_suggestions=current_preferences.get("ai_suggestions", True),
                email_frequency=current_preferences.get("email_frequency", "weekly"),
                export_format=current_preferences.get("export_format", "pdf"),
                privacy_level=current_preferences.get("privacy_level", "standard")
            )
            
            logger.info(f"User preferences updated: {user_id}")
            return preferences
            
        except Exception as e:
            await session.rollback()
            if isinstance(e, UserNotFoundException):
                raise
            logger.error(f"Preferences update failed: {user_id}, error: {e}")
            raise DatabaseException(f"Preferences update failed: {str(e)}")
    
    async def get_user_preferences(
        self,
        session: AsyncSession,
        user_id: uuid.UUID
    ) -> UserPreferencesResponse:
        """
        Get user preferences.
        
        Args:
            session: Database session
            user_id: User ID
            
        Returns:
            User preferences
        """
        try:
            user = await self.get_user_profile(session, user_id)
            preferences = user.preferences or {}
            
            return UserPreferencesResponse(
                theme=preferences.get("theme", "light"),
                default_template_id=preferences.get("default_template_id"),
                auto_save=preferences.get("auto_save", True),
                ai_suggestions=preferences.get("ai_suggestions", True),
                email_frequency=preferences.get("email_frequency", "weekly"),
                export_format=preferences.get("export_format", "pdf"),
                privacy_level=preferences.get("privacy_level", "standard")
            )
            
        except Exception as e:
            if isinstance(e, UserNotFoundException):
                raise
            logger.error(f"Failed to get preferences for {user_id}: {e}")
            raise DatabaseException(f"Failed to retrieve preferences: {str(e)}")
    
    async def upgrade_subscription(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        subscription_type: SubscriptionType,
        duration_months: int = 1
    ) -> User:
        """
        Upgrade user subscription.
        
        Args:
            session: Database session
            user_id: User ID
            subscription_type: New subscription type
            duration_months: Subscription duration in months
            
        Returns:
            Updated user
        """
        try:
            user = await self.get_user_profile(session, user_id)
            
            # Update subscription
            user.subscription_type = subscription_type
            
            # Calculate expiration date
            if user.subscription_expires_at and user.subscription_expires_at > datetime.utcnow():
                # Extend existing subscription
                expires_at = user.subscription_expires_at + timedelta(days=30 * duration_months)
            else:
                # New subscription
                expires_at = datetime.utcnow() + timedelta(days=30 * duration_months)
            
            user.subscription_expires_at = expires_at
            
            await session.commit()
            
            # Send upgrade confirmation email
            try:
                await self.email_service.send_email(
                    to_email=user.email,
                    subject=f"Subscription Upgraded - {settings.APP_NAME}",
                    html_content=f"""
                    <h2>Subscription Upgraded!</h2>
                    <p>Hello {user.first_name or 'there'},</p>
                    <p>Your subscription has been successfully upgraded to {subscription_type}.</p>
                    <p>Your subscription will expire on {expires_at.strftime('%B %d, %Y')}.</p>
                    <p>Enjoy your premium features!</p>
                    """,
                    text_content=f"Your subscription has been upgraded to {subscription_type}. Expires: {expires_at.strftime('%B %d, %Y')}"
                )
            except Exception as e:
                logger.warning(f"Failed to send upgrade email to {user.email}: {e}")
            
            logger.info(f"User subscription upgraded: {user_id} to {subscription_type}")
            return user
            
        except Exception as e:
            await session.rollback()
            if isinstance(e, UserNotFoundException):
                raise
            logger.error(f"Subscription upgrade failed: {user_id}, error: {e}")
            raise DatabaseException(f"Subscription upgrade failed: {str(e)}")
    
    async def get_user_sessions(
        self,
        session: AsyncSession,
        user_id: uuid.UUID
    ) -> UserSessionListResponse:
        """
        Get all active sessions for user.
        
        Args:
            session: Database session
            user_id: User ID
            
        Returns:
            List of user sessions
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
                .order_by(desc(UserSession.created_at))
            )
            sessions = result.scalars().all()
            
            session_responses = [
                UserSessionResponse(
                    id=s.id,
                    is_active=s.is_active,
                    expires_at=s.expires_at,
                    ip_address=s.ip_address,
                    user_agent=s.user_agent,
                    device_info=s.device_info or {},
                    created_at=s.created_at
                )
                for s in sessions
            ]
            
            return UserSessionListResponse(
                sessions=session_responses,
                total_count=len(session_responses)
            )
            
        except Exception as e:
            logger.error(f"Failed to get user sessions for {user_id}: {e}")
            raise DatabaseException(f"Failed to retrieve sessions: {str(e)}")
    
    async def revoke_user_session(
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
            
            logger.info(f"User session revoked: {session_id}")
            return True
            
        except Exception as e:
            await session.rollback()
            logger.error(f"Session revocation failed: {session_id}, error: {e}")
            return False
    
    # Admin Methods
    async def search_users(
        self,
        session: AsyncSession,
        search_request: UserSearchRequest,
        admin_user_id: uuid.UUID
    ) -> Tuple[List[User], int]:
        """
        Search users (admin only).
        
        Args:
            session: Database session
            search_request: Search parameters
            admin_user_id: Admin user ID
            
        Returns:
            Tuple of (users, total_count)
        """
        try:
            # Verify admin permissions
            admin_user = await self.get_user_profile(session, admin_user_id)
            if admin_user.role != UserRole.ADMIN:
                raise PermissionDeniedException("Admin access required")
            
            # Build query
            query = select(User)
            
            # Apply text search
            if search_request.query:
                search_terms = f"%{search_request.query}%"
                query = query.where(
                    or_(
                        User.email.ilike(search_terms),
                        User.first_name.ilike(search_terms),
                        User.last_name.ilike(search_terms),
                        User.company.ilike(search_terms)
                    )
                )
            
            # Apply filters
            if search_request.role:
                query = query.where(User.role == search_request.role)
            
            if search_request.status:
                query = query.where(User.status == search_request.status)
            
            if search_request.subscription_type:
                query = query.where(User.subscription_type == search_request.subscription_type)
            
            if search_request.is_verified is not None:
                query = query.where(User.is_verified == search_request.is_verified)
            
            # Date filters
            if search_request.created_after:
                query = query.where(User.created_at >= search_request.created_after)
            
            if search_request.created_before:
                query = query.where(User.created_at <= search_request.created_before)
            
            # Get total count
            count_query = select(func.count()).select_from(query.subquery())
            total_result = await session.execute(count_query)
            total_count = total_result.scalar()
            
            # Apply sorting
            if search_request.sort_by == "email":
                sort_field = User.email
            elif search_request.sort_by == "created_at":
                sort_field = User.created_at
            elif search_request.sort_by == "last_login_at":
                sort_field = User.last_login_at
            else:
                sort_field = User.created_at
            
            if search_request.sort_order == "asc":
                query = query.order_by(sort_field.asc())
            else:
                query = query.order_by(sort_field.desc())
            
            # Apply pagination
            paginated_query = query.limit(search_request.page_size).offset(
                (search_request.page - 1) * search_request.page_size
            )
            
            result = await session.execute(paginated_query)
            users = result.scalars().all()
            
            return list(users), total_count
            
        except Exception as e:
            if isinstance(e, (UserNotFoundException, PermissionDeniedException)):
                raise
            logger.error(f"User search failed: {e}")
            raise DatabaseException(f"User search failed: {str(e)}")
    
    async def update_user_admin(
        self,
        session: AsyncSession,
        target_user_id: uuid.UUID,
        admin_user_id: uuid.UUID,
        admin_data: UserAdminUpdate
    ) -> User:
        """
        Update user as admin.
        
        Args:
            session: Database session
            target_user_id: Target user ID
            admin_user_id: Admin user ID
            admin_data: Admin update data
            
        Returns:
            Updated user
        """
        try:
            # Verify admin permissions
            admin_user = await self.get_user_profile(session, admin_user_id)
            if admin_user.role != UserRole.ADMIN:
                raise PermissionDeniedException("Admin access required")
            
            # Get target user
            target_user = await self.get_user_profile(session, target_user_id)
            
            # Update fields that are provided
            for field, value in admin_data.dict(exclude_unset=True).items():
                if hasattr(target_user, field):
                    setattr(target_user, field, value)
            
            # If suspending user, deactivate all sessions
            if admin_data.status == UserStatus.SUSPENDED:
                await session.execute(
                    update(UserSession)
                    .where(UserSession.user_id == target_user_id)
                    .values(is_active=False)
                )
            
            await session.commit()
            
            logger.info(f"User updated by admin: {target_user_id} by {admin_user_id}")
            return target_user
            
        except Exception as e:
            await session.rollback()
            if isinstance(e, (UserNotFoundException, PermissionDeniedException)):
                raise
            logger.error(f"Admin user update failed: {target_user_id}, error: {e}")
            raise DatabaseException(f"Admin update failed: {str(e)}")
    
    async def get_user_activity_log(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Get user activity log (simplified implementation).
        
        Args:
            session: Database session
            user_id: User ID
            limit: Number of activities to return
            
        Returns:
            List of activity records
        """
        try:
            # This is a simplified implementation
            # In a real application, you would have an activity log table
            
            activities = []
            
            # Get recent resumes
            recent_resumes = await session.execute(
                select(Resume.title, Resume.created_at, Resume.updated_at)
                .where(
                    and_(
                        Resume.user_id == user_id,
                        Resume.is_deleted == False
                    )
                )
                .order_by(desc(Resume.updated_at))
                .limit(limit // 2)
            )
            
            for title, created_at, updated_at in recent_resumes.fetchall():
                activities.append({
                    "type": "resume_created" if created_at == updated_at else "resume_updated",
                    "description": f"{'Created' if created_at == updated_at else 'Updated'} resume: {title}",
                    "timestamp": updated_at,
                    "metadata": {"resume_title": title}
                })
            
            # Get recent job descriptions
            recent_jobs = await session.execute(
                select(JobDescription.title, JobDescription.company, JobDescription.created_at)
                .where(JobDescription.user_id == user_id)
                .order_by(desc(JobDescription.created_at))
                .limit(limit // 2)
            )
            
            for title, company, created_at in recent_jobs.fetchall():
                activities.append({
                    "type": "job_added",
                    "description": f"Added job: {title} at {company}",
                    "timestamp": created_at,
                    "metadata": {"job_title": title, "company": company}
                })
            
            # Sort by timestamp
            activities.sort(key=lambda x: x["timestamp"], reverse=True)
            
            return activities[:limit]
            
        except Exception as e:
            logger.error(f"Failed to get activity log for {user_id}: {e}")
            raise DatabaseException(f"Failed to retrieve activity log: {str(e)}")
    
    async def export_user_data(
        self,
        session: AsyncSession,
        user_id: uuid.UUID
    ) -> Dict[str, Any]:
        """
        Export all user data (GDPR compliance).
        
        Args:
            session: Database session
            user_id: User ID
            
        Returns:
            Complete user data export
        """
        try:
            # Get user profile
            user = await self.get_user_profile(session, user_id)
            
            # Get user's resumes
            resumes_result = await session.execute(
                select(Resume)
                .where(
                    and_(
                        Resume.user_id == user_id,
                        Resume.is_deleted == False
                    )
                )
            )
            resumes = resumes_result.scalars().all()
            
            # Get user's job descriptions
            jobs_result = await session.execute(
                select(JobDescription)
                .where(JobDescription.user_id == user_id)
            )
            jobs = jobs_result.scalars().all()
            
            # Get user sessions
            sessions_result = await session.execute(
                select(UserSession)
                .where(UserSession.user_id == user_id)
            )
            sessions = sessions_result.scalars().all()
            
            # Compile export data
            export_data = {
                "export_date": datetime.utcnow().isoformat(),
                "user_profile": {
                    "id": str(user.id),
                    "email": user.email,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "phone_number": user.phone_number,
                    "job_title": user.job_title,
                    "company": user.company,
                    "industry": user.industry,
                    "experience_years": user.experience_years,
                    "timezone": user.timezone,
                    "language": user.language,
                    "preferences": user.preferences,
                    "subscription_type": user.subscription_type,
                    "created_at": user.created_at.isoformat(),
                    "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None
                },
                "resumes": [
                    {
                        "id": str(resume.id),
                        "title": resume.title,
                        "description": resume.description,
                        "created_at": resume.created_at.isoformat(),
                        "updated_at": resume.updated_at.isoformat()
                    }
                    for resume in resumes
                ],
                "job_descriptions": [
                    {
                        "id": str(job.id),
                        "title": job.title,
                        "company": job.company,
                        "location": job.location,
                        "created_at": job.created_at.isoformat()
                    }
                    for job in jobs
                ],
                "sessions": [
                    {
                        "id": str(session.id),
                        "ip_address": session.ip_address,
                        "created_at": session.created_at.isoformat(),
                        "is_active": session.is_active
                    }
                    for session in sessions
                ]
            }
            
            logger.info(f"User data exported: {user_id}")
            return export_data
            
        except Exception as e:
            if isinstance(e, UserNotFoundException):
                raise
            logger.error(f"User data export failed: {user_id}, error: {e}")
            raise DatabaseException(f"Data export failed: {str(e)}")


# Export service
__all__ = ["UserService"]