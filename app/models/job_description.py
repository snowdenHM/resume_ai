"""
Job description related database models.
"""

from datetime import datetime
from enum import Enum
from typing import Optional, List

from sqlalchemy import (
    Column, String, Boolean, DateTime, Integer, Text, Float,
    ForeignKey, Index, CheckConstraint
)
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY, TSVECTOR
from sqlalchemy.orm import relationship, validates
from sqlalchemy.sql import func

from app.models.base import BaseModel, SoftDeleteModel, create_enum_field, create_json_field


class JobStatus(str, Enum):
    """Job posting status."""
    ACTIVE = "active"
    CLOSED = "closed"
    DRAFT = "draft"
    EXPIRED = "expired"


class JobType(str, Enum):
    """Job type enumeration."""
    FULL_TIME = "full_time"
    PART_TIME = "part_time"
    CONTRACT = "contract"
    TEMPORARY = "temporary"
    INTERNSHIP = "internship"
    FREELANCE = "freelance"


class ExperienceLevel(str, Enum):
    """Experience level enumeration."""
    ENTRY_LEVEL = "entry_level"
    MID_LEVEL = "mid_level"
    SENIOR_LEVEL = "senior_level"
    EXECUTIVE = "executive"
    STUDENT = "student"


class RemoteType(str, Enum):
    """Remote work type."""
    ON_SITE = "on_site"
    REMOTE = "remote"
    HYBRID = "hybrid"


