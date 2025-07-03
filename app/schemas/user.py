"""
User-related Pydantic schemas for request/response validation.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
import uuid

from pydantic import (
    BaseModel,
    EmailStr,
    Field,
    field_validator,
    model_validator
)

from app.models.user import UserRole, UserStatus, SubscriptionType


# Base schemas
class UserBase(BaseModel):
    """Base user schema with common fields."""

    email: EmailStr = Field(..., description="User email address")
    first_name: Optional[str] = Field(None, max_length=100, description="First name")
    last_name: Optional[str] = Field(None, max_length=100, description="Last name")
    phone_number: Optional[str] = Field(None, max_length=20, description="Phone number")
    job_title: Optional[str] = Field(None, max_length=200, description="Job title")
    company: Optional[str] = Field(None, max_length=200, description="Company name")
    industry: Optional[str] = Field(None, max_length=100, description="Industry")
    experience_years: Optional[int] = Field(None, ge=0, le=50, description="Years of experience")
    timezone: str = Field("UTC", max_length=50, description="User timezone")
    language: str = Field("en", max_length=10, description="Preferred language")

    @field_validator("phone_number")
    @classmethod
    def validate_phone_number(cls, v):
        if v:
            digits_only = ''.join(filter(str.isdigit, v))
            if len(digits_only) < 10:
                raise ValueError("Phone number must have at least 10 digits")
        return v

    @field_validator("industry")
    @classmethod
    def validate_industry(cls, v):
        if v:
            valid_industries = [
                "technology", "finance", "healthcare", "education", "manufacturing",
                "retail", "consulting", "marketing", "sales", "human_resources",
                "operations", "legal", "design", "other"
            ]
            if v.lower() not in valid_industries:
                v = "other"
        return v


# Request schemas
class UserCreate(UserBase):
    password: str = Field(..., min_length=8, max_length=128, description="User password (min 8 characters)")
    username: Optional[str] = Field(
        None,
        min_length=3,
        max_length=50,
        pattern=r"^[a-zA-Z0-9_]+$",
        description="Username (alphanumeric and underscore only)"
    )
    email_notifications: bool = Field(True, description="Enable email notifications")
    marketing_emails: bool = Field(False, description="Enable marketing emails")

    @field_validator("password")
    @classmethod
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long")

        has_upper = any(c.isupper() for c in v)
        has_lower = any(c.islower() for c in v)
        has_digit = any(c.isdigit() for c in v)
        has_special = any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in v)

        if not (has_upper and has_lower and has_digit):
            raise ValueError("Password must contain uppercase, lowercase, and digit")

        return v


class UserUpdate(BaseModel):
    first_name: Optional[str] = Field(None, max_length=100)
    last_name: Optional[str] = Field(None, max_length=100)
    phone_number: Optional[str] = Field(None, max_length=20)
    job_title: Optional[str] = Field(None, max_length=200)
    company: Optional[str] = Field(None, max_length=200)
    industry: Optional[str] = Field(None, max_length=100)
    experience_years: Optional[int] = Field(None, ge=0, le=50)
    timezone: Optional[str] = Field(None, max_length=50)
    language: Optional[str] = Field(None, max_length=10)
    email_notifications: Optional[bool] = None
    marketing_emails: Optional[bool] = None
    preferences: Optional[Dict[str, Any]] = None


class UserLogin(BaseModel):
    email: EmailStr = Field(..., description="User email")
    password: str = Field(..., min_length=1, description="User password")
    remember_me: bool = Field(False, description="Remember login")


class PasswordChange(BaseModel):
    current_password: str = Field(..., description="Current password")
    new_password: str = Field(..., min_length=8, max_length=128, description="New password")
    confirm_password: str = Field(..., description="Confirm new password")

    @model_validator(mode="after")
    def validate_passwords_match(self) -> "PasswordChange":
        if self.new_password != self.confirm_password:
            raise ValueError("New passwords do not match")
        return self


class PasswordReset(BaseModel):
    email: EmailStr = Field(..., description="User email")


class PasswordResetConfirm(BaseModel):
    token: str = Field(..., description="Reset token")
    new_password: str = Field(..., min_length=8, max_length=128, description="New password")
    confirm_password: str = Field(..., description="Confirm new password")

    @model_validator(mode="after")
    def validate_passwords_match(self) -> "PasswordResetConfirm":
        if self.new_password != self.confirm_password:
            raise ValueError("Passwords do not match")
        return self


class EmailVerification(BaseModel):
    token: str = Field(..., description="Verification token")


class RefreshToken(BaseModel):
    refresh_token: str = Field(..., description="Refresh token")


# Response schemas
class UserResponse(UserBase):
    id: uuid.UUID = Field(..., description="User ID")
    username: Optional[str] = Field(None, description="Username")
    role: UserRole = Field(..., description="User role")
    status: UserStatus = Field(..., description="Account status")
    subscription_type: SubscriptionType = Field(..., description="Subscription type")
    is_active: bool = Field(..., description="Account active status")
    is_verified: bool = Field(..., description="Email verification status")
    subscription_expires_at: Optional[datetime] = Field(None, description="Subscription expiry")
    last_login_at: Optional[datetime] = Field(None, description="Last login timestamp")
    last_activity_at: Optional[datetime] = Field(None, description="Last activity timestamp")
    login_count: int = Field(..., description="Total login count")
    email_notifications: bool = Field(..., description="Email notifications enabled")
    marketing_emails: bool = Field(..., description="Marketing emails enabled")
    profile_picture_url: Optional[str] = Field(None, description="Profile picture URL")
    preferences: Optional[Dict[str, Any]] = Field(None, description="User preferences")
    created_at: datetime = Field(..., description="Account creation time")
    updated_at: datetime = Field(..., description="Last update time")

    class Config:
        from_attributes = True


class UserPublicResponse(BaseModel):
    id: uuid.UUID = Field(..., description="User ID")
    username: Optional[str] = Field(None, description="Username")
    first_name: Optional[str] = Field(None, description="First name")
    last_name: Optional[str] = Field(None, description="Last name")
    profile_picture_url: Optional[str] = Field(None, description="Profile picture URL")

    class Config:
        from_attributes = True


class UserStatsResponse(BaseModel):
    resume_count: int = Field(..., description="Number of resumes")
    job_applications_count: int = Field(..., description="Number of job applications")
    analyses_count: int = Field(..., description="Number of analyses performed")
    last_activity: Optional[datetime] = Field(None, description="Last activity")
    subscription_days_remaining: Optional[int] = Field(None, description="Days until subscription expires")

    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    access_token: str = Field(..., description="JWT access token")
    refresh_token: str = Field(..., description="JWT refresh token")
    token_type: str = Field("bearer", description="Token type")
    expires_in: int = Field(..., description="Token expiration in seconds")
    user: UserResponse = Field(..., description="User information")


class LoginResponse(TokenResponse):
    message: str = Field("Login successful", description="Success message")
    is_first_login: bool = Field(False, description="Is this the first login")


class LogoutResponse(BaseModel):
    message: str = Field("Logout successful", description="Success message")


class UserSessionResponse(BaseModel):
    id: uuid.UUID = Field(..., description="Session ID")
    is_active: bool = Field(..., description="Session active status")
    expires_at: datetime = Field(..., description="Session expiration")
    ip_address: Optional[str] = Field(None, description="Client IP address")
    user_agent: Optional[str] = Field(None, description="Client user agent")
    device_info: Optional[Dict[str, Any]] = Field(None, description="Device information")
    created_at: datetime = Field(..., description="Session creation time")

    class Config:
        from_attributes = True


class UserSessionListResponse(BaseModel):
    sessions: List[UserSessionResponse] = Field(..., description="Active sessions")
    total_count: int = Field(..., description="Total session count")


class UserPreferencesUpdate(BaseModel):
    theme: Optional[str] = Field(None, description="UI theme preference")
    default_template_id: Optional[uuid.UUID] = Field(None, description="Default resume template")
    auto_save: Optional[bool] = Field(None, description="Auto-save enabled")
    ai_suggestions: Optional[bool] = Field(None, description="AI suggestions enabled")
    email_frequency: Optional[str] = Field(None, description="Email notification frequency")
    export_format: Optional[str] = Field(None, description="Default export format")
    privacy_level: Optional[str] = Field(None, description="Privacy level setting")


class UserPreferencesResponse(BaseModel):
    theme: str = Field("light", description="UI theme")
    default_template_id: Optional[uuid.UUID] = Field(None, description="Default template")
    auto_save: bool = Field(True, description="Auto-save enabled")
    ai_suggestions: bool = Field(True, description="AI suggestions enabled")
    email_frequency: str = Field("weekly", description="Email frequency")
    export_format: str = Field("pdf", description="Default export format")
    privacy_level: str = Field("standard", description="Privacy level")

    class Config:
        from_attributes = True


class UserAdminUpdate(BaseModel):
    role: Optional[UserRole] = Field(None, description="User role")
    status: Optional[UserStatus] = Field(None, description="Account status")
    subscription_type: Optional[SubscriptionType] = Field(None, description="Subscription type")
    subscription_expires_at: Optional[datetime] = Field(None, description="Subscription expiry")
    is_active: Optional[bool] = Field(None, description="Account active status")
    is_verified: Optional[bool] = Field(None, description="Email verification status")


class UserListResponse(BaseModel):
    users: List[UserResponse] = Field(..., description="List of users")
    total_count: int = Field(..., description="Total user count")
    page: int = Field(..., description="Current page")
    page_size: int = Field(..., description="Page size")
    total_pages: int = Field(..., description="Total pages")


class UserSearchRequest(BaseModel):
    query: Optional[str] = Field(None, description="Search query")
    role: Optional[UserRole] = Field(None, description="Filter by role")
    status: Optional[UserStatus] = Field(None, description="Filter by status")
    subscription_type: Optional[SubscriptionType] = Field(None, description="Filter by subscription")
    is_verified: Optional[bool] = Field(None, description="Filter by verification status")
    created_after: Optional[datetime] = Field(None, description="Created after date")
    created_before: Optional[datetime] = Field(None, description="Created before date")
    page: int = Field(1, ge=1, description="Page number")
    page_size: int = Field(20, ge=1, le=100, description="Page size")
    sort_by: str = Field("created_at", description="Sort field")
    sort_order: str = Field("desc", pattern="^(asc|desc)$", description="Sort order")



# Export all schemas
__all__ = [
    # Base schemas
    "UserBase",
    
    # Request schemas
    "UserCreate",
    "UserUpdate",
    "UserLogin",
    "PasswordChange",
    "PasswordReset",
    "PasswordResetConfirm",
    "EmailVerification",
    "RefreshToken",
    
    # Response schemas
    "UserResponse",
    "UserPublicResponse",
    "UserStatsResponse",
    "TokenResponse",
    "LoginResponse",
    "LogoutResponse",
    
    # Session schemas
    "UserSessionResponse",
    "UserSessionListResponse",
    
    # Preferences schemas
    "UserPreferencesUpdate",
    "UserPreferencesResponse",
    
    # Admin schemas
    "UserAdminUpdate",
    "UserListResponse",
    
    # Search schemas
    "UserSearchRequest"
]