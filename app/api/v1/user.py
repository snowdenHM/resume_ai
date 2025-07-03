"""
User management API endpoints for profile, preferences, and admin operations.
"""

import logging
from typing import List, Optional
import uuid

from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, desc

from app.api.deps import (
    get_db_session, get_current_user, get_current_verified_user, 
    get_current_admin_user, get_pagination_params, PaginationParams,
    check_rate_limit, get_request_id
)
from app.exceptions import (
    UserNotFoundException, ValidationException, AuthorizationException
)
from app.models.user import User, UserRole, UserStatus, SubscriptionType
from app.schemas.user import (
    UserResponse, UserUpdate, UserPreferencesUpdate, UserPreferencesResponse,
    UserAdminUpdate, UserListResponse, UserSearchRequest, UserStatsResponse
)
from app.services.user_service import UserService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/users", tags=["User Management"])

# Initialize service
user_service = UserService()


@router.get(
    "/profile",
    response_model=UserResponse,
    summary="Get user profile",
    description="Get current user's profile information"
)
async def get_user_profile(
    current_user: User = Depends(get_current_user)
) -> UserResponse:
    """
    Get current user's profile information.
    
    Returns complete user profile data.
    """
    return UserResponse.from_orm(current_user)


@router.put(
    "/profile",
    response_model=UserResponse,
    summary="Update user profile",
    description="Update current user's profile information"
)
async def update_user_profile(
    profile_data: UserUpdate,
    current_user: User = Depends(get_current_verified_user),
    session: AsyncSession = Depends(get_db_session),
    request_id: str = Depends(get_request_id)
) -> UserResponse:
    """
    Update current user's profile information.
    
    - **first_name**: First name
    - **last_name**: Last name
    - **phone_number**: Phone number
    - **job_title**: Current job title
    - **company**: Current company
    - **industry**: Industry sector
    - **experience_years**: Years of experience
    - **timezone**: User timezone
    - **language**: Preferred language
    - **email_notifications**: Email notification preference
    - **marketing_emails**: Marketing email preference
    
    Returns updated user profile.
    """
    try:
        updated_user = await user_service.update_user_profile(
            session, current_user.id, profile_data
        )
        
        logger.info(f"User profile updated: {current_user.id} - Request: {request_id}")
        return UserResponse.from_orm(updated_user)
        
    except ValidationException as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Profile update failed for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Profile update failed"
        )


@router.post(
    "/profile/avatar",
    response_model=UserResponse,
    summary="Upload profile picture",
    description="Upload user profile picture"
)
async def upload_profile_picture(
    file: UploadFile = File(..., description="Profile picture file"),
    current_user: User = Depends(get_current_verified_user),
    session: AsyncSession = Depends(get_db_session),
    request_id: str = Depends(get_request_id),
    _: None = Depends(check_rate_limit)
) -> UserResponse:
    """
    Upload profile picture.
    
    - **file**: Image file (JPG, PNG, max 5MB)
    
    Returns updated user profile with new avatar URL.
    """
    try:
        updated_user = await user_service.upload_profile_picture(
            session, current_user.id, file
        )
        
        logger.info(f"Profile picture uploaded: {current_user.id} - Request: {request_id}")
        return UserResponse.from_orm(updated_user)
        
    except ValidationException as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Profile picture upload failed for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Profile picture upload failed"
        )


@router.get(
    "/preferences",
    response_model=UserPreferencesResponse,
    summary="Get user preferences",
    description="Get current user's application preferences"
)
async def get_user_preferences(
    current_user: User = Depends(get_current_verified_user),
    session: AsyncSession = Depends(get_db_session)
) -> UserPreferencesResponse:
    """
    Get user's application preferences.
    
    Returns user preferences and settings.
    """
    try:
        preferences = await user_service.get_user_preferences(session, current_user.id)
        return preferences
        
    except Exception as e:
        logger.error(f"Failed to get preferences for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve preferences"
        )


