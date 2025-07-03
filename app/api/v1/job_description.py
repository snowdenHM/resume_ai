"""
Job description API endpoints for CRUD operations and job matching.
"""

import logging
from typing import List, Optional
import uuid

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    get_db_session, get_current_verified_user, get_pagination_params,
    PaginationParams, check_rate_limit, get_request_id
)
from app.exceptions import (
    JobDescriptionNotFoundException, ValidationException, AIServiceException
)
from app.models.user import User
from app.models.job_description import JobStatus, JobType, ExperienceLevel, RemoteType
from app.schemas.job_description import (
    JobDescriptionResponse, JobDescriptionListResponse, JobDescriptionCreateRequest,
    JobDescriptionUpdateRequest, JobMatchResponse, JobAnalysisResponse,
    JobSearchRequest, JobStatsResponse
)
from app.services.job_description_service import JobDescriptionService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/jobs", tags=["Job Descriptions"])

# Initialize service
job_service = JobDescriptionService()


@router.post(
    "/",
    response_model=JobDescriptionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create job description",
    description="Create a new job description for resume matching"
)
async def create_job_description(
    job_data: JobDescriptionCreateRequest,
    current_user: User = Depends(get_current_verified_user),
    session: AsyncSession = Depends(get_db_session),
    request_id: str = Depends(get_request_id),
    _: None = Depends(check_rate_limit)
) -> JobDescriptionResponse:
    """
    Create a new job description.
    
    - **title**: Job title
    - **company**: Company name
    - **location**: Job location
    - **job_type**: Employment type (full_time, part_time, contract, etc.)
    - **experience_level**: Required experience level
    - **remote_type**: Remote work type (on_site, remote, hybrid)
    - **industry**: Industry sector
    - **description**: Full job description
    - **requirements**: Job requirements list
    - **responsibilities**: Job responsibilities list
    - **salary_min/max**: Salary range (optional)
    - **application_url**: Application URL (optional)
    
    Returns the created job description with extracted requirements.
    """
    try:
        job_description = await job_service.create_job_description(
            session, current_user.id, job_data
        )
        
        logger.info(f"Job description created: {job_description.id} by user {current_user.id} - Request: {request_id}")
        return JobDescriptionResponse.from_orm(job_description)
        
    except ValidationException as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Job description creation failed for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Job description creation failed"
        )


@router.get(
    "/",
    response_model=JobDescriptionListResponse,
    summary="Get job descriptions",
    description="Get user's job descriptions with pagination and filtering"
)
async def get_job_descriptions(
    status: Optional[JobStatus] = Query(None, description="Filter by job status"),
    job_type: Optional[JobType] = Query(None, description="Filter by job type"),
    experience_level: Optional[ExperienceLevel] = Query(None, description="Filter by experience level"),
    remote_type: Optional[RemoteType] = Query(None, description="Filter by remote type"),
    industry: Optional[str] = Query(None, description="Filter by industry"),
    company: Optional[str] = Query(None, description="Filter by company"),
    location: Optional[str] = Query(None, description="Filter by location"),
    pagination: PaginationParams = Depends(get_pagination_params),
    current_user: User = Depends(get_current_verified_user),
    session: AsyncSession = Depends(get_db_session)
) -> JobDescriptionListResponse:
    """
    Get user's job descriptions with filtering.
    
    - **status**: Filter by job status
    - **job_type**: Filter by employment type
    - **experience_level**: Filter by experience level
    - **remote_type**: Filter by remote work type
    - **industry**: Filter by industry
    - **company**: Filter by company name
    - **location**: Filter by location
    - **page**: Page number
    - **page_size**: Items per page
    
    Returns paginated list of job descriptions.
    """
    try:
        filters = {
            "status": status,
            "job_type": job_type,
            "experience_level": experience_level,
            "remote_type": remote_type,
            "industry": industry,
            "company": company,
            "location": location
        }
        
        jobs, total_count = await job_service.get_user_job_descriptions(
            session, current_user.id, pagination, filters
        )
        
        total_pages = (total_count + pagination.page_size - 1) // pagination.page_size
        
        return JobDescriptionListResponse(
            jobs=[JobDescriptionResponse.from_orm(job) for job in jobs],
            total_count=total_count,
            page=pagination.page,
            page_size=pagination.page_size,
            total_pages=total_pages
        )
        
    except Exception as e:
        logger.error(f"Failed to get job descriptions for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve job descriptions"
        )


