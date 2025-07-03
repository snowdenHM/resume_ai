"""
User-related database models.
"""

from datetime import datetime
from enum import Enum
from typing import Optional, List

from sqlalchemy import (
    Column, String, Boolean, DateTime, Integer, 
    ForeignKey, Index, CheckConstraint, Text
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship, validates
from sqlalchemy.sql import func

from app.models.base import BaseModel, SoftDeleteModel, create_enum_field


class UserRole(str, Enum):
    """User roles enumeration."""
    USER = "user"
    PREMIUM = "premium"
    ADMIN = "admin"


class UserStatus(str, Enum):
    """User status enumeration."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    PENDING_VERIFICATION = "pending_verification"


class SubscriptionType(str, Enum):
    """Subscription types."""
    FREE = "free"
    BASIC = "basic"
    PREMIUM = "premium"
    ENTERPRISE = "enterprise"


class User(BaseModel):
    """User model for authentication and profile management."""
    
    __tablename__ = "users"
    
    # Basic Information
    email = Column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
        comment="User email address"
    )
    
    username = Column(
        String(50),
        unique=True,
        nullable=True,
        index=True,
        comment="Unique username (optional)"
    )
    
    hashed_password = Column(
        String(255),
        nullable=False,
        comment="Hashed password"
    )
    
    # Profile Information
    first_name = Column(
        String(100),
        nullable=True,
        comment="User first name"
    )
    
    last_name = Column(
        String(100),
        nullable=True,
        comment="User last name"
    )
    
    phone_number = Column(
        String(20),
        nullable=True,
        comment="Phone number"
    )
    
    profile_picture_url = Column(
        String(500),
        nullable=True,
        comment="Profile picture URL"
    )
    
    # Account Status
    role = create_enum_field(
        UserRole,
        "role",
        default=UserRole.USER,
        comment="User role"
    )
    
    status = create_enum_field(
        UserStatus,
        "status",
        default=UserStatus.PENDING_VERIFICATION,
        comment="Account status"
    )
    
    is_active = Column(
        Boolean,
        default=True,
        nullable=False,
        index=True,
        comment="Account active flag"
    )
    
    is_verified = Column(
        Boolean,
        default=False,
        nullable=False,
        index=True,
        comment="Email verification status"
    )
    
    # Subscription Information
    subscription_type = create_enum_field(
        SubscriptionType,
        "subscription_type",
        default=SubscriptionType.FREE,
        comment="Subscription plan"
    )
    
    subscription_expires_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Subscription expiration date"
    )
    
    # Activity Tracking
    last_login_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Last login timestamp"
    )
    
    last_activity_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Last activity timestamp"
    )
    
    login_count = Column(
        Integer,
        default=0,
        nullable=False,
        comment="Total login count"
    )
    
    # Professional Information
    job_title = Column(
        String(200),
        nullable=True,
        comment="Current job title"
    )
    
    company = Column(
        String(200),
        nullable=True,
        comment="Current company"
    )
    
    industry = Column(
        String(100),
        nullable=True,
        comment="Industry"
    )
    
    experience_years = Column(
        Integer,
        nullable=True,
        comment="Years of experience"
    )
    
    # Preferences
    preferences = Column(
        JSONB,
        nullable=True,
        default=dict,
        comment="User preferences as JSON"
    )
    
    # Settings
    email_notifications = Column(
        Boolean,
        default=True,
        nullable=False,
        comment="Email notifications enabled"
    )
    
    marketing_emails = Column(
        Boolean,
        default=False,
        nullable=False,
        comment="Marketing emails enabled"
    )
    
    timezone = Column(
        String(50),
        default="UTC",
        nullable=False,
        comment="User timezone"
    )
    
    language = Column(
        String(10),
        default="en",
        nullable=False,
        comment="Preferred language"
    )
    
    # Relationships
    resumes = relationship(
        "Resume",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="dynamic"
    )
    
    job_descriptions = relationship(
        "JobDescription",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="dynamic"
    )
    
    user_sessions = relationship(
        "UserSession",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="dynamic"
    )
    
    # Constraints
    __table_args__ = (
        CheckConstraint(
            "experience_years >= 0 AND experience_years <= 50",
            name="check_experience_years"
        ),
        Index("idx_user_email_status", "email", "status"),
        Index("idx_user_role_active", "role", "is_active"),
        Index("idx_user_subscription", "subscription_type", "subscription_expires_at"),
    )
    
    @validates("email")
    def validate_email(self, key, email):
        """Validate email format."""
        import re
        
        if not email:
            raise ValueError("Email is required")
        
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(pattern, email):
            raise ValueError("Invalid email format")
        
        return email.lower()
    
    @validates("phone_number")
    def validate_phone(self, key, phone):
        """Validate phone number format."""
        if phone:
            # Remove all non-digit characters
            digits_only = ''.join(filter(str.isdigit, phone))
            if len(digits_only) < 10:
                raise ValueError("Phone number must have at least 10 digits")
        return phone
    
    @property
    def full_name(self) -> str:
        """Get user's full name."""
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        elif self.first_name:
            return self.first_name
        elif self.last_name:
            return self.last_name
        else:
            return self.email.split("@")[0]
    
    @property
    def is_premium(self) -> bool:
        """Check if user has premium subscription."""
        if self.subscription_type in [SubscriptionType.PREMIUM, SubscriptionType.ENTERPRISE]:
            if self.subscription_expires_at:
                return self.subscription_expires_at > datetime.utcnow()
            return True
        return False
    
    @property
    def resume_count(self) -> int:
        """Get user's resume count."""
        return self.resumes.filter_by(is_deleted=False).count()
    
    def update_last_activity(self) -> None:
        """Update last activity timestamp."""
        self.last_activity_at = datetime.utcnow()
    
    def update_login_info(self) -> None:
        """Update login information."""
        self.last_login_at = datetime.utcnow()
        self.login_count += 1
        self.update_last_activity()
    
    def can_create_resume(self) -> bool:
        """Check if user can create new resume based on subscription."""
        if self.is_premium:
            return True
        
        # Free users limited to 3 resumes
        return self.resume_count < 3
    
    def __repr__(self) -> str:
        return f"<User(id={self.id}, email='{self.email}', role='{self.role}')>"


class UserSession(BaseModel):
    """User session model for tracking active sessions."""
    
    __tablename__ = "user_sessions"
    
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="User ID"
    )
    
    token_hash = Column(
        String(255),
        nullable=False,
        unique=True,
        index=True,
        comment="Hashed session token"
    )
    
    refresh_token_hash = Column(
        String(255),
        nullable=True,
        unique=True,
        index=True,
        comment="Hashed refresh token"
    )
    
    expires_at = Column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        comment="Session expiration time"
    )
    
    is_active = Column(
        Boolean,
        default=True,
        nullable=False,
        index=True,
        comment="Session active status"
    )
    
    ip_address = Column(
        String(45),  # IPv6 max length
        nullable=True,
        comment="Client IP address"
    )
    
    user_agent = Column(
        Text,
        nullable=True,
        comment="Client user agent"
    )
    
    device_info = Column(
        JSONB,
        nullable=True,
        default=dict,
        comment="Device information"
    )
    
    # Relationships
    user = relationship("User", back_populates="user_sessions")
    
    # Constraints
    __table_args__ = (
        Index("idx_session_user_active", "user_id", "is_active"),
        Index("idx_session_expires", "expires_at"),
    )
    
    @property
    def is_expired(self) -> bool:
        """Check if session is expired."""
        return datetime.utcnow() > self.expires_at
    
    def deactivate(self) -> None:
        """Deactivate session."""
        self.is_active = False
    
    def __repr__(self) -> str:
        return f"<UserSession(id={self.id}, user_id={self.user_id}, active={self.is_active})>"


