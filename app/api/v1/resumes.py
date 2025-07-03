"""
Resume API endpoints for CRUD operations, analysis, and optimization.
"""

import logging
from typing import List, Optional
import uuid

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.api.deps import (
    get_db_session, get_current_verified_user, get_pagination_params,
    PaginationParams, check_rate_limit, get_request_id
)
from app.exceptions import (
    ResumeNotFoundException, ResumeQuotaExceededException, FileProcessingException,
    ValidationException, AIServiceException
)
from app.models.user import User
from app.models.resume import ResumeStatus, ResumeType
from app.schemas.resume import (
    ResumeResponse, ResumeListResponse, ResumeCreateRequest, ResumeUpdateRequest,
    ResumeAnalysisResponse, ResumeOptimizationRequest, ResumeUploadResponse,
    ResumeSectionResponse, ResumeStatsResponse
)
from app.services.resume_service import ResumeService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/resumes", tags=["Resumes"])

# Initialize service
resume_service = ResumeService()


@router.post(
    "/",
    response_model=ResumeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create new resume",
    description="Create a new empty resume"
)
async def create_resume(
    resume_data: ResumeCreateRequest,
    current_user: User = Depends(get_current_verified_user),
    session: AsyncSession = Depends(get_db_session),
    request_id: str = Depends(get_request_id),
    _: None = Depends(check_rate_limit)
) -> ResumeResponse:
    """
    Create a new empty resume.
    
    - **title**: Resume title/name
    - **description**: Optional description
    
    Returns the created resume with default sections.
    """
    try:
        resume = await resume_service.create_resume(
            session,
            current_user.id,
            resume_data.title,
            resume_data.description
        )
        
        logger.info(f"Resume created: {resume.id} by user {current_user.id} - Request: {request_id}")
        return ResumeResponse.from_orm(resume)
        
    except ResumeQuotaExceededException as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except ValidationException as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Resume creation failed for user {current_user.id}: {e} - Request: {request_id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Resume creation failed. Please try again."
        )


@router.post(
    "/upload",
    response_model=ResumeUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload resume file",
    description="Upload and parse a resume file (PDF, DOCX, DOC)"
)
async def upload_resume(
    file: UploadFile = File(..., description="Resume file to upload"),
    title: str = Form(..., description="Resume title"),
    description: Optional[str] = Form(None, description="Resume description"),
    current_user: User = Depends(get_current_verified_user),
    session: AsyncSession = Depends(get_db_session),
    request_id: str = Depends(get_request_id),
    _: None = Depends(check_rate_limit)
) -> ResumeUploadResponse:
    """
    Upload and parse a resume file.
    
    - **file**: Resume file (PDF, DOCX, DOC formats supported)
    - **title**: Resume title/name
    - **description**: Optional description
    
    The file will be processed and parsed automatically.
    Analysis will be triggered in the background.
    """
    try:
        resume = await resume_service.upload_resume(
            session,
            current_user.id,
            file,
            title,
            description
        )
        
        logger.info(f"Resume uploaded: {resume.id} by user {current_user.id} - Request: {request_id}")
        return ResumeUploadResponse(
            **ResumeResponse.from_orm(resume).dict(),
            parsing_status="completed" if resume.status == ResumeStatus.COMPLETED else "processing",
            analysis_queued=True
        )
        
    except ResumeQuotaExceededException as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except FileProcessingException as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Resume upload failed for user {current_user.id}: {e} - Request: {request_id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Resume upload failed. Please try again."
        )


