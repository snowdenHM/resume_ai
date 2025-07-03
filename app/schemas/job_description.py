"""
Job description-related Pydantic schemas for request/response validation.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
import uuid

from pydantic import BaseModel, Field, validator

from app.models.job_description import JobStatus, JobType, ExperienceLevel, RemoteType


# Base schemas
class JobDescriptionBase(BaseModel):
    """Base job description schema with common fields."""
    
    title: str = Field(..., min_length=1, max_length=200, description="Job title")
    company: str = Field(..., min_length=1, max_length=200, description="Company name")
    location: Optional[str] = Field(None, max_length=200, description="Job location")
    job_type: JobType = Field(JobType.FULL_TIME, description="Employment type")
    experience_level: ExperienceLevel = Field(ExperienceLevel.MID_LEVEL, description="Required experience level")
    remote_type: RemoteType = Field(RemoteType.ON_SITE, description="Remote work type")
    industry: Optional[str] = Field(None, max_length=100, description="Industry sector")
    department: Optional[str] = Field(None, max_length=100, description="Department")
    description: str = Field(..., min_length=10, description="Full job description")


# Request schemas
class JobDescriptionCreateRequest(JobDescriptionBase):
    """Schema for creating a job description."""
    
    # Salary information
    salary_min: Optional[int] = Field(None, ge=0, description="Minimum salary")
    salary_max: Optional[int] = Field(None, ge=0, description="Maximum salary")
    salary_currency: str = Field("USD", max_length=10, description="Salary currency")
    salary_period: str = Field("yearly", description="Salary period")
    
    # Job details
    responsibilities: Optional[List[str]] = Field(None, description="Job responsibilities")
    requirements: Optional[List[str]] = Field(None, description="Job requirements")
    nice_to_have: Optional[List[str]] = Field(None, description="Nice to have qualifications")
    benefits: Optional[List[str]] = Field(None, description="Job benefits")
    
    # Skills and experience
    required_skills: Optional[List[str]] = Field(None, description="Required skills")
    preferred_skills: Optional[List[str]] = Field(None, description="Preferred skills")
    education_requirements: Optional[List[str]] = Field(None, description="Education requirements")
    years_experience_min: Optional[int] = Field(None, ge=0, le=50, description="Minimum years of experience")
    years_experience_max: Optional[int] = Field(None, ge=0, le=50, description="Maximum years of experience")
    
    # Application info
    application_url: Optional[str] = Field(None, max_length=500, description="Application URL")
    application_email: Optional[str] = Field(None, max_length=255, description="Application email")
    application_deadline: Optional[datetime] = Field(None, description="Application deadline")
    
    # Metadata
    status: JobStatus = Field(JobStatus.ACTIVE, description="Job posting status")
    posted_date: Optional[datetime] = Field(None, description="Job posting date")
    source_url: Optional[str] = Field(None, max_length=500, description="Original posting URL")
    source_platform: Optional[str] = Field(None, max_length=100, description="Job board platform")
    
    @validator("salary_max")
    def validate_salary_range(cls, v, values):
        salary_min = values.get("salary_min")
        if salary_min is not None and v is not None and v < salary_min:
            raise ValueError("Maximum salary must be greater than or equal to minimum salary")
        return v
    
    @validator("years_experience_max")
    def validate_experience_range(cls, v, values):
        years_min = values.get("years_experience_min")
        if years_min is not None and v is not None and v < years_min:
            raise ValueError("Maximum experience must be greater than or equal to minimum experience")
        return v


class JobDescriptionUpdateRequest(BaseModel):
    """Schema for updating a job description."""
    
    title: Optional[str] = Field(None, min_length=1, max_length=200, description="Job title")
    company: Optional[str] = Field(None, min_length=1, max_length=200, description="Company name")
    location: Optional[str] = Field(None, max_length=200, description="Job location")
    job_type: Optional[JobType] = Field(None, description="Employment type")
    experience_level: Optional[ExperienceLevel] = Field(None, description="Required experience level")
    remote_type: Optional[RemoteType] = Field(None, description="Remote work type")
    industry: Optional[str] = Field(None, max_length=100, description="Industry sector")
    department: Optional[str] = Field(None, max_length=100, description="Department")
    description: Optional[str] = Field(None, min_length=10, description="Full job description")
    
    # Salary information
    salary_min: Optional[int] = Field(None, ge=0, description="Minimum salary")
    salary_max: Optional[int] = Field(None, ge=0, description="Maximum salary")
    salary_currency: Optional[str] = Field(None, max_length=10, description="Salary currency")
    salary_period: Optional[str] = Field(None, description="Salary period")
    
    # Job details
    responsibilities: Optional[List[str]] = Field(None, description="Job responsibilities")
    requirements: Optional[List[str]] = Field(None, description="Job requirements")
    nice_to_have: Optional[List[str]] = Field(None, description="Nice to have qualifications")
    benefits: Optional[List[str]] = Field(None, description="Job benefits")
    
    # Skills and experience
    required_skills: Optional[List[str]] = Field(None, description="Required skills")
    preferred_skills: Optional[List[str]] = Field(None, description="Preferred skills")
    education_requirements: Optional[List[str]] = Field(None, description="Education requirements")
    years_experience_min: Optional[int] = Field(None, ge=0, le=50, description="Minimum years of experience")
    years_experience_max: Optional[int] = Field(None, ge=0, le=50, description="Maximum years of experience")
    
    # Application info
    application_url: Optional[str] = Field(None, max_length=500, description="Application URL")
    application_email: Optional[str] = Field(None, max_length=255, description="Application email")
    application_deadline: Optional[datetime] = Field(None, description="Application deadline")
    
    # Status
    status: Optional[JobStatus] = Field(None, description="Job posting status")


# Response schemas
class JobDescriptionResponse(JobDescriptionBase):
    """Schema for job description response."""
    
    id: uuid.UUID = Field(..., description="Job description ID")
    user_id: uuid.UUID = Field(..., description="User who added this job")
    
    # Salary information
    salary_min: Optional[int] = Field(None, description="Minimum salary")
    salary_max: Optional[int] = Field(None, description="Maximum salary")
    salary_currency: str = Field("USD", description="Salary currency")
    salary_period: str = Field("yearly", description="Salary period")
    salary_range_text: Optional[str] = Field(None, description="Formatted salary range")
    
    # Job details
    responsibilities: Optional[List[str]] = Field(None, description="Job responsibilities")
    requirements: Optional[List[str]] = Field(None, description="Job requirements")
    nice_to_have: Optional[List[str]] = Field(None, description="Nice to have qualifications")
    benefits: Optional[List[str]] = Field(None, description="Job benefits")
    
    # Skills and experience
    required_skills: Optional[List[str]] = Field(None, description="Required skills")
    preferred_skills: Optional[List[str]] = Field(None, description="Preferred skills")
    keywords: Optional[List[str]] = Field(None, description="Important keywords")
    education_requirements: Optional[List[str]] = Field(None, description="Education requirements")
    years_experience_min: Optional[int] = Field(None, description="Minimum years of experience")
    years_experience_max: Optional[int] = Field(None, description="Maximum years of experience")
    
    # Application info
    application_url: Optional[str] = Field(None, description="Application URL")
    application_email: Optional[str] = Field(None, description="Application email")
    application_deadline: Optional[datetime] = Field(None, description="Application deadline")
    
    # Status and metadata
    status: JobStatus = Field(..., description="Job posting status")
    posted_date: Optional[datetime] = Field(None, description="Job posting date")
    source_url: Optional[str] = Field(None, description="Original posting URL")
    source_platform: Optional[str] = Field(None, description="Job board platform")
    
    # AI analysis
    structured_data: Optional[Dict[str, Any]] = Field(None, description="AI-extracted structured data")
    analysis_score: Optional[float] = Field(None, description="Job description analysis score")
    complexity_score: Optional[float] = Field(None, description="Job complexity score")
    last_analyzed_at: Optional[datetime] = Field(None, description="Last analysis timestamp")
    
    # Tracking
    view_count: int = Field(0, description="Number of views")
    match_count: int = Field(0, description="Number of resume matches")
    
    # Computed properties
    has_salary_range: Optional[bool] = Field(None, description="Whether salary range is specified")
    is_remote_friendly: Optional[bool] = Field(None, description="Whether job supports remote work")
    is_active: Optional[bool] = Field(None, description="Whether job is currently active")
    is_expired: Optional[bool] = Field(None, description="Whether application deadline has passed")
    total_skills: Optional[List[str]] = Field(None, description="All skills (required + preferred)")
    
    # Timestamps
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    
    class Config:
        from_attributes = True


class JobDescriptionListResponse(BaseModel):
    """Schema for paginated job description list response."""
    
    jobs: List[JobDescriptionResponse] = Field(..., description="List of job descriptions")
    total_count: int = Field(..., description="Total number of jobs")
    page: int = Field(..., description="Current page number")
    page_size: int = Field(..., description="Page size")
    total_pages: int = Field(..., description="Total number of pages")


# Analysis schemas
class JobAnalysisResponse(BaseModel):
    """Schema for job description analysis response."""
    
    job_id: uuid.UUID = Field(..., description="Job description ID")
    analysis_score: float = Field(..., ge=0, le=100, description="Overall analysis score")
    complexity_score: float = Field(..., ge=0, le=100, description="Job complexity score")
    
    # Extracted requirements
    extracted_requirements: Dict[str, List[str]] = Field(..., description="Structured requirements")
    required_skills: List[str] = Field(..., description="Required technical skills")
    soft_skills: List[str] = Field(..., description="Required soft skills")
    education_level: Optional[str] = Field(None, description="Required education level")
    experience_range: Optional[Dict[str, int]] = Field(None, description="Experience requirements")
    
    # Keywords and terminology
    important_keywords: List[str] = Field(..., description="Important keywords for ATS")
    industry_terms: List[str] = Field(..., description="Industry-specific terminology")
    role_specific_terms: List[str] = Field(..., description="Role-specific terminology")
    
    # Analysis insights
    job_category: Optional[str] = Field(None, description="Categorized job type")
    seniority_level: Optional[str] = Field(None, description="Detected seniority level")
    department_type: Optional[str] = Field(None, description="Department categorization")
    company_size_indicators: Optional[List[str]] = Field(None, description="Company size indicators")
    
    # Quality assessment
    description_quality: Dict[str, float] = Field(..., description="Description quality metrics")
    clarity_score: float = Field(..., description="Clarity of requirements")
    completeness_score: float = Field(..., description="Completeness of information")
    
    # Recommendations
    improvement_suggestions: List[str] = Field(..., description="Suggestions for job posting")
    missing_information: List[str] = Field(..., description="Important missing information")
    
    analyzed_at: datetime = Field(..., description="Analysis timestamp")
    
    class Config:
        from_attributes = True


# Job matching schemas
class JobMatchResponse(BaseModel):
    """Schema for job match response."""
    
    id: uuid.UUID = Field(..., description="Match ID")
    resume_id: uuid.UUID = Field(..., description="Resume ID")
    job_description_id: uuid.UUID = Field(..., description="Job description ID")
    user_id: uuid.UUID = Field(..., description="User ID")
    
    # Match scores
    overall_match_score: float = Field(..., ge=0, le=100, description="Overall match score")
    skills_match_score: Optional[float] = Field(None, ge=0, le=100, description="Skills match score")
    experience_match_score: Optional[float] = Field(None, ge=0, le=100, description="Experience match score")
    education_match_score: Optional[float] = Field(None, ge=0, le=100, description="Education match score")
    keyword_match_score: Optional[float] = Field(None, ge=0, le=100, description="Keyword match score")
    
    # Match details
    matched_skills: Optional[List[str]] = Field(None, description="Skills that match")
    missing_skills: Optional[List[str]] = Field(None, description="Skills missing from resume")
    matched_keywords: Optional[List[str]] = Field(None, description="Keywords that match")
    missing_keywords: Optional[List[str]] = Field(None, description="Keywords missing from resume")
    
    # Recommendations
    recommendations: Optional[List[str]] = Field(None, description="Improvement recommendations")
    match_data: Optional[Dict[str, Any]] = Field(None, description="Detailed match analysis")
    
    # User actions
    is_bookmarked: bool = Field(False, description="User bookmarked this match")
    is_applied: bool = Field(False, description="User applied to this job")
    applied_at: Optional[datetime] = Field(None, description="Application timestamp")
    notes: Optional[str] = Field(None, description="User notes about this match")
    
    # Metadata
    processing_time: Optional[float] = Field(None, description="Match processing time")
    ai_model_used: Optional[str] = Field(None, description="AI model used")
    created_at: datetime = Field(..., description="Match creation timestamp")
    
    class Config:
        from_attributes = True


# Search and filter schemas
class JobSearchRequest(BaseModel):
    """Schema for job search request."""
    
    query: Optional[str] = Field(None, min_length=1, description="Text search query")
    skills: Optional[List[str]] = Field(None, description="Required skills filter")
    keywords: Optional[List[str]] = Field(None, description="Keywords filter")
    
    # Salary filters
    salary_min: Optional[int] = Field(None, ge=0, description="Minimum salary filter")
    salary_max: Optional[int] = Field(None, ge=0, description="Maximum salary filter")
    salary_currency: Optional[str] = Field(None, description="Salary currency filter")
    
    # Location and remote
    location: Optional[str] = Field(None, description="Location filter")
    remote_type: Optional[RemoteType] = Field(None, description="Remote work type filter")
    
    # Company and industry
    company: Optional[str] = Field(None, description="Company filter")
    industry: Optional[str] = Field(None, description="Industry filter")
    
    # Job characteristics
    job_type: Optional[JobType] = Field(None, description="Employment type filter")
    experience_level: Optional[ExperienceLevel] = Field(None, description="Experience level filter")
    
    # Date filters
    posted_after: Optional[datetime] = Field(None, description="Posted after date")
    posted_before: Optional[datetime] = Field(None, description="Posted before date")
    application_deadline_after: Optional[datetime] = Field(None, description="Deadline after date")
    
    # Advanced filters
    has_salary_info: Optional[bool] = Field(None, description="Has salary information")
    is_remote_friendly: Optional[bool] = Field(None, description="Supports remote work")
    min_match_score: Optional[float] = Field(None, ge=0, le=100, description="Minimum match score")
    
    # Pagination and sorting
    page: int = Field(1, ge=1, description="Page number")
    page_size: int = Field(20, ge=1, le=100, description="Page size")
    sort_by: str = Field("created_at", description="Sort field")
    sort_order: str = Field("desc", pattern="^(asc|desc)$", description="Sort order")


class JobStatsResponse(BaseModel):
    """Schema for job statistics response."""
    
    total_jobs: int = Field(..., description="Total number of jobs")
    active_jobs: int = Field(..., description="Number of active jobs")
    jobs_by_type: Dict[str, int] = Field(..., description="Job counts by type")
    jobs_by_industry: Dict[str, int] = Field(..., description="Job counts by industry")
    jobs_by_experience_level: Dict[str, int] = Field(..., description="Job counts by experience level")
    
    # Recent activity
    jobs_added_this_week: int = Field(..., description="Jobs added this week")
    jobs_added_this_month: int = Field(..., description="Jobs added this month")
    
    # Matching stats
    total_matches: int = Field(..., description="Total resume matches performed")
    average_match_score: Optional[float] = Field(None, description="Average match score")
    best_match_job: Optional[Dict[str, Any]] = Field(None, description="Best matching job")
    
    # Application tracking
    applications_count: int = Field(..., description="Number of applications tracked")
    bookmarked_jobs: int = Field(..., description="Number of bookmarked jobs")
    
    # Trends
    popular_skills: List[str] = Field(..., description="Most requested skills")
    popular_industries: List[str] = Field(..., description="Most active industries")
    salary_trends: Optional[Dict[str, Any]] = Field(None, description="Salary trend information")
    
    last_updated: datetime = Field(..., description="Statistics last updated")


# Import and URL extraction schemas
class JobImportRequest(BaseModel):
    """Schema for importing job from URL."""
    
    url: str = Field(..., description="Job posting URL")
    auto_extract: bool = Field(True, description="Automatically extract job information")
    save_as_draft: bool = Field(False, description="Save as draft instead of active")


class JobUrlExtractionResponse(BaseModel):
    """Schema for URL extraction response."""
    
    url: str = Field(..., description="Original URL")
    extracted_data: Dict[str, Any] = Field(..., description="Extracted job data")
    extraction_confidence: float = Field(..., ge=0, le=1, description="Confidence in extraction")
    
    # Extracted fields
    title: Optional[str] = Field(None, description="Extracted job title")
    company: Optional[str] = Field(None, description="Extracted company name")
    location: Optional[str] = Field(None, description="Extracted location")
    description: Optional[str] = Field(None, description="Extracted description")
    requirements: Optional[List[str]] = Field(None, description="Extracted requirements")
    
    # Metadata
    source_platform: Optional[str] = Field(None, description="Detected job board")
    extraction_method: str = Field(..., description="Method used for extraction")
    extracted_at: datetime = Field(..., description="Extraction timestamp")
    
    # Issues and warnings
    extraction_warnings: List[str] = Field(..., description="Extraction warnings")
    missing_fields: List[str] = Field(..., description="Fields that couldn't be extracted")


# Export all schemas
__all__ = [
    # Base schemas
    "JobDescriptionBase",
    
    # Request schemas
    "JobDescriptionCreateRequest",
    "JobDescriptionUpdateRequest",
    "JobSearchRequest",
    "JobImportRequest",
    
    # Response schemas
    "JobDescriptionResponse",
    "JobDescriptionListResponse",
    "JobAnalysisResponse",
    "JobMatchResponse",
    "JobStatsResponse",
    "JobUrlExtractionResponse"
]