class UserVerification(BaseModel):
    """User email verification model."""
    
    __tablename__ = "user_verifications"
    
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="User ID"
    )
    
    verification_token = Column(
        String(255),
        nullable=False,
        unique=True,
        index=True,
        comment="Verification token"
    )
    
    verification_type = Column(
        String(50),
        nullable=False,
        comment="Type of verification (email, phone, etc.)"
    )
    
    expires_at = Column(
        DateTime(timezone=True),
        nullable=False,
        comment="Token expiration time"
    )
    
    is_used = Column(
        Boolean,
        default=False,
        nullable=False,
        comment="Token usage status"
    )
    
    used_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Token usage timestamp"
    )
    
    attempts = Column(
        Integer,
        default=0,
        nullable=False,
        comment="Number of verification attempts"
    )
    
    # Relationships
    user = relationship("User")
    
    # Constraints
    __table_args__ = (
        Index("idx_verification_token_type", "verification_token", "verification_type"),
        Index("idx_verification_user_type", "user_id", "verification_type"),
    )
    
    @property
    def is_expired(self) -> bool:
        """Check if verification token is expired."""
        return datetime.utcnow() > self.expires_at
    
    @property
    def is_valid(self) -> bool:
        """Check if verification token is valid."""
        return not self.is_used and not self.is_expired and self.attempts < 5
    
    def mark_as_used(self) -> None:
        """Mark verification token as used."""
        self.is_used = True
        self.used_at = datetime.utcnow()
    
    def increment_attempts(self) -> None:
        """Increment verification attempts."""
        self.attempts += 1
    
    def __repr__(self) -> str:
        return f"<UserVerification(id={self.id}, user_id={self.user_id}, type='{self.verification_type}')>"


# Export models
__all__ = [
    "User",
    "UserSession", 
    "UserVerification",
    "UserRole",
    "UserStatus",
    "SubscriptionType"
]