@router.get(
    "/",
    response_model=ResumeListResponse,
    summary="Get user resumes",
    description="Get list of user's resumes with pagination and filtering"
)
async def get_resumes(
    status: Optional[ResumeStatus] = Query(None, description="Filter by status"),
    resume_type: Optional[ResumeType] = Query(None, description="Filter by type"),
    pagination: PaginationParams = Depends(get_pagination_params),
    current_user: User = Depends(get_current_verified_user),
    session: AsyncSession = Depends(get_db_session)
) -> ResumeListResponse:
    """
    Get user's resumes with pagination and filtering.
    
    - **status**: Filter by resume status (draft, processing, completed, error)
    - **resume_type**: Filter by resume type (original, optimized, etc.)
    - **page**: Page number (default: 1)
    - **page_size**: Items per page (default: 20, max: 100)
    - **sort_by**: Sort field (default: created_at)
    - **sort_order**: Sort order (asc/desc, default: desc)
    
    Returns paginated list of resumes.
    """
    try:
        resumes, total_count = await resume_service.get_user_resumes(
            session,
            current_user.id,
            pagination.limit,
            pagination.offset,
            status,
            resume_type
        )
        
        total_pages = (total_count + pagination.page_size - 1) // pagination.page_size
        
        return ResumeListResponse(
            resumes=[ResumeResponse.from_orm(resume) for resume in resumes],
            total_count=total_count,
            page=pagination.page,
            page_size=pagination.page_size,
            total_pages=total_pages
        )
        
    except Exception as e:
        logger.error(f"Failed to get resumes for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve resumes"
        )


@router.get(
    "/{resume_id}",
    response_model=ResumeResponse,
    summary="Get resume details",
    description="Get detailed resume information including sections"
)
async def get_resume(
    resume_id: uuid.UUID,
    current_user: User = Depends(get_current_verified_user),
    session: AsyncSession = Depends(get_db_session)
) -> ResumeResponse:
    """
    Get detailed resume information.
    
    - **resume_id**: Resume ID
    
    Returns complete resume data including all sections.
    """
    try:
        resume = await resume_service.get_resume(session, resume_id, current_user.id)
        return ResumeResponse.from_orm(resume)
        
    except ResumeNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resume not found"
        )
    except Exception as e:
        logger.error(f"Failed to get resume {resume_id} for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve resume"
        )


@router.put(
    "/{resume_id}",
    response_model=ResumeResponse,
    summary="Update resume",
    description="Update resume information and sections"
)
async def update_resume(
    resume_id: uuid.UUID,
    resume_data: ResumeUpdateRequest,
    current_user: User = Depends(get_current_verified_user),
    session: AsyncSession = Depends(get_db_session),
    request_id: str = Depends(get_request_id)
) -> ResumeResponse:
    """
    Update resume information and sections.
    
    - **resume_id**: Resume ID
    - **title**: New title (optional)
    - **description**: New description (optional)
    - **sections**: Updated sections data (optional)
    
    Returns updated resume data.
    """
    try:
        resume = await resume_service.update_resume(
            session,
            resume_id,
            current_user.id,
            resume_data.title,
            resume_data.description,
            resume_data.sections
        )
        
        logger.info(f"Resume updated: {resume_id} by user {current_user.id} - Request: {request_id}")
        return ResumeResponse.from_orm(resume)
        
    except ResumeNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resume not found"
        )
    except ValidationException as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Resume update failed: {resume_id}, user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Resume update failed"
        )


@router.delete(
    "/{resume_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete resume",
    description="Delete resume (soft delete by default)"
)
async def delete_resume(
    resume_id: uuid.UUID,
    hard_delete: bool = Query(False, description="Permanently delete the resume"),
    current_user: User = Depends(get_current_verified_user),
    session: AsyncSession = Depends(get_db_session),
    request_id: str = Depends(get_request_id)
):
    """
    Delete resume.
    
    - **resume_id**: Resume ID
    - **hard_delete**: If true, permanently delete; otherwise soft delete
    
    Soft delete allows recovery, hard delete is permanent.
    """
    try:
        success = await resume_service.delete_resume(
            session,
            resume_id,
            current_user.id,
            hard_delete
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Resume deletion failed"
            )
        
        logger.info(f"Resume deleted: {resume_id} by user {current_user.id} (hard={hard_delete}) - Request: {request_id}")
        
    except ResumeNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resume not found"
        )
    except Exception as e:
        logger.error(f"Resume deletion failed: {resume_id}, user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Resume deletion failed"
        )


