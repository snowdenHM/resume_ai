"""
Analysis-related Pydantic schemas for request/response validation.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
import uuid

from pydantic import BaseModel, Field, validator

from app.models.resume import ProcessingStatus


# Base schemas
class AnalysisBase(BaseModel):
    """Base analysis schema with common fields."""
    
    analysis_type: str = Field(..., description="Type of analysis")
    overall_score: Optional[float] = Field(None, ge=0, le=100, description="Overall score")
    ats_score: Optional[float] = Field(None, ge=0, le=100, description="ATS score")
    content_score: Optional[float] = Field(None, ge=0, le=100, description="Content score")
    keyword_score: Optional[float] = Field(None, ge=0, le=100, description="Keyword score")
    format_score: Optional[float] = Field(None, ge=0, le=100, description="Format score")


# Request schemas
class AnalysisRequest(BaseModel):
    """Schema for analysis request."""
    
    resume_id: uuid.UUID = Field(..., description="Resume ID to analyze")
    job_description_id: Optional[uuid.UUID] = Field(None, description="Job description for targeted analysis")
    analysis_type: str = Field(
        "comprehensive",
        regex="^(comprehensive|quick|ats|content|keywords)$",
        description="Type of analysis"
    )
    include_suggestions: bool = Field(True, description="Include improvement suggestions")


class BatchAnalysisRequest(BaseModel):
    """Schema for batch analysis request."""
    
    resume_ids: List[uuid.UUID] = Field(..., min_items=1, max_items=10, description="Resume IDs to analyze")
    analysis_type: str = Field(
        "general",
        regex="^(general|quick|ats)$",
        description="Type of analysis"
    )
    job_description_id: Optional[uuid.UUID] = Field(None, description="Job description for targeted analysis")
    priority: str = Field("normal", regex="^(normal|high)$", description="Analysis priority")


class AnalysisReportRequest(BaseModel):
    """Schema for analysis report request."""
    
    resume_ids: List[uuid.UUID] = Field(..., min_items=1, max_items=20, description="Resumes to include")
    report_type: str = Field(
        "individual",
        regex="^(individual|comparative|portfolio)$",
        description="Type of report"
    )
    include_trends: bool = Field(True, description="Include trend analysis")
    include_recommendations: bool = Field(True, description="Include recommendations")
    format: str = Field("pdf", regex="^(pdf|html|json)$", description="Report format")
    time_period: Optional[str] = Field("3months", description="Time period for trends")


# Response schemas
class AnalysisResponse(AnalysisBase):
    """Schema for analysis response."""
    
    id: uuid.UUID = Field(..., description="Analysis ID")
    resume_id: uuid.UUID = Field(..., description="Resume ID")
    job_description_id: Optional[uuid.UUID] = Field(None, description="Job description ID")
    status: ProcessingStatus = Field(..., description="Analysis status")
    
    # Analysis results
    strengths: Optional[List[str]] = Field(None, description="Identified strengths")
    weaknesses: Optional[List[str]] = Field(None, description="Areas for improvement")
    recommendations: Optional[List[str]] = Field(None, description="Improvement recommendations")
    missing_keywords: Optional[List[str]] = Field(None, description="Missing keywords")
    extracted_skills: Optional[List[str]] = Field(None, description="Extracted skills")
    
    # Detailed analysis
    analysis_data: Optional[Dict[str, Any]] = Field(None, description="Detailed analysis data")
    insights: Optional[Dict[str, Any]] = Field(None, description="AI insights")
    
    # Processing info
    processing_time: Optional[float] = Field(None, description="Processing time in seconds")
    ai_model_used: Optional[str] = Field(None, description="AI model used")
    error_message: Optional[str] = Field(None, description="Error message if failed")
    
    # Timestamps
    created_at: datetime = Field(..., description="Analysis timestamp")
    
    class Config:
        from_attributes = True


class AnalysisListResponse(BaseModel):
    """Schema for paginated analysis list response."""
    
    analyses: List[AnalysisResponse] = Field(..., description="List of analyses")
    total_count: int = Field(..., description="Total number of analyses")
    page: int = Field(..., description="Current page number")
    page_size: int = Field(..., description="Page size")
    total_pages: int = Field(..., description="Total number of pages")


class AnalysisComparisonResponse(BaseModel):
    """Schema for analysis comparison response."""
    
    comparison_id: str = Field(..., description="Comparison ID")
    resume_analyses: List[AnalysisResponse] = Field(..., description="Individual analyses")
    comparison_data: Dict[str, Any] = Field(..., description="Comparison results")
    relative_strengths: Dict[str, List[str]] = Field(..., description="Relative strengths per resume")
    improvement_priority: List[Dict[str, Any]] = Field(..., description="Prioritized improvements")
    best_practices: List[str] = Field(..., description="Best practices identified")
    
    class Config:
        from_attributes = True


class AnalysisInsightsResponse(BaseModel):
    """Schema for analysis insights response."""
    
    resume_id: uuid.UUID = Field(..., description="Resume ID")
    insight_type: str = Field(..., description="Type of insights")
    
    # Content insights
    content_quality: Dict[str, Any] = Field(..., description="Content quality assessment")
    ats_compatibility: Dict[str, Any] = Field(..., description="ATS compatibility")
    keyword_optimization: Dict[str, Any] = Field(..., description="Keyword optimization")
    
    # Career insights
    career_progression: Optional[Dict[str, Any]] = Field(None, description="Career progression analysis")
    industry_alignment: Optional[Dict[str, Any]] = Field(None, description="Industry alignment")
    skill_gaps: Optional[List[str]] = Field(None, description="Identified skill gaps")
    
    # Improvement suggestions
    quick_wins: List[str] = Field(..., description="Quick improvement opportunities")
    long_term_goals: List[str] = Field(..., description="Long-term improvement goals")
    personalized_tips: List[str] = Field(..., description="Personalized tips")
    
    # Market insights
    market_trends: Optional[Dict[str, Any]] = Field(None, description="Market trends relevant to user")
    competitive_analysis: Optional[Dict[str, Any]] = Field(None, description="Competitive positioning")
    
    generated_at: datetime = Field(..., description="Insights generation timestamp")


class AnalysisTrendsResponse(BaseModel):
    """Schema for analysis trends response."""
    
    user_id: uuid.UUID = Field(..., description="User ID")
    time_period: str = Field(..., description="Time period")
    trend_type: str = Field(..., description="Type of trends")
    
    # Score trends
    score_trends: Dict[str, List[Dict[str, Any]]] = Field(..., description="Score trends over time")
    improvement_rate: float = Field(..., description="Overall improvement rate")
    
    # Activity trends
    analysis_frequency: Dict[str, int] = Field(..., description="Analysis frequency by period")
    most_improved_areas: List[str] = Field(..., description="Most improved areas")
    areas_needing_attention: List[str] = Field(..., description="Areas still needing work")
    
    # Progress metrics
    total_analyses: int = Field(..., description="Total analyses in period")
    average_score_improvement: float = Field(..., description="Average score improvement")
    consistency_score: float = Field(..., description="Consistency of improvements")
    
    # Insights
    trend_insights: List[str] = Field(..., description="Trend-based insights")
    recommendations: List[str] = Field(..., description="Trend-based recommendations")
    
    generated_at: datetime = Field(..., description="Trends generation timestamp")


class BatchAnalysisResponse(BaseModel):
    """Schema for batch analysis response."""
    
    batch_id: str = Field(..., description="Batch ID")
    requested_count: int = Field(..., description="Number of analyses requested")
    queued_count: int = Field(..., description="Number successfully queued")
    failed_count: int = Field(..., description="Number that failed to queue")
    
    # Task tracking
    task_ids: List[str] = Field(..., description="Celery task IDs")
    estimated_completion: Optional[datetime] = Field(None, description="Estimated completion time")
    
    # Individual results
    results: List[Dict[str, Any]] = Field(..., description="Individual analysis results")
    
    # Status
    batch_status: str = Field("processing", description="Overall batch status")
    created_at: datetime = Field(..., description="Batch creation time")


class AnalysisReportResponse(BaseModel):
    """Schema for analysis report response."""
    
    report_id: str = Field(..., description="Report ID")
    report_type: str = Field(..., description="Type of report")
    format: str = Field(..., description="Report format")
    
    # Report content
    report_data: Dict[str, Any] = Field(..., description="Report data")
    summary: Dict[str, Any] = Field(..., description="Executive summary")
    recommendations: List[str] = Field(..., description="Key recommendations")
    
    # Files
    download_url: Optional[str] = Field(None, description="Download URL")
    file_size: Optional[int] = Field(None, description="File size in bytes")
    
    # Metadata
    generated_at: datetime = Field(..., description="Report generation time")
    expires_at: Optional[datetime] = Field(None, description="Report expiration time")


# Specialized analysis schemas
class ATSAnalysisResponse(BaseModel):
    """Schema for ATS-specific analysis response."""
    
    ats_score: float = Field(..., ge=0, le=100, description="ATS compatibility score")
    
    # ATS factors
    keyword_density: float = Field(..., description="Keyword density score")
    format_compatibility: float = Field(..., description="Format compatibility score")
    section_organization: float = Field(..., description="Section organization score")
    
    # Specific issues
    format_issues: List[str] = Field(..., description="Format-related issues")
    missing_sections: List[str] = Field(..., description="Missing standard sections")
    keyword_gaps: List[str] = Field(..., description="Important missing keywords")
    
    # Recommendations
    ats_recommendations: List[str] = Field(..., description="ATS-specific recommendations")
    priority_fixes: List[str] = Field(..., description="High-priority fixes")
    
    class Config:
        from_attributes = True


class JobMatchAnalysisResponse(BaseModel):
    """Schema for job match analysis response."""
    
    overall_match_score: float = Field(..., ge=0, le=100, description="Overall match score")
    
    # Detailed scores
    skills_match_score: float = Field(..., ge=0, le=100, description="Skills match score")
    experience_match_score: float = Field(..., ge=0, le=100, description="Experience match score")
    education_match_score: float = Field(..., ge=0, le=100, description="Education match score")
    keyword_match_score: float = Field(..., ge=0, le=100, description="Keyword match score")
    
    # Match details
    matched_skills: List[str] = Field(..., description="Skills that match")
    missing_skills: List[str] = Field(..., description="Skills missing from resume")
    matched_keywords: List[str] = Field(..., description="Keywords that match")
    missing_keywords: List[str] = Field(..., description="Keywords missing from resume")
    
    # Experience analysis
    relevant_experience: List[str] = Field(..., description="Relevant experience found")
    experience_gaps: List[str] = Field(..., description="Experience gaps identified")
    
    # Recommendations
    improvement_suggestions: List[str] = Field(..., description="Specific improvement suggestions")
    keyword_recommendations: List[str] = Field(..., description="Keywords to add")
    
    # Match explanation
    match_explanation: str = Field(..., description="Detailed explanation of match assessment")
    confidence_level: float = Field(..., ge=0, le=1, description="Confidence in match assessment")
    
    class Config:
        from_attributes = True


# Search and filter schemas
class AnalysisSearchRequest(BaseModel):
    """Schema for analysis search request."""
    
    query: Optional[str] = Field(None, description="Search query")
    resume_ids: Optional[List[uuid.UUID]] = Field(None, description="Filter by resume IDs")
    analysis_types: Optional[List[str]] = Field(None, description="Filter by analysis types")
    min_score: Optional[float] = Field(None, ge=0, le=100, description="Minimum score filter")
    max_score: Optional[float] = Field(None, ge=0, le=100, description="Maximum score filter")
    status: Optional[ProcessingStatus] = Field(None, description="Filter by status")
    date_from: Optional[datetime] = Field(None, description="Filter from date")
    date_to: Optional[datetime] = Field(None, description="Filter to date")
    
    # Pagination
    page: int = Field(1, ge=1, description="Page number")
    page_size: int = Field(20, ge=1, le=100, description="Page size")
    sort_by: str = Field("created_at", description="Sort field")
    sort_order: str = Field("desc", regex="^(asc|desc)$", description="Sort order")


# Export all schemas
__all__ = [
    # Base schemas
    "AnalysisBase",
    
    # Request schemas
    "AnalysisRequest",
    "BatchAnalysisRequest",
    "AnalysisReportRequest",
    "AnalysisSearchRequest",
    
    # Response schemas
    "AnalysisResponse",
    "AnalysisListResponse",
    "AnalysisComparisonResponse",
    "AnalysisInsightsResponse",
    "AnalysisTrendsResponse",
    "BatchAnalysisResponse",
    "AnalysisReportResponse",
    
    # Specialized schemas
    "ATSAnalysisResponse",
    "JobMatchAnalysisResponse"
]