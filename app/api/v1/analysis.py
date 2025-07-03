"""
AI analysis API endpoints for resume analysis, job matching, and insights.
"""

import logging
from typing import List, Optional, Dict, Any
import uuid

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    get_db_session, get_current_verified_user, get_current_premium_user,
    get_pagination_params, PaginationParams, check_rate_limit, get_request_id
)
from app.exceptions import (
    ResumeNotFoundException, JobDescriptionNotFoundException, 
    AIServiceException, ValidationException
)
from app.models.user import User
from app.schemas.analysis import (
    AnalysisResponse, AnalysisListResponse, AnalysisComparisonResponse,
    AnalysisInsightsResponse, AnalysisTrendsResponse, BatchAnalysisRequest,
    BatchAnalysisResponse, AnalysisReportRequest, AnalysisReportResponse
)
from app.services.analysis_service import AnalysisService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/analysis", tags=["AI Analysis"])

# Initialize service
analysis_service = AnalysisService()


@router.post(
    "/resume/{resume_id}",
    response_model=AnalysisResponse,
    summary="Analyze resume",
    description="Perform comprehensive AI analysis of a resume"
)
async def analyze_resume(
    resume_id: uuid.UUID,
    analysis_type: str = Query("comprehensive", regex="^(comprehensive|quick|ats|content|keywords)$"),
    job_description_id: Optional[uuid.UUID] = Query(None, description="Job description for targeted analysis"),
    include_suggestions: bool = Query(True, description="Include improvement suggestions"),
    current_user: User = Depends(get_current_verified_user),
    session: AsyncSession = Depends(get_db_session),
    request_id: str = Depends(get_request_id),
    _: None = Depends(check_rate_limit)
) -> AnalysisResponse:
    """
    Perform AI analysis of a resume.
    
    - **resume_id**: Resume ID to analyze
    - **analysis_type**: Type of analysis (comprehensive, quick, ats, content, keywords)
    - **job_description_id**: Optional job description for targeted analysis
    - **include_suggestions**: Whether to include improvement suggestions
    
    Returns detailed analysis with scores, insights, and recommendations.
    Premium users get more detailed analysis and advanced features.
    """
    try:
        # Check premium requirements for advanced analysis
        if analysis_type == "comprehensive" and not current_user.is_premium:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail="Premium subscription required for comprehensive analysis"
            )
        
        analysis = await analysis_service.analyze_resume(
            session, resume_id, current_user.id, analysis_type, 
            job_description_id, include_suggestions
        )
        
        logger.info(f"Resume analysis completed: {resume_id} by user {current_user.id} - Request: {request_id}")
        return analysis
        
    except ResumeNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resume not found"
        )
    except JobDescriptionNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job description not found"
        )
    except AIServiceException as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Resume analysis failed: {resume_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Resume analysis failed"
        )


@router.post(
    "/job-match/{resume_id}/{job_id}",
    response_model=AnalysisResponse,
    summary="Analyze job match",
    description="Analyze compatibility between resume and job description"
)
async def analyze_job_match(
    resume_id: uuid.UUID,
    job_id: uuid.UUID,
    detailed_analysis: bool = Query(True, description="Include detailed matching analysis"),
    current_user: User = Depends(get_current_verified_user),
    session: AsyncSession = Depends(get_db_session),
    request_id: str = Depends(get_request_id),
    _: None = Depends(check_rate_limit)
) -> AnalysisResponse:
    """
    Analyze compatibility between resume and job description.
    
    - **resume_id**: Resume ID
    - **job_id**: Job description ID
    - **detailed_analysis**: Include detailed skill and experience matching
    
    Returns comprehensive match analysis with compatibility scores and recommendations.
    """
    try:
        analysis = await analysis_service.analyze_job_match(
            session, resume_id, job_id, current_user.id, detailed_analysis
        )
        
        logger.info(f"Job match analysis completed: resume {resume_id}, job {job_id} by user {current_user.id} - Request: {request_id}")
        return analysis
        
    except (ResumeNotFoundException, JobDescriptionNotFoundException) as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except AIServiceException as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Job match analysis failed: resume {resume_id}, job {job_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Job match analysis failed"
        )