@router.put(
    "/preferences",
    response_model=UserPreferencesResponse,
    summary="Update user preferences",
    description="Update current user's application preferences"
)
async def update_user_preferences(
    preferences_data: UserPreferencesUpdate,
    current_user: User = Depends(get_current_verified_user),
    session: AsyncSession = Depends(get_db_session),
    request_id: str = Depends(get_request_id)
) -> UserPreferencesResponse:
    """
    Update user's application preferences.
    
    - **theme**: UI theme preference (light/dark)
    - **default_template_id**: Default resume template
    - **auto_save**: Auto-save enabled
    - **ai_suggestions**: AI suggestions enabled
    - **email_frequency**: Email notification frequency
    - **export_format**: Default export format
    - **privacy_level**: Privacy level setting
    
    Returns updated preferences.
    """
    try:
        preferences = await user_service.update_user_preferences(
            session, current_user.id, preferences_data
        )
        
        logger.info(f"User preferences updated: {current_user.id} - Request: {request_id}")
        return preferences
        
    except ValidationException as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Preferences update failed for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Preferences update failed"
        )


@router.get(
    "/stats",
    response_model=UserStatsResponse,
    summary="Get user statistics",
    description="Get current user's activity statistics"
)
async def get_user_stats(
    current_user: User = Depends(get_current_verified_user),
    session: AsyncSession = Depends(get_db_session)
) -> UserStatsResponse:
    """
    Get user's activity statistics.
    
    Returns comprehensive user activity data and insights.
    """
    try:
        stats = await user_service.get_user_stats(session, current_user.id)
        return stats
        
    except Exception as e:
        logger.error(f"Failed to get stats for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve statistics"
        )


@router.delete(
    "/account",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete user account",
    description="Delete current user's account and all associated data"
)
async def delete_user_account(
    confirm_email: str = Query(..., description="User's email for confirmation"),
    current_user: User = Depends(get_current_verified_user),
    session: AsyncSession = Depends(get_db_session),
    request_id: str = Depends(get_request_id)
):
    """
    Delete user account and all associated data.
    
    - **confirm_email**: User's email address for confirmation
    
    This action is irreversible and will delete all user data.
    """
    try:
        if confirm_email.lower() != current_user.email.lower():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email confirmation does not match"
            )
        
        success = await user_service.delete_user_account(session, current_user.id)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Account deletion failed"
            )
        
        logger.info(f"User account deleted: {current_user.id} - Request: {request_id}")
        
    except Exception as e:
        if isinstance(e, HTTPException):
            raise
        logger.error(f"Account deletion failed for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Account deletion failed"
        )


# Admin endpoints
@router.get(
    "/admin/users",
    response_model=UserListResponse,
    summary="List all users (Admin)",
    description="Get paginated list of all users with filtering (Admin only)"
)
async def admin_list_users(
    search_params: UserSearchRequest = Depends(),
    pagination: PaginationParams = Depends(get_pagination_params),
    current_user: User = Depends(get_current_admin_user),
    session: AsyncSession = Depends(get_db_session)
) -> UserListResponse:
    """
    Get paginated list of all users with filtering (Admin only).
    
    - **query**: Search query for name/email
    - **role**: Filter by user role
    - **status**: Filter by account status
    - **subscription_type**: Filter by subscription
    - **is_verified**: Filter by verification status
    - **created_after**: Filter by creation date
    - **created_before**: Filter by creation date
    - **page**: Page number
    - **page_size**: Items per page
    - **sort_by**: Sort field
    - **sort_order**: Sort order
    
    Returns paginated list of users.
    """
    try:
        users, total_count = await user_service.admin_search_users(
            session, search_params, pagination
        )
        
        total_pages = (total_count + pagination.page_size - 1) // pagination.page_size
        
        return UserListResponse(
            users=[UserResponse.from_orm(user) for user in users],
            total_count=total_count,
            page=pagination.page,
            page_size=pagination.page_size,
            total_pages=total_pages
        )
        
    except Exception as e:
        logger.error(f"Admin user list failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve users"
        )