@router.get(
    "/{job_id}",
    response_model=JobDescriptionResponse,
    summary="Get job description",
    description="Get detailed job description information"
)
async def get_job_description(
    job_id: uuid.UUID,
    current_user: User = Depends(get_current_verified_user),
    session: AsyncSession = Depends(get_db_session)
) -> JobDescriptionResponse:
    """
    Get detailed job description information.
    
    - **job_id**: Job description ID
    
    Returns complete job description data.
    """
    try:
        job_description = await job_service.get_job_description(
            session, job_id, current_user.id
        )
        
        # Increment view count
        job_description.increment_view_count()
        await session.commit()
        
        return JobDescriptionResponse.from_orm(job_description)
        
    except JobDescriptionNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job description not found"
        )
    except Exception as e:
        logger.error(f"Failed to get job description {job_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve job description"
        )


@router.put(
    "/{job_id}",
    response_model=JobDescriptionResponse,
    summary="Update job description",
    description="Update job description information"
)
async def update_job_description(
    job_id: uuid.UUID,
    job_data: JobDescriptionUpdateRequest,
    current_user: User = Depends(get_current_verified_user),
    session: AsyncSession = Depends(get_db_session),
    request_id: str = Depends(get_request_id)
) -> JobDescriptionResponse:
    """
    Update job description information.
    
    - **job_id**: Job description ID
    - All fields are optional for partial updates
    
    Returns updated job description.
    """
    try:
        job_description = await job_service.update_job_description(
            session, job_id, current_user.id, job_data
        )
        
        logger.info(f"Job description updated: {job_id} by user {current_user.id} - Request: {request_id}")
        return JobDescriptionResponse.from_orm(job_description)
        
    except JobDescriptionNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job description not found"
        )
    except ValidationException as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Job description update failed: {job_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Job description update failed"
        )


@router.delete(
    "/{job_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete job description",
    description="Delete job description"
)
async def delete_job_description(
    job_id: uuid.UUID,
    hard_delete: bool = Query(False, description="Permanently delete the job description"),
    current_user: User = Depends(get_current_verified_user),
    session: AsyncSession = Depends(get_db_session),
    request_id: str = Depends(get_request_id)
):
    """
    Delete job description.
    
    - **job_id**: Job description ID
    - **hard_delete**: If true, permanently delete; otherwise soft delete
    
    Soft delete allows recovery, hard delete is permanent.
    """
    try:
        success = await job_service.delete_job_description(
            session, job_id, current_user.id, hard_delete
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Job description deletion failed"
            )
        
        logger.info(f"Job description deleted: {job_id} by user {current_user.id} (hard={hard_delete}) - Request: {request_id}")
        
    except JobDescriptionNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job description not found"
        )
    except Exception as e:
        logger.error(f"Job description deletion failed: {job_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Job description deletion failed"
        )


@router.post(
    "/{job_id}/analyze",
    response_model=JobAnalysisResponse,
    summary="Analyze job description",
    description="Analyze job description to extract requirements and insights"
)
async def analyze_job_description(
    job_id: uuid.UUID,
    current_user: User = Depends(get_current_verified_user),
    session: AsyncSession = Depends(get_db_session),
    request_id: str = Depends(get_request_id),
    _: None = Depends(check_rate_limit)
) -> JobAnalysisResponse:
    """
    Analyze job description with AI to extract structured requirements.
    
    - **job_id**: Job description ID to analyze
    
    Returns extracted requirements, skills, keywords, and insights.
    """
    try:
        analysis = await job_service.analyze_job_description(
            session, job_id, current_user.id
        )
        
        logger.info(f"Job description analyzed: {job_id} by user {current_user.id} - Request: {request_id}")
        return analysis
        
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
        logger.error(f"Job description analysis failed: {job_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Job description analysis failed"
        )


@router.post(
    "/{job_id}/match",
    response_model=List[JobMatchResponse],
    summary="Match resumes to job",
    description="Find and rank user's resumes by compatibility with job description"
)
async def match_resumes_to_job(
    job_id: uuid.UUID,
    min_score: float = Query(0, ge=0, le=100, description="Minimum match score"),
    limit: int = Query(10, ge=1, le=50, description="Maximum number of matches"),
    current_user: User = Depends(get_current_verified_user),
    session: AsyncSession = Depends(get_db_session),
    request_id: str = Depends(get_request_id),
    _: None = Depends(check_rate_limit)
) -> List[JobMatchResponse]:
    """
    Match user's resumes to job description.
    
    - **job_id**: Job description ID
    - **min_score**: Minimum compatibility score (0-100)
    - **limit**: Maximum number of matches to return
    
    Returns ranked list of resume matches with compatibility scores.
    Premium users get more detailed matching analysis.
    """
    try:
        matches = await job_service.match_resumes_to_job(
            session, job_id, current_user.id, min_score, limit
        )
        
        logger.info(f"Resume matching completed: {job_id} by user {current_user.id} - Request: {request_id}")
        return [JobMatchResponse.from_orm(match) for match in matches]
        
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
        logger.error(f"Resume matching failed: {job_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Resume matching failed"
        )