@router.post(
    "/{resume_id}/analyze",
    response_model=ResumeAnalysisResponse,
    summary="Analyze resume",
    description="Analyze resume with AI for insights and recommendations"
)
async def analyze_resume(
    resume_id: uuid.UUID,
    job_description_id: Optional[uuid.UUID] = Query(None, description="Job description ID for targeted analysis"),
    analysis_type: str = Query("general", description="Type of analysis (general, job_match, ats_check)"),
    current_user: User = Depends(get_current_verified_user),
    session: AsyncSession = Depends(get_db_session),
    request_id: str = Depends(get_request_id),
    _: None = Depends(check_rate_limit)
) -> ResumeAnalysisResponse:
    """
    Analyze resume with AI.
    
    - **resume_id**: Resume ID to analyze
    - **job_description_id**: Optional job description for targeted analysis
    - **analysis_type**: Type of analysis (general, job_match, ats_check)
    
    Returns comprehensive analysis with scores and recommendations.
    Premium users get more detailed analysis.
    """
    try:
        # Check if user can perform analysis
        if not current_user.is_premium and analysis_type != "general":
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail="Premium subscription required for advanced analysis"
            )
        
        analysis = await resume_service.analyze_resume(
            session,
            resume_id,
            current_user.id,
            job_description_id,
            analysis_type
        )
        
        logger.info(f"Resume analysis completed: {resume_id} by user {current_user.id} - Request: {request_id}")
        return ResumeAnalysisResponse.from_orm(analysis)
        
    except ResumeNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resume not found"
        )
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
        logger.error(f"Resume analysis failed: {resume_id}, user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Resume analysis failed. Please try again."
        )


@router.post(
    "/{resume_id}/optimize",
    response_model=ResumeResponse,
    summary="Optimize resume",
    description="Optimize resume for specific job description using AI"
)
async def optimize_resume(
    resume_id: uuid.UUID,
    optimization_data: ResumeOptimizationRequest,
    current_user: User = Depends(get_current_verified_user),
    session: AsyncSession = Depends(get_db_session),
    request_id: str = Depends(get_request_id),
    _: None = Depends(check_rate_limit)
) -> ResumeResponse:
    """
    Optimize resume for specific job description.
    
    - **resume_id**: Resume ID to optimize
    - **job_description_id**: Target job description ID
    - **optimization_type**: Type of optimization (full, keywords, format)
    
    Creates a new optimized version of the resume.
    Requires premium subscription.
    """
    try:
        # Check premium requirement
        if not current_user.is_premium:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail="Premium subscription required for resume optimization"
            )
        
        optimized_resume = await resume_service.optimize_resume(
            session,
            resume_id,
            current_user.id,
            optimization_data.job_description_id,
            optimization_data.optimization_type
        )
        
        logger.info(f"Resume optimized: {resume_id} -> {optimized_resume.id} by user {current_user.id} - Request: {request_id}")
        return ResumeResponse.from_orm(optimized_resume)
        
    except ResumeNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resume not found"
        )
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
        logger.error(f"Resume optimization failed: {resume_id}, user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Resume optimization failed. Please try again."
        )


@router.get(
    "/{resume_id}/sections",
    response_model=List[ResumeSectionResponse],
    summary="Get resume sections",
    description="Get all sections of a resume"
)
async def get_resume_sections(
    resume_id: uuid.UUID,
    current_user: User = Depends(get_current_verified_user),
    session: AsyncSession = Depends(get_db_session)
) -> List[ResumeSectionResponse]:
    """
    Get all sections of a resume.
    
    - **resume_id**: Resume ID
    
    Returns list of resume sections in display order.
    """
    try:
        resume = await resume_service.get_resume(session, resume_id, current_user.id)
        
        # Sort sections by order_index
        sorted_sections = sorted(resume.sections, key=lambda s: s.order_index)
        
        return [ResumeSectionResponse.from_orm(section) for section in sorted_sections]
        
    except ResumeNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resume not found"
        )
    except Exception as e:
        logger.error(f"Failed to get resume sections: {resume_id}, user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve resume sections"
        )