class JobDescription(SoftDeleteModel):
    """Job description model."""
    
    __tablename__ = "job_descriptions"
    
    # Basic Information
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="User who added this job"
    )
    
    title = Column(
        String(200),
        nullable=False,
        comment="Job title"
    )
    
    company = Column(
        String(200),
        nullable=False,
        comment="Company name"
    )
    
    location = Column(
        String(200),
        nullable=True,
        comment="Job location"
    )
    
    # Job Details
    job_type = create_enum_field(
        JobType,
        "job_type",
        default=JobType.FULL_TIME,
        comment="Type of employment"
    )
    
    experience_level = create_enum_field(
        ExperienceLevel,
        "experience_level",
        default=ExperienceLevel.MID_LEVEL,
        comment="Required experience level"
    )
    
    remote_type = create_enum_field(
        RemoteType,
        "remote_type",
        default=RemoteType.ON_SITE,
        comment="Remote work type"
    )
    
    industry = Column(
        String(100),
        nullable=True,
        comment="Industry sector"
    )
    
    department = Column(
        String(100),
        nullable=True,
        comment="Department/Team"
    )
    
    # Salary Information
    salary_min = Column(
        Integer,
        nullable=True,
        comment="Minimum salary"
    )
    
    salary_max = Column(
        Integer,
        nullable=True,
        comment="Maximum salary"
    )
    
    salary_currency = Column(
        String(10),
        default="USD",
        nullable=False,
        comment="Salary currency"
    )
    
    salary_period = Column(
        String(20),
        default="yearly",
        nullable=False,
        comment="Salary period (yearly, monthly, hourly)"
    )
    
    # Content
    description = Column(
        Text,
        nullable=False,
        comment="Full job description"
    )
    
    responsibilities = Column(
        ARRAY(String),
        nullable=True,
        comment="Job responsibilities"
    )
    
    requirements = Column(
        ARRAY(String),
        nullable=True,
        comment="Job requirements"
    )
    
    nice_to_have = Column(
        ARRAY(String),
        nullable=True,
        comment="Nice to have qualifications"
    )
    
    benefits = Column(
        ARRAY(String),
        nullable=True,
        comment="Job benefits"
    )
    
    # Skills and Keywords
    required_skills = Column(
        ARRAY(String),
        nullable=True,
        comment="Required skills"
    )
    
    preferred_skills = Column(
        ARRAY(String),
        nullable=True,
        comment="Preferred skills"
    )
    
    keywords = Column(
        ARRAY(String),
        nullable=True,
        comment="Important keywords"
    )
    
    # Education and Experience
    education_requirements = Column(
        ARRAY(String),
        nullable=True,
        comment="Education requirements"
    )
    
    years_experience_min = Column(
        Integer,
        nullable=True,
        comment="Minimum years of experience"
    )
    
    years_experience_max = Column(
        Integer,
        nullable=True,
        comment="Maximum years of experience"
    )
    
    # Application Information
    application_url = Column(
        String(500),
        nullable=True,
        comment="Application URL"
    )
    
    application_email = Column(
        String(255),
        nullable=True,
        comment="Application email"
    )
    
    application_deadline = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Application deadline"
    )
    
    # Status and Metadata
    status = create_enum_field(
        JobStatus,
        "status",
        default=JobStatus.ACTIVE,
        comment="Job posting status"
    )
    
    posted_date = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Job posting date"
    )
    
    source_url = Column(
        String(500),
        nullable=True,
        comment="Original job posting URL"
    )
    
    source_platform = Column(
        String(100),
        nullable=True,
        comment="Job board/platform"
    )
    
    # AI Analysis
    structured_data = create_json_field(
        "structured_data",
        default=dict,
        comment="AI-extracted structured data"
    )
    
    analysis_score = Column(
        Float,
        nullable=True,
        comment="Job description analysis score"
    )
    
    complexity_score = Column(
        Float,
        nullable=True,
        comment="Job complexity score"
    )
    
    last_analyzed_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Last analysis timestamp"
    )
    
    # Search
    search_vector = Column(
        TSVECTOR,
        nullable=True,
        comment="Full-text search vector"
    )
    
    # Tracking
    view_count = Column(
        Integer,
        default=0,
        nullable=False,
        comment="Number of views"
    )
    
    match_count = Column(
        Integer,
        default=0,
        nullable=False,
        comment="Number of resume matches"
    )
    
    # Relationships
    user = relationship("User", back_populates="job_descriptions")
    resume_analyses = relationship("ResumeAnalysis", back_populates="job_description", cascade="all, delete-orphan")
    job_matches = relationship("JobMatch", back_populates="job_description", cascade="all, delete-orphan")
    
    # Constraints
    __table_args__ = (
        CheckConstraint("salary_min >= 0", name="check_salary_min"),
        CheckConstraint("salary_max >= 0", name="check_salary_max"),
        CheckConstraint("salary_max >= salary_min", name="check_salary_range"),
        CheckConstraint("years_experience_min >= 0", name="check_experience_min"),
        CheckConstraint("years_experience_max >= 0", name="check_experience_max"),
        CheckConstraint("years_experience_max >= years_experience_min", name="check_experience_range"),
        CheckConstraint("analysis_score >= 0 AND analysis_score <= 100", name="check_analysis_score_job"),
        CheckConstraint("complexity_score >= 0 AND complexity_score <= 100", name="check_complexity_score"),
        CheckConstraint("view_count >= 0", name="check_view_count"),
        CheckConstraint("match_count >= 0", name="check_match_count"),
        Index("idx_job_user_status", "user_id", "status"),
        Index("idx_job_company_title", "company", "title"),
        Index("idx_job_industry_type", "industry", "job_type"),
        Index("idx_job_location_remote", "location", "remote_type"),
        Index("idx_job_salary_range", "salary_min", "salary_max"),
        Index("idx_job_experience_level", "experience_level", "years_experience_min"),
        Index("idx_job_posted_date", "posted_date"),
        Index("idx_job_deadline", "application_deadline"),
        Index("idx_job_search", "search_vector", postgresql_using="gin"),
        Index("idx_job_skills", "required_skills", postgresql_using="gin"),
        Index("idx_job_keywords", "keywords", postgresql_using="gin"),
    )
    
    @validates("title")
    def validate_title(self, key, title):
        if not title or len(title.strip()) < 1:
            raise ValueError("Job title is required")
        return title.strip()
    
    @validates("company")
    def validate_company(self, key, company):
        if not company or len(company.strip()) < 1:
            raise ValueError("Company name is required")
        return company.strip()
    
    @validates("description")
    def validate_description(self, key, description):
        if not description or len(description.strip()) < 10:
            raise ValueError("Job description must be at least 10 characters")
        return description.strip()
    
    @validates("salary_currency")
    def validate_currency(self, key, currency):
        valid_currencies = ["USD", "EUR", "GBP", "CAD", "AUD", "JPY", "INR"]
        if currency not in valid_currencies:
            return "USD"
        return currency
    
    @validates("salary_period")
    def validate_salary_period(self, key, period):
        valid_periods = ["yearly", "monthly", "weekly", "daily", "hourly"]
        if period not in valid_periods:
            return "yearly"
        return period
    
    @property
    def has_salary_range(self) -> bool:
        """Check if job has salary information."""
        return self.salary_min is not None or self.salary_max is not None
    
    @property
    def salary_range_text(self) -> str:
        """Get formatted salary range."""
        if not self.has_salary_range:
            return "Not specified"
        
        if self.salary_min and self.salary_max:
            return f"{self.salary_currency} {self.salary_min:,} - {self.salary_max:,} {self.salary_period}"
        elif self.salary_min:
            return f"{self.salary_currency} {self.salary_min:,}+ {self.salary_period}"
        elif self.salary_max:
            return f"Up to {self.salary_currency} {self.salary_max:,} {self.salary_period}"
        
        return "Not specified"
    
    @property
    def is_remote_friendly(self) -> bool:
        """Check if job supports remote work."""
        return self.remote_type in [RemoteType.REMOTE, RemoteType.HYBRID]
    
    @property
    def is_active(self) -> bool:
        """Check if job is active."""
        return self.status == JobStatus.ACTIVE
    
    @property
    def is_expired(self) -> bool:
        """Check if application deadline has passed."""
        if not self.application_deadline:
            return False
        return datetime.utcnow() > self.application_deadline
    
    @property
    def total_skills(self) -> List[str]:
        """Get all skills (required + preferred)."""
        skills = []
        if self.required_skills:
            skills.extend(self.required_skills)
        if self.preferred_skills:
            skills.extend(self.preferred_skills)
        return list(set(skills))  # Remove duplicates
    
    def increment_view_count(self):
        """Increment view count."""
        self.view_count += 1
    
    def increment_match_count(self):
        """Increment match count."""
        self.match_count += 1
    
    def __repr__(self) -> str:
        return f"<JobDescription(id={self.id}, title='{self.title}', company='{self.company}')>"