@router.post(
    "/search",
    response_model=JobDescriptionListResponse,
    summary="Search job descriptions",
    description="Search job descriptions with advanced filtering"
)
async def search_job_descriptions(
    search_params: JobSearchRequest,
    current_user: User = Depends(get_current_verified_user),
    session: AsyncSession = Depends(get_db_session)
) -> JobDescriptionListResponse:
    """
    Search job descriptions with advanced filtering.
    
    - **query**: Text search query
    - **skills**: Required skills filter
    - **keywords**: Keywords filter
    - **salary_min/max**: Salary range filter
    - **location**: Location filter
    - **company**: Company filter
    - **industry**: Industry filter
    - **job_type**: Employment type filter
    - **experience_level**: Experience level filter
    - **remote_type**: Remote work type filter
    - **posted_after**: Posted date filter
    
    Returns matching job descriptions ranked by relevance.
    """
    try:
        jobs, total_count = await job_service.search_job_descriptions(
            session, current_user.id, search_params
        )
        
        total_pages = (total_count + search_params.page_size - 1) // search_params.page_size
        
        return JobDescriptionListResponse(
            jobs=[JobDescriptionResponse.from_orm(job) for job in jobs],
            total_count=total_count,
            page=search_params.page,
            page_size=search_params.page_size,
            total_pages=total_pages
        )
        
    except Exception as e:
        logger.error(f"Job search failed for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Job search failed"
        )


@router.get(
    "/stats",
    response_model=JobStatsResponse,
    summary="Get job statistics",
    description="Get user's job description statistics and insights"
)
async def get_job_stats(
    current_user: User = Depends(get_current_verified_user),
    session: AsyncSession = Depends(get_db_session)
) -> JobStatsResponse:
    """
    Get user's job description statistics.
    
    Returns comprehensive statistics about saved jobs and matching activity.
    """
    try:
        stats = await job_service.get_job_stats(session, current_user.id)
        return stats
        
    except Exception as e:
        logger.error(f"Failed to get job stats for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve job statistics"
        )


@router.post(
    "/import",
    response_model=JobDescriptionResponse,
    summary="Import job from URL",
    description="Import job description from job board URL"
)
async def import_job_from_url(
    job_url: str = Query(..., description="Job posting URL"),
    current_user: User = Depends(get_current_verified_user),
    session: AsyncSession = Depends(get_db_session),
    request_id: str = Depends(get_request_id),
    _: None = Depends(check_rate_limit)
) -> JobDescriptionResponse:
    """
    Import job description from job board URL.
    
    - **job_url**: URL of job posting (LinkedIn, Indeed, company website, etc.)
    
    Automatically extracts job information from the URL.
    Premium feature with enhanced extraction capabilities.
    """
    try:
        if not current_user.is_premium:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail="Premium subscription required for job URL import"
            )
        
        job_description = await job_service.import_job_from_url(
            session, current_user.id, job_url
        )
        
        logger.info(f"Job imported from URL: {job_url} by user {current_user.id} - Request: {request_id}")
        return JobDescriptionResponse.from_orm(job_description)
        
    except ValidationException as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Job import failed for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Job import failed"
        )


@router.get(
    "/{job_id}/matches",
    response_model=List[JobMatchResponse],
    summary="Get job matches",
    description="Get existing resume matches for a job description"
)
async def get_job_matches(
    job_id: uuid.UUID,
    current_user: User = Depends(get_current_verified_user),
    session: AsyncSession = Depends(get_db_session)
) -> List[JobMatchResponse]:
    """
    Get existing resume matches for a job description.
    
    - **job_id**: Job description ID
    
    Returns previously calculated resume matches for this job.
    """
    try:
        matches = await job_service.get_job_matches(
            session, job_id, current_user.id
        )
        
        return [JobMatchResponse.from_orm(match) for match in matches]
        
    except JobDescriptionNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job description not found"
        )
    except Exception as e:
        logger.error(f"Failed to get job matches: {job_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve job matches"
        )