@router.get(
    "/admin/users/{user_id}",
    response_model=UserResponse,
    summary="Get user details (Admin)",
    description="Get detailed user information (Admin only)"
)
async def admin_get_user(
    user_id: uuid.UUID,
    current_user: User = Depends(get_current_admin_user),
    session: AsyncSession = Depends(get_db_session)
) -> UserResponse:
    """
    Get detailed user information (Admin only).
    
    - **user_id**: User ID to retrieve
    
    Returns complete user profile and activity data.
    """
    try:
        user = await user_service.admin_get_user(session, user_id)
        return UserResponse.from_orm(user)
        
    except UserNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    except Exception as e:
        logger.error(f"Admin get user failed: {user_id}, error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve user"
        )


@router.put(
    "/admin/users/{user_id}",
    response_model=UserResponse,
    summary="Update user (Admin)",
    description="Update user information and status (Admin only)"
)
async def admin_update_user(
    user_id: uuid.UUID,
    update_data: UserAdminUpdate,
    current_user: User = Depends(get_current_admin_user),
    session: AsyncSession = Depends(get_db_session),
    request_id: str = Depends(get_request_id)
) -> UserResponse:
    """
    Update user information and status (Admin only).
    
    - **user_id**: User ID to update
    - **role**: User role (user/premium/admin)
    - **status**: Account status (active/inactive/suspended)
    - **subscription_type**: Subscription type
    - **subscription_expires_at**: Subscription expiry date
    - **is_active**: Account active status
    - **is_verified**: Email verification status
    
    Returns updated user information.
    """
    try:
        updated_user = await user_service.admin_update_user(
            session, user_id, update_data
        )
        
        logger.info(f"Admin updated user: {user_id} by {current_user.id} - Request: {request_id}")
        return UserResponse.from_orm(updated_user)
        
    except UserNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    except ValidationException as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Admin user update failed: {user_id}, error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="User update failed"
        )


@router.delete(
    "/admin/users/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete user (Admin)",
    description="Delete user account and all data (Admin only)"
)
async def admin_delete_user(
    user_id: uuid.UUID,
    hard_delete: bool = Query(False, description="Permanently delete user"),
    current_user: User = Depends(get_current_admin_user),
    session: AsyncSession = Depends(get_db_session),
    request_id: str = Depends(get_request_id)
):
    """
    Delete user account (Admin only).
    
    - **user_id**: User ID to delete
    - **hard_delete**: If true, permanently delete; otherwise deactivate
    
    This action affects all user data and associated records.
    """
    try:
        # Prevent admin from deleting themselves
        if user_id == current_user.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete your own account"
            )
        
        success = await user_service.admin_delete_user(session, user_id, hard_delete)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="User deletion failed"
            )
        
        logger.info(f"Admin deleted user: {user_id} by {current_user.id} (hard={hard_delete}) - Request: {request_id}")
        
    except UserNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    except Exception as e:
        if isinstance(e, HTTPException):
            raise
        logger.error(f"Admin user deletion failed: {user_id}, error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="User deletion failed"
        )


@router.get(
    "/admin/stats",
    response_model=dict,
    summary="Get platform statistics (Admin)",
    description="Get comprehensive platform statistics (Admin only)"
)
async def admin_get_platform_stats(
    current_user: User = Depends(get_current_admin_user),
    session: AsyncSession = Depends(get_db_session)
) -> dict:
    """
    Get platform-wide statistics (Admin only).
    
    Returns comprehensive statistics about users, activity, and system health.
    """
    try:
        stats = await user_service.admin_get_platform_stats(session)
        return stats
        
    except Exception as e:
        logger.error(f"Admin platform stats failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve platform statistics"
        )