class JobMatch(BaseModel):
    """Resume-Job matching results."""
    
    __tablename__ = "job_matches"
    
    resume_id = Column(
        UUID(as_uuid=True),
        ForeignKey("resumes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Resume ID"
    )
    
    job_description_id = Column(
        UUID(as_uuid=True),
        ForeignKey("job_descriptions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Job description ID"
    )
    
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="User who initiated the match"
    )
    
    # Match Scores
    overall_match_score = Column(
        Float,
        nullable=False,
        comment="Overall match score (0-100)"
    )
    
    skills_match_score = Column(
        Float,
        nullable=True,
        comment="Skills match score (0-100)"
    )
    
    experience_match_score = Column(
        Float,
        nullable=True,
        comment="Experience match score (0-100)"
    )
    
    education_match_score = Column(
        Float,
        nullable=True,
        comment="Education match score (0-100)"
    )
    
    keyword_match_score = Column(
        Float,
        nullable=True,
        comment="Keyword match score (0-100)"
    )
    
    # Match Details
    matched_skills = Column(
        ARRAY(String),
        nullable=True,
        comment="Skills that match"
    )
    
    missing_skills = Column(
        ARRAY(String),
        nullable=True,
        comment="Skills missing from resume"
    )
    
    matched_keywords = Column(
        ARRAY(String),
        nullable=True,
        comment="Keywords that match"
    )
    
    missing_keywords = Column(
        ARRAY(String),
        nullable=True,
        comment="Keywords missing from resume"
    )
    
    # Recommendations
    recommendations = Column(
        ARRAY(String),
        nullable=True,
        comment="Improvement recommendations"
    )
    
    # Analysis Data
    match_data = create_json_field(
        "match_data",
        default=dict,
        comment="Detailed match analysis"
    )
    
    # Status
    status = create_enum_field(
        "ProcessingStatus",
        "status",
        default="completed",
        comment="Match processing status"
    )
    
    processing_time = Column(
        Float,
        nullable=True,
        comment="Match processing time in seconds"
    )
    
    ai_model_used = Column(
        String(50),
        nullable=True,
        comment="AI model used for matching"
    )
    
    # User Actions
    is_bookmarked = Column(
        Boolean,
        default=False,
        nullable=False,
        comment="User bookmarked this match"
    )
    
    is_applied = Column(
        Boolean,
        default=False,
        nullable=False,
        comment="User applied to this job"
    )
    
    applied_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Application timestamp"
    )
    
    notes = Column(
        Text,
        nullable=True,
        comment="User notes about this match"
    )
    
    # Relationships
    resume = relationship("Resume", back_populates="job_matches")
    job_description = relationship("JobDescription", back_populates="job_matches")
    user = relationship("User")
    
    # Constraints
    __table_args__ = (
        CheckConstraint("overall_match_score >= 0 AND overall_match_score <= 100", name="check_overall_match_score"),
        CheckConstraint("skills_match_score >= 0 AND skills_match_score <= 100", name="check_skills_match_score"),
        CheckConstraint("experience_match_score >= 0 AND experience_match_score <= 100", name="check_experience_match_score"),
        CheckConstraint("education_match_score >= 0 AND education_match_score <= 100", name="check_education_match_score"),
        CheckConstraint("keyword_match_score >= 0 AND keyword_match_score <= 100", name="check_keyword_match_score"),
        Index("idx_match_resume_job", "resume_id", "job_description_id"),
        Index("idx_match_user_score", "user_id", "overall_match_score"),
        Index("idx_match_bookmarked", "user_id", "is_bookmarked"),
        Index("idx_match_applied", "user_id", "is_applied", "applied_at"),
        Index("idx_match_created", "created_at"),
    )
    
    @property
    def match_percentage(self) -> int:
        """Get match percentage as integer."""
        return int(round(self.overall_match_score))
    
    @property
    def is_good_match(self) -> bool:
        """Check if this is a good match (>= 70%)."""
        return self.overall_match_score >= 70.0
    
    @property
    def is_excellent_match(self) -> bool:
        """Check if this is an excellent match (>= 85%)."""
        return self.overall_match_score >= 85.0
    
    @property
    def skills_match_percentage(self) -> int:
        """Get skills match as percentage."""
        return int(round(self.skills_match_score)) if self.skills_match_score else 0
    
    @property
    def missing_skills_count(self) -> int:
        """Get count of missing skills."""
        return len(self.missing_skills) if self.missing_skills else 0
    
    def mark_as_applied(self):
        """Mark this match as applied."""
        self.is_applied = True
        self.applied_at = datetime.utcnow()
    
    def toggle_bookmark(self):
        """Toggle bookmark status."""
        self.is_bookmarked = not self.is_bookmarked
    
    def __repr__(self) -> str:
        return f"<JobMatch(id={self.id}, score={self.overall_match_score:.1f}, resume_id={self.resume_id})>"


# Export all models
__all__ = [
    "JobDescription",
    "JobMatch",
    "JobStatus",
    "JobType",
    "ExperienceLevel",
    "RemoteType"
]