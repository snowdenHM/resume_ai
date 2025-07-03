"""
Resume-related database models.
"""

from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any

from sqlalchemy import (
    Column, String, Boolean, DateTime, Integer, Text, Float,
    ForeignKey, Index, CheckConstraint, UniqueConstraint
)
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY, TSVECTOR
from sqlalchemy.orm import relationship, validates
from sqlalchemy.sql import func

from app.models.base import BaseModel, SoftDeleteModel, create_enum_field, create_json_field


class ResumeStatus(str, Enum):
    """Resume processing status."""
    DRAFT = "draft"
    PROCESSING = "processing" 
    COMPLETED = "completed"
    ERROR = "error"
    ARCHIVED = "archived"


class ResumeType(str, Enum):
    """Resume type enumeration."""
    ORIGINAL = "original"
    OPTIMIZED = "optimized"
    TEMPLATE_BASED = "template_based"
    AI_GENERATED = "ai_generated"


class ProcessingStatus(str, Enum):
    """Processing status for various operations."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Resume(SoftDeleteModel):
    """Main resume model."""
    
    __tablename__ = "resumes"
    
    # Basic Information
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Owner user ID"
    )
    
    title = Column(
        String(200),
        nullable=False,
        comment="Resume title/name"
    )
    
    description = Column(
        Text,
        nullable=True,
        comment="Resume description"
    )
    
    # Status and Type
    status = create_enum_field(
        ResumeStatus,
        "status",
        default=ResumeStatus.DRAFT,
        comment="Processing status"
    )
    
    resume_type = create_enum_field(
        ResumeType,
        "resume_type", 
        default=ResumeType.ORIGINAL,
        comment="Resume type"
    )
    
    # File Information
    original_filename = Column(
        String(255),
        nullable=True,
        comment="Original uploaded filename"
    )
    
    file_path = Column(
        String(500),
        nullable=True,
        comment="File storage path"
    )
    
    file_size = Column(
        Integer,
        nullable=True,
        comment="File size in bytes"
    )
    
    file_type = Column(
        String(50),
        nullable=True,
        comment="MIME type"
    )
    
    # Content
    raw_text = Column(
        Text,
        nullable=True,
        comment="Extracted raw text content"
    )
    
    structured_data = create_json_field(
        "structured_data",
        default=dict,
        comment="Structured resume data"
    )
    
    # Metadata
    language = Column(
        String(10),
        default="en",
        nullable=False,
        comment="Resume language"
    )
    
    word_count = Column(
        Integer,
        nullable=True,
        comment="Total word count"
    )
    
    page_count = Column(
        Integer,
        nullable=True,
        comment="Number of pages"
    )
    
    # Versioning
    version = Column(
        String(20),
        default="1.0",
        nullable=False,
        comment="Resume version"
    )
    
    parent_resume_id = Column(
        UUID(as_uuid=True),
        ForeignKey("resumes.id", ondelete="CASCADE"),
        nullable=True,
        comment="Parent resume for versions"
    )
    
    # Template Information
    template_id = Column(
        UUID(as_uuid=True),
        ForeignKey("resume_templates.id", ondelete="SET NULL"),
        nullable=True,
        comment="Applied template"
    )
    
    # Search and Analysis
    search_vector = Column(
        TSVECTOR,
        nullable=True,
        comment="Full-text search vector"
    )
    
    keywords = Column(
        ARRAY(String),
        nullable=True,
        comment="Extracted keywords"
    )
    
    skills = Column(
        ARRAY(String),
        nullable=True,
        comment="Extracted skills"
    )
    
    # AI Analysis Results
    analysis_score = Column(
        Float,
        nullable=True,
        comment="Overall analysis score (0-100)"
    )
    
    ats_score = Column(
        Float,
        nullable=True,
        comment="ATS compatibility score (0-100)"
    )
    
    last_analyzed_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Last analysis timestamp"
    )
    
    # Relationships
    user = relationship("User", back_populates="resumes")
    template = relationship("ResumeTemplate", back_populates="resumes")
    parent_resume = relationship("Resume", remote_side="Resume.id")
    child_resumes = relationship("Resume", back_populates="parent_resume")
    sections = relationship("ResumeSection", back_populates="resume", cascade="all, delete-orphan")
    analyses = relationship("ResumeAnalysis", back_populates="resume", cascade="all, delete-orphan")
    job_matches = relationship("JobMatch", back_populates="resume", cascade="all, delete-orphan")
    exports = relationship("ResumeExport", back_populates="resume", cascade="all, delete-orphan")
    
    # Constraints
    __table_args__ = (
        CheckConstraint("analysis_score >= 0 AND analysis_score <= 100", name="check_analysis_score"),
        CheckConstraint("ats_score >= 0 AND ats_score <= 100", name="check_ats_score"),
        CheckConstraint("word_count >= 0", name="check_word_count"),
        CheckConstraint("page_count >= 0", name="check_page_count"),
        Index("idx_resume_user_status", "user_id", "status"),
        Index("idx_resume_type_created", "resume_type", "created_at"),
        Index("idx_resume_search", "search_vector", postgresql_using="gin"),
        Index("idx_resume_skills", "skills", postgresql_using="gin"),
        Index("idx_resume_parent", "parent_resume_id"),
    )
    
    @validates("title")
    def validate_title(self, key, title):
        if not title or len(title.strip()) < 1:
            raise ValueError("Resume title is required")
        return title.strip()
    
    @validates("version")
    def validate_version(self, key, version):
        if not version:
            return "1.0"
        return version
    
    @property
    def is_original(self) -> bool:
        """Check if this is an original resume."""
        return self.resume_type == ResumeType.ORIGINAL
    
    @property
    def is_optimized(self) -> bool:
        """Check if this is an optimized resume."""
        return self.resume_type in [ResumeType.OPTIMIZED, ResumeType.AI_GENERATED]
    
    @property
    def has_analysis(self) -> bool:
        """Check if resume has been analyzed."""
        return self.analysis_score is not None
    
    @property
    def section_count(self) -> int:
        """Get number of sections."""
        return len(self.sections) if self.sections else 0
    
    def __repr__(self) -> str:
        return f"<Resume(id={self.id}, title='{self.title}', user_id={self.user_id})>"


class ResumeSection(BaseModel):
    """Resume sections (experience, education, skills, etc.)."""
    
    __tablename__ = "resume_sections"
    
    resume_id = Column(
        UUID(as_uuid=True),
        ForeignKey("resumes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Resume ID"
    )
    
    section_type = Column(
        String(50),
        nullable=False,
        comment="Section type (personal_info, experience, education, etc.)"
    )
    
    title = Column(
        String(200),
        nullable=False,
        comment="Section title"
    )
    
    content = Column(
        Text,
        nullable=True,
        comment="Section content"
    )
    
    structured_content = create_json_field(
        "structured_content",
        default=dict,
        comment="Structured section data"
    )
    
    order_index = Column(
        Integer,
        default=0,
        nullable=False,
        comment="Display order"
    )
    
    is_visible = Column(
        Boolean,
        default=True,
        nullable=False,
        comment="Section visibility"
    )
    
    # Relationships
    resume = relationship("Resume", back_populates="sections")
    
    # Constraints
    __table_args__ = (
        UniqueConstraint("resume_id", "section_type", name="uq_resume_section_type"),
        Index("idx_section_resume_order", "resume_id", "order_index"),
        Index("idx_section_type_visible", "section_type", "is_visible"),
    )
    
    @validates("section_type")
    def validate_section_type(self, key, section_type):
        valid_types = [
            "personal_info", "summary", "objective", "experience", "education",
            "skills", "certifications", "projects", "achievements", "languages",
            "references", "publications", "awards", "volunteer", "interests"
        ]
        if section_type not in valid_types:
            raise ValueError(f"Invalid section type: {section_type}")
        return section_type
    
    def __repr__(self) -> str:
        return f"<ResumeSection(id={self.id}, type='{self.section_type}', resume_id={self.resume_id})>"


class ResumeAnalysis(BaseModel):
    """Resume analysis results from AI."""
    
    __tablename__ = "resume_analyses"
    
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
        nullable=True,
        index=True,
        comment="Job description ID (if job-specific analysis)"
    )
    
    analysis_type = Column(
        String(50),
        nullable=False,
        comment="Type of analysis (general, job_match, ats_check, etc.)"
    )
    
    # Scores
    overall_score = Column(
        Float,
        nullable=True,
        comment="Overall score (0-100)"
    )
    
    ats_score = Column(
        Float,
        nullable=True,
        comment="ATS compatibility score (0-100)"
    )
    
    content_score = Column(
        Float,
        nullable=True,
        comment="Content quality score (0-100)"
    )
    
    keyword_score = Column(
        Float,
        nullable=True,
        comment="Keyword optimization score (0-100)"
    )
    
    format_score = Column(
        Float,
        nullable=True,
        comment="Format quality score (0-100)"
    )
    
    # Analysis Results
    strengths = Column(
        ARRAY(String),
        nullable=True,
        comment="Identified strengths"
    )
    
    weaknesses = Column(
        ARRAY(String),
        nullable=True,
        comment="Areas for improvement"
    )
    
    recommendations = Column(
        ARRAY(String),
        nullable=True,
        comment="Improvement recommendations"
    )
    
    missing_keywords = Column(
        ARRAY(String),
        nullable=True,
        comment="Missing important keywords"
    )
    
    extracted_skills = Column(
        ARRAY(String),
        nullable=True,
        comment="Skills found in resume"
    )
    
    # Detailed Analysis
    analysis_data = create_json_field(
        "analysis_data",
        default=dict,
        comment="Detailed analysis results"
    )
    
    processing_time = Column(
        Float,
        nullable=True,
        comment="Analysis processing time in seconds"
    )
    
    ai_model_used = Column(
        String(50),
        nullable=True,
        comment="AI model used for analysis"
    )
    
    # Status
    status = create_enum_field(
        ProcessingStatus,
        "status",
        default=ProcessingStatus.PENDING,
        comment="Analysis processing status"
    )
    
    error_message = Column(
        Text,
        nullable=True,
        comment="Error message if analysis failed"
    )
    
    # Relationships
    resume = relationship("Resume", back_populates="analyses")
    job_description = relationship("JobDescription", back_populates="resume_analyses")
    
    # Constraints
    __table_args__ = (
        CheckConstraint("overall_score >= 0 AND overall_score <= 100", name="check_overall_score"),
        CheckConstraint("ats_score >= 0 AND ats_score <= 100", name="check_ats_score_analysis"),
        CheckConstraint("content_score >= 0 AND content_score <= 100", name="check_content_score"),
        CheckConstraint("keyword_score >= 0 AND keyword_score <= 100", name="check_keyword_score"),
        CheckConstraint("format_score >= 0 AND format_score <= 100", name="check_format_score"),
        Index("idx_analysis_resume_type", "resume_id", "analysis_type"),
        Index("idx_analysis_status_created", "status", "created_at"),
        Index("idx_analysis_job_resume", "job_description_id", "resume_id"),
    )
    
    @validates("analysis_type")
    def validate_analysis_type(self, key, analysis_type):
        valid_types = [
            "general", "job_match", "ats_check", "keyword_analysis", 
            "content_review", "format_check", "skill_assessment"
        ]
        if analysis_type not in valid_types:
            raise ValueError(f"Invalid analysis type: {analysis_type}")
        return analysis_type
    
    @property
    def is_completed(self) -> bool:
        """Check if analysis is completed."""
        return self.status == ProcessingStatus.COMPLETED
    
    @property
    def has_recommendations(self) -> bool:
        """Check if analysis has recommendations."""
        return bool(self.recommendations)
    
    def __repr__(self) -> str:
        return f"<ResumeAnalysis(id={self.id}, type='{self.analysis_type}', resume_id={self.resume_id})>"


class ResumeExport(BaseModel):
    """Resume export history and tracking."""
    
    __tablename__ = "resume_exports"
    
    resume_id = Column(
        UUID(as_uuid=True),
        ForeignKey("resumes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Resume ID"
    )
    
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="User who exported"
    )
    
    export_format = Column(
        String(20),
        nullable=False,
        comment="Export format (pdf, docx, json)"
    )
    
    template_id = Column(
        UUID(as_uuid=True),
        ForeignKey("resume_templates.id", ondelete="SET NULL"),
        nullable=True,
        comment="Template used for export"
    )
    
    # File Information
    file_path = Column(
        String(500),
        nullable=True,
        comment="Exported file path"
    )
    
    file_size = Column(
        Integer,
        nullable=True,
        comment="Exported file size"
    )
    
    download_url = Column(
        String(500),
        nullable=True,
        comment="Download URL"
    )
    
    # Export Settings
    export_settings = create_json_field(
        "export_settings",
        default=dict,
        comment="Export configuration"
    )
    
    # Status and Timing
    status = create_enum_field(
        ProcessingStatus,
        "status",
        default=ProcessingStatus.PENDING,
        comment="Export processing status"
    )
    
    started_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Export start time"
    )
    
    completed_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Export completion time"
    )
    
    processing_time = Column(
        Float,
        nullable=True,
        comment="Export processing time in seconds"
    )
    
    # Download Tracking
    download_count = Column(
        Integer,
        default=0,
        nullable=False,
        comment="Number of downloads"
    )
    
    last_downloaded_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Last download timestamp"
    )
    
    expires_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Export expiration time"
    )
    
    error_message = Column(
        Text,
        nullable=True,
        comment="Error message if export failed"
    )
    
    # Relationships
    resume = relationship("Resume", back_populates="exports")
    user = relationship("User")
    template = relationship("ResumeTemplate")
    
    # Constraints
    __table_args__ = (
        CheckConstraint("download_count >= 0", name="check_download_count"),
        Index("idx_export_user_format", "user_id", "export_format"),
        Index("idx_export_status_created", "status", "created_at"),
        Index("idx_export_expires", "expires_at"),
    )
    
    @validates("export_format")
    def validate_export_format(self, key, export_format):
        valid_formats = ["pdf", "docx", "json", "html", "txt"]
        if export_format not in valid_formats:
            raise ValueError(f"Invalid export format: {export_format}")
        return export_format
    
    @property
    def is_expired(self) -> bool:
        """Check if export has expired."""
        if not self.expires_at:
            return False
        return datetime.utcnow() > self.expires_at
    
    @property
    def is_completed(self) -> bool:
        """Check if export is completed."""
        return self.status == ProcessingStatus.COMPLETED
    
    def increment_download_count(self):
        """Increment download count and update timestamp."""
        self.download_count += 1
        self.last_downloaded_at = datetime.utcnow()
    
    def __repr__(self) -> str:
        return f"<ResumeExport(id={self.id}, format='{self.export_format}', resume_id={self.resume_id})>"


# Export all models
__all__ = [
    "Resume",
    "ResumeSection", 
    "ResumeAnalysis",
    "ResumeExport",
    "ResumeStatus",
    "ResumeType",
    "ProcessingStatus"
]