@router.post(
    "/compare-resumes",
    response_model=AnalysisComparisonResponse,
    summary="Compare resumes",
    description="Compare multiple resumes and analyze differences"
)
async def compare_resumes(
    resume_ids: List[uuid.UUID] = Query(..., min_items=2, max_items=5),
    comparison_type: str = Query("comprehensive", regex="^(comprehensive|scores|content|skills)$"),
    current_user: User = Depends(get_current_premium_user),
    session: AsyncSession = Depends(get_db_session),
    request_id: str = Depends(get_request_id),
    _: None = Depends(check_rate_limit)
) -> AnalysisComparisonResponse:
    """
    Compare multiple resumes and analyze differences (Premium feature).
    
    - **resume_ids**: List of resume IDs to compare (2-5 resumes)
    - **comparison_type**: Type of comparison (comprehensive, scores, content, skills)
    
    Returns detailed comparison with relative strengths and recommendations.
    """
    try:
        comparison = await analysis_service.compare_resumes(
            session, resume_ids, current_user.id, comparison_type
        )
        
        logger.info(f"Resume comparison completed: {len(resume_ids)} resumes by user {current_user.id} - Request: {request_id}")
        return comparison
        
    except ResumeNotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except AIServiceException as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Resume comparison failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Resume comparison failed"
        )


@router.get(
    "/insights/{resume_id}",
    response_model=AnalysisInsightsResponse,
    summary="Get resume insights",
    description="Get AI-powered insights and recommendations for resume improvement"
)
async def get_resume_insights(
    resume_id: uuid.UUID,
    insight_type: str = Query("all", regex="^(all|skills|content|ats|industry|career)$"),
    current_user: User = Depends(get_current_verified_user),
    session: AsyncSession = Depends(get_db_session)
) -> AnalysisInsightsResponse:
    """
    Get AI-powered insights for resume improvement.
    
    - **resume_id**: Resume ID
    - **insight_type**: Type of insights (all, skills, content, ats, industry, career)
    
    Returns personalized insights and improvement recommendations.
    """
    try:
        insights = await analysis_service.get_resume_insights(
            session, resume_id, current_user.id, insight_type
        )
        
        return insights
        
    except ResumeNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resume not found"
        )
    except Exception as e:
        logger.error(f"Failed to get insights for resume {resume_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve insights"
        )


@router.get(
    "/trends",
    response_model=AnalysisTrendsResponse,
    summary="Get analysis trends",
    description="Get analysis trends and patterns for user's resumes"
)
async def get_analysis_trends(
    time_period: str = Query("3months", regex="^(1month|3months|6months|1year|all)$"),
    trend_type: str = Query("scores", regex="^(scores|skills|improvements|activity)$"),
    current_user: User = Depends(get_current_verified_user),
    session: AsyncSession = Depends(get_db_session)
) -> AnalysisTrendsResponse:
    """
    Get analysis trends and patterns.
    
    - **time_period**: Time period for trends (1month, 3months, 6months, 1year, all)
    - **trend_type**: Type of trends (scores, skills, improvements, activity)
    
    Returns trend analysis showing progress and patterns over time.
    """
    try:
        trends = await analysis_service.get_analysis_trends(
            session, current_user.id, time_period, trend_type
        )
        
        return trends
        
    except Exception as e:
        logger.error(f"Failed to get analysis trends for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve analysis trends"
        )


@router.post(
    "/batch",
    response_model=BatchAnalysisResponse,
    summary="Batch analysis",
    description="Analyze multiple resumes in batch (Premium feature)"
)
async def batch_analysis(
    batch_request: BatchAnalysisRequest,
    current_user: User = Depends(get_current_premium_user),
    session: AsyncSession = Depends(get_db_session),
    request_id: str = Depends(get_request_id),
    _: None = Depends(check_rate_limit)
) -> BatchAnalysisResponse:
    """
    Analyze multiple resumes in batch (Premium feature).
    
    - **resume_ids**: List of resume IDs to analyze
    - **analysis_type**: Type of analysis to perform
    - **job_description_id**: Optional job description for targeted analysis
    - **priority**: Analysis priority (normal, high)
    
    Returns batch analysis results with individual resume analyses.
    """
    try:
        batch_result = await analysis_service.batch_analysis(
            session, batch_request, current_user.id
        )
        
        logger.info(f"Batch analysis completed: {len(batch_request.resume_ids)} resumes by user {current_user.id} - Request: {request_id}")
        return batch_result
        
    except ValidationException as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )
    except AIServiceException as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Batch analysis failed for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Batch analysis failed"
        )


