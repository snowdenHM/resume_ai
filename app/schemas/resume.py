"""
Resume-related Pydantic schemas for request/response validation.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
import uuid

from pydantic import BaseModel, Field, validator

from app.models.resume import ResumeStatus, ResumeType, ProcessingStatus


# Base schemas
class ResumeBase(BaseModel):
    """Base resume schema with common fields."""
    
    title: str = Field(..., min_length=1, max_length=200, description="Resume title")
    description: Optional[str] = Field(None, max_length=1000, description="Resume description")


# Request schemas
class ResumeCreateRequest(ResumeBase):
    """Schema for creating a new resume."""
    pass


class ResumeUpdateRequest(BaseModel):
    """Schema for updating a resume."""
    
    title: Optional[str] = Field(None, min_length=1, max_length=200, description="Resume title")
    description: Optional[str] = Field(None, max_length=1000, description="Resume description")
    sections: Optional[Dict[str, Any]] = Field(None, description="Resume sections data")


class ResumeOptimizationRequest(BaseModel):
    """Schema for resume optimization request."""
    
    job_description_id: uuid.UUID = Field(..., description="Target job description ID")
    optimization_type: str = Field(
        "full", 
        regex="^(full|keywords|format|content)$",
        description="Type of optimization"
    )


# Section schemas
class ResumeSectionBase(BaseModel):
    """Base resume section schema."""
    
    section_type: str = Field(..., description="Section type")
    title: str = Field(..., description="Section title") 
    content: Optional[str] = Field(None, description="Section content")
    structured_content: Optional[Dict[str, Any]] = Field(None, description="Structured content")
    order_index: int = Field(0, description="Display order")
    is_visible: bool = Field(True, description="Section visibility")


class ResumeSectionResponse(ResumeSectionBase):
    """Schema for resume section response."""
    
    id: uuid.UUID = Field(..., description="Section ID")
    resume_id: uuid.UUID = Field(..., description="Resume ID")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    
    class Config:
        from_attributes = True


# Analysis schemas
class ResumeAnalysisBase(BaseModel):
    """Base resume analysis schema."""
    
    analysis_type: str = Field(..., description="Analysis type")
    overall_score: Optional[float] = Field(None, ge=0, le=100, description="Overall score")
    ats_score: Optional[float] = Field(None, ge=0, le=100, description="ATS score")
    content_score: Optional[float] = Field(None, ge=0, le=100, description="Content score")
    keyword_score: Optional[float] = Field(None, ge=0, le=100, description="Keyword score")
    format_score: Optional[float] = Field(None, ge=0, le=100, description="Format score")


class ResumeAnalysisResponse(ResumeAnalysisBase):
    """Schema for resume analysis response."""
    
    id: uuid.UUID = Field(..., description="Analysis ID")
    resume_id: uuid.UUID = Field(..., description="Resume ID")
    job_description_id: Optional[uuid.UUID] = Field(None, description="Job description ID")
    status: ProcessingStatus = Field(..., description="Analysis status")
    strengths: Optional[List[str]] = Field(None, description="Identified strengths")
    weaknesses: Optional[List[str]] = Field(None, description="Areas for improvement")
    recommendations: Optional[List[str]] = Field(None, description="Recommendations")
    missing_keywords: Optional[List[str]] = Field(None, description="Missing keywords")
    extracted_skills: Optional[List[str]] = Field(None, description="Extracted skills")
    analysis_data: Optional[Dict[str, Any]] = Field(None, description="Detailed analysis data")
    processing_time: Optional[float] = Field(None, description="Processing time in seconds")
    ai_model_used: Optional[str] = Field(None, description="AI model used")
    error_message: Optional[str] = Field(None, description="Error message if failed")
    created_at: datetime = Field(..., description="Analysis timestamp")
    
    class Config:
        from_attributes = True


# Main resume schemas
class ResumeResponse(ResumeBase):
    """Schema for resume response."""
    
    id: uuid.UUID = Field(..., description="Resume ID")
    user_id: uuid.UUID = Field(..., description="Owner user ID")
    status: ResumeStatus = Field(..., description="Resume status")
    resume_type: ResumeType = Field(..., description="Resume type")
    version: str = Field(..., description="Resume version")
    parent_resume_id: Optional[uuid.UUID] = Field(None, description="Parent resume ID")
    
    # File information
    original_filename: Optional[str] = Field(None, description="Original filename")
    file_path: Optional[str] = Field(None, description="File storage path")
    file_size: Optional[int] = Field(None, description="File size in bytes")
    file_type: Optional[str] = Field(None, description="File MIME type")
    
    # Content
    word_count: Optional[int] = Field(None, description="Word count")
    page_count: Optional[int] = Field(None, description="Page count")
    language: str = Field("en", description="Resume language")
    
    # Analysis results
    analysis_score: Optional[float] = Field(None, ge=0, le=100, description="Latest analysis score")
    ats_score: Optional[float] = Field(None, ge=0, le=100, description="Latest ATS score")
    last_analyzed_at: Optional[datetime] = Field(None, description="Last analysis timestamp")
    
    # Metadata
    skills: Optional[List[str]] = Field(None, description="Extracted skills")
    keywords: Optional[List[str]] = Field(None, description="Extracted keywords")
    structured_data: Optional[Dict[str, Any]] = Field(None, description="Structured resume data")
    
    # Template
    template_id: Optional[uuid.UUID] = Field(None, description="Applied template ID")
    
    # Timestamps
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    
    # Relationships (optional, loaded based on context)
    sections: Optional[List[ResumeSectionResponse]] = Field(None, description="Resume sections")
    analyses: Optional[List[ResumeAnalysisResponse]] = Field(None, description="Recent analyses")
    
    class Config:
        from_attributes = True


class ResumeUploadResponse(ResumeResponse):
    """Schema for resume upload response."""
    
    parsing_status: str = Field(..., description="File parsing status")
    analysis_queued: bool = Field(False, description="Whether analysis was queued")


class ResumeListResponse(BaseModel):
    """Schema for paginated resume list response."""
    
    resumes: List[ResumeResponse] = Field(..., description="List of resumes")
    total_count: int = Field(..., description="Total number of resumes")
    page: int = Field(..., description="Current page number")
    page_size: int = Field(..., description="Page size")
    total_pages: int = Field(..., description="Total number of pages")


class ResumeStatsResponse(BaseModel):
    """Schema for resume statistics response."""
    
    total_resumes: int = Field(..., description="Total number of resumes")
    status_counts: Dict[str, int] = Field(..., description="Resume counts by status")
    total_analyses: int = Field(..., description="Total number of analyses")
    latest_analysis_score: Optional[float] = Field(None, description="Latest analysis score")
    average_analysis_score: Optional[float] = Field(None, description="Average analysis score")
    can_create_more: bool = Field(..., description="Whether user can create more resumes")
    max_resumes_allowed: int = Field(..., description="Maximum resumes allowed")


# Export schemas
class ResumeExportRequest(BaseModel):
    """Schema for resume export request."""
    
    export_format: str = Field(
        ...,
        regex="^(pdf|docx|json|html)$",
        description="Export format"
    )
    template_id: Optional[uuid.UUID] = Field(None, description="Template to use for export")
    export_settings: Optional[Dict[str, Any]] = Field(None, description="Export configuration")


class ResumeExportResponse(BaseModel):
    """Schema for resume export response."""
    
    id: uuid.UUID = Field(..., description="Export ID")
    resume_id: uuid.UUID = Field(..., description="Resume ID")
    export_format: str = Field(..., description="Export format")
    status: ProcessingStatus = Field(..., description="Export status")
    download_url: Optional[str] = Field(None, description="Download URL")
    file_size: Optional[int] = Field(None, description="File size in bytes")
    expires_at: Optional[datetime] = Field(None, description="Expiration timestamp")
    processing_time: Optional[float] = Field(None, description="Processing time")
    error_message: Optional[str] = Field(None, description="Error message if failed")
    created_at: datetime = Field(..., description="Export creation time")
    
    class Config:
        from_attributes = True


# Search and filter schemas
class ResumeSearchRequest(BaseModel):
    """Schema for resume search request."""
    
    query: Optional[str] = Field(None, min_length=1, description="Search query")
    skills: Optional[List[str]] = Field(None, description="Filter by skills")
    keywords: Optional[List[str]] = Field(None, description="Filter by keywords")
    min_score: Optional[float] = Field(None, ge=0, le=100, description="Minimum analysis score")
    max_score: Optional[float] = Field(None, ge=0, le=100, description="Maximum analysis score")
    status: Optional[ResumeStatus] = Field(None, description="Filter by status")
    resume_type: Optional[ResumeType] = Field(None, description="Filter by type")
    created_after: Optional[datetime] = Field(None, description="Created after date")
    created_before: Optional[datetime] = Field(None, description="Created before date")
    page: int = Field(1, ge=1, description="Page number")
    page_size: int = Field(20, ge=1, le=100, description="Page size")
    sort_by: str = Field("updated_at", description="Sort field")
    sort_order: str = Field("desc", regex="^(asc|desc)$", description="Sort order")
    
    @validator("max_score")
    def validate_score_range(cls, v, values):
        min_score = values.get("min_score")
        if min_score is not None and v is not None and v < min_score:
            raise ValueError("max_score must be greater than or equal to min_score")
        return v


# Bulk operation schemas
class BulkResumeAnalysisRequest(BaseModel):
    """Schema for bulk resume analysis request."""
    
    resume_ids: List[uuid.UUID] = Field(..., min_items=1, max_items=10, description="Resume IDs to analyze")
    analysis_type: str = Field(
        "general",
        regex="^(general|ats_check)$",
        description="Type of analysis"
    )


class BulkResumeAnalysisResponse(BaseModel):
    """Schema for bulk analysis response."""
    
    requested_count: int = Field(..., description="Number of analyses requested")
    queued_count: int = Field(..., description="Number of analyses queued")
    failed_count: int = Field(..., description="Number of failures")
    task_ids: List[str] = Field(..., description="Celery task IDs")
    estimated_completion: Optional[datetime] = Field(None, description="Estimated completion time")


# Version management schemas
class ResumeVersionResponse(BaseModel):
    """Schema for resume version information."""
    
    id: uuid.UUID = Field(..., description="Resume ID")
    version: str = Field(..., description="Version number")
    title: str = Field(..., description="Resume title")
    resume_type: ResumeType = Field(..., description="Resume type")
    parent_resume_id: Optional[uuid.UUID] = Field(None, description="Parent resume ID")
    analysis_score: Optional[float] = Field(None, description="Analysis score")
    created_at: datetime = Field(..., description="Creation timestamp")
    
    class Config:
        from_attributes = True


class ResumeVersionListResponse(BaseModel):
    """Schema for resume version list response."""
    
    versions: List[ResumeVersionResponse] = Field(..., description="Resume versions")
    total_count: int = Field(..., description="Total version count")


# AI-specific schemas
class ResumeAIInsights(BaseModel):
    """Schema for AI-generated insights."""
    
    content_quality: str = Field(..., description="Content quality assessment")
    ats_compatibility: str = Field(..., description="ATS compatibility assessment")
    improvement_suggestions: List[str] = Field(..., description="Specific improvement suggestions")
    industry_alignment: Optional[str] = Field(None, description="Industry alignment assessment")
    experience_presentation: str = Field(..., description="Experience presentation feedback")
    skills_optimization: List[str] = Field(..., description="Skills optimization suggestions")


class ResumeComparisonRequest(BaseModel):
    """Schema for comparing two resumes."""
    
    resume_id_1: uuid.UUID = Field(..., description="First resume ID")
    resume_id_2: uuid.UUID = Field(..., description="Second resume ID")
    comparison_type: str = Field(
        "comprehensive",
        regex="^(comprehensive|scores_only|content_only)$",
        description="Type of comparison"
    )


class ResumeComparisonResponse(BaseModel):
    """Schema for resume comparison response."""
    
    resume_1: ResumeResponse = Field(..., description="First resume")
    resume_2: ResumeResponse = Field(..., description="Second resume") 
    score_comparison: Dict[str, Any] = Field(..., description="Score comparison")
    content_differences: Optional[Dict[str, Any]] = Field(None, description="Content differences")
    recommendations: List[str] = Field(..., description="Comparison-based recommendations")


# Export all schemas
__all__ = [
    # Base schemas
    "ResumeBase",
    "ResumeSectionBase",
    "ResumeAnalysisBase",
    
    # Request schemas
    "ResumeCreateRequest",
    "ResumeUpdateRequest",
    "ResumeOptimizationRequest",
    "ResumeExportRequest",
    "ResumeSearchRequest",
    "BulkResumeAnalysisRequest",
    "ResumeComparisonRequest",
    
    # Response schemas
    "ResumeResponse",
    "ResumeUploadResponse",
    "ResumeListResponse",
    "ResumeStatsResponse",
    "ResumeSectionResponse",
    "ResumeAnalysisResponse",
    "ResumeExportResponse",
    "BulkResumeAnalysisResponse",
    "ResumeVersionResponse",
    "ResumeVersionListResponse",
    "ResumeComparisonResponse",
    
    # AI schemas
    "ResumeAIInsights"
]