@router.get(
    "/{resume_id}/analyses",
    response_model=List[ResumeAnalysisResponse],
    summary="Get resume analyses",
    description="Get all analyses performed on a resume"
)
async def get_resume_analyses(
    resume_id: uuid.UUID,
    limit: int = Query(10, ge=1, le=50, description="Number of analyses to return"),
    current_user: User = Depends(get_current_verified_user),
    session: AsyncSession = Depends(get_db_session)
) -> List[ResumeAnalysisResponse]:
    """
    Get analyses performed on a resume.
    
    - **resume_id**: Resume ID
    - **limit**: Maximum number of analyses to return
    
    Returns list of analyses ordered by creation date (newest first).
    """
    try:
        resume = await resume_service.get_resume(session, resume_id, current_user.id)
        
        # Sort analyses by creation date (newest first) and limit
        sorted_analyses = sorted(resume.analyses, key=lambda a: a.created_at, reverse=True)[:limit]
        
        return [ResumeAnalysisResponse.from_orm(analysis) for analysis in sorted_analyses]
        
    except ResumeNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resume not found"
        )
    except Exception as e:
        logger.error(f"Failed to get resume analyses: {resume_id}, user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve resume analyses"
        )


@router.get(
    "/stats",
    response_model=ResumeStatsResponse,
    summary="Get resume statistics",
    description="Get user's resume statistics and insights"
)
async def get_resume_stats(
    current_user: User = Depends(get_current_verified_user),
    session: AsyncSession = Depends(get_db_session)
) -> ResumeStatsResponse:
    """
    Get user's resume statistics.
    
    Returns comprehensive statistics about user's resumes and activities.
    """
    try:
        from sqlalchemy import func, desc
        from app.models.resume import Resume, ResumeAnalysis
        
        # Get resume counts by status
        resume_counts = await session.execute(
            select(Resume.status, func.count(Resume.id))
            .where(Resume.user_id == current_user.id)
            .group_by(Resume.status)
        )
        status_counts = {status.value: 0 for status in ResumeStatus}
        for status, count in resume_counts:
            status_counts[status.value] = count
        
        # Get total resumes
        total_resumes = sum(status_counts.values())
        
        # Get analysis counts
        analysis_count = await session.execute(
            select(func.count(ResumeAnalysis.id))
            .join(Resume, ResumeAnalysis.resume_id == Resume.id)
            .where(Resume.user_id == current_user.id)
        )
        total_analyses = analysis_count.scalar()
        
        # Get latest analysis score
        latest_analysis = await session.execute(
            select(ResumeAnalysis.overall_score)
            .join(Resume, ResumeAnalysis.resume_id == Resume.id)
            .where(Resume.user_id == current_user.id)
            .order_by(desc(ResumeAnalysis.created_at))
            .limit(1)
        )
        latest_score = latest_analysis.scalar()
        
        # Get average score
        avg_score = await session.execute(
            select(func.avg(ResumeAnalysis.overall_score))
            .join(Resume, ResumeAnalysis.resume_id == Resume.id)
            .where(Resume.user_id == current_user.id)
        )
        average_score = avg_score.scalar()
        
        return ResumeStatsResponse(
            total_resumes=total_resumes,
            status_counts=status_counts,
            total_analyses=total_analyses,
            latest_analysis_score=latest_score,
            average_analysis_score=float(average_score) if average_score else None,
            can_create_more=current_user.can_create_resume(),
            max_resumes_allowed=3 if not current_user.is_premium else 50
        )
        
    except Exception as e:
        logger.error(f"Failed to get resume stats for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve resume statistics"
        )