@router.get(
    "/history",
    response_model=AnalysisListResponse,
    summary="Get analysis history",
    description="Get user's analysis history with pagination"
)
async def get_analysis_history(
    resume_id: Optional[uuid.UUID] = Query(None, description="Filter by resume ID"),
    analysis_type: Optional[str] = Query(None, description="Filter by analysis type"),
    job_id: Optional[uuid.UUID] = Query(None, description="Filter by job description ID"),
    pagination: PaginationParams = Depends(get_pagination_params),
    current_user: User = Depends(get_current_verified_user),
    session: AsyncSession = Depends(get_db_session)
) -> AnalysisListResponse:
    """
    Get user's analysis history with filtering.
    
    - **resume_id**: Filter by specific resume
    - **analysis_type**: Filter by analysis type
    - **job_id**: Filter by job description
    - **page**: Page number
    - **page_size**: Items per page
    
    Returns paginated list of analyses ordered by date (newest first).
    """
    try:
        filters = {
            "resume_id": resume_id,
            "analysis_type": analysis_type,
            "job_id": job_id
        }
        
        analyses, total_count = await analysis_service.get_analysis_history(
            session, current_user.id, pagination, filters
        )
        
        total_pages = (total_count + pagination.page_size - 1) // pagination.page_size
        
        return AnalysisListResponse(
            analyses=analyses,
            total_count=total_count,
            page=pagination.page,
            page_size=pagination.page_size,
            total_pages=total_pages
        )
        
    except Exception as e:
        logger.error(f"Failed to get analysis history for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve analysis history"
        )


@router.post(
    "/report",
    response_model=AnalysisReportResponse,
    summary="Generate analysis report",
    description="Generate comprehensive analysis report (Premium feature)"
)
async def generate_analysis_report(
    report_request: AnalysisReportRequest,
    current_user: User = Depends(get_current_premium_user),
    session: AsyncSession = Depends(get_db_session),
    request_id: str = Depends(get_request_id),
    _: None = Depends(check_rate_limit)
) -> AnalysisReportResponse:
    """
    Generate comprehensive analysis report (Premium feature).
    
    - **resume_ids**: Resumes to include in report
    - **report_type**: Type of report (individual, comparative, portfolio)
    - **include_trends**: Include trend analysis
    - **include_recommendations**: Include improvement recommendations
    - **format**: Report format (pdf, html, json)
    
    Returns comprehensive report with analysis data and insights.
    """
    try:
        report = await analysis_service.generate_analysis_report(
            session, report_request, current_user.id
        )
        
        logger.info(f"Analysis report generated by user {current_user.id} - Request: {request_id}")
        return report
        
    except ValidationException as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Report generation failed for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Report generation failed"
        )


@router.get(
    "/stats",
    response_model=Dict[str, Any],
    summary="Get analysis statistics",
    description="Get comprehensive analysis statistics for user"
)
async def get_analysis_stats(
    current_user: User = Depends(get_current_verified_user),
    session: AsyncSession = Depends(get_db_session)
) -> Dict[str, Any]:
    """
    Get comprehensive analysis statistics.
    
    Returns detailed statistics about user's analysis activity and progress.
    """
    try:
        stats = await analysis_service.get_analysis_stats(session, current_user.id)
        return stats
        
    except Exception as e:
        logger.error(f"Failed to get analysis stats for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve analysis statistics"
        )


@router.delete(
    "/{analysis_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete analysis",
    description="Delete an analysis record"
)
async def delete_analysis(
    analysis_id: uuid.UUID,
    current_user: User = Depends(get_current_verified_user),
    session: AsyncSession = Depends(get_db_session),
    request_id: str = Depends(get_request_id)
):
    """
    Delete an analysis record.
    
    - **analysis_id**: Analysis ID to delete
    
    This will permanently delete the analysis record and results.
    """
    try:
        success = await analysis_service.delete_analysis(
            session, analysis_id, current_user.id
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Analysis not found"
            )
        
        logger.info(f"Analysis deleted: {analysis_id} by user {current_user.id} - Request: {request_id}")
        
    except Exception as e:
        logger.error(f"Analysis deletion failed: {analysis_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Analysis deletion failed"
        )


@router.get(
    "/ai-service/status",
    response_model=Dict[str, Any],
    summary="Get AI service status",
    description="Get current status and capabilities of AI analysis services"
)
async def get_ai_service_status(
    current_user: User = Depends(get_current_verified_user)
) -> Dict[str, Any]:
    """
    Get AI service status and capabilities.
    
    Returns information about available AI services and their current status.
    """
    try:
        status_info = await analysis_service.get_ai_service_status()
        return status_info
        
    except Exception as e:
        logger.error(f"Failed to get AI service status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve AI service status"
        )