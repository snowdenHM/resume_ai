"""
Resume export API endpoints for generating and downloading resume files.
"""

import logging
from typing import List, Optional
import uuid

from fastapi import APIRouter, Depends, HTTPException, status, Query, Response
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    get_db_session, get_current_verified_user, get_pagination_params,
    PaginationParams, check_rate_limit, get_request_id
)
from app.exceptions import (
    ResumeNotFoundException, ExportFailedException, UnsupportedExportFormatException,
    ValidationException
)
from app.models.user import User
from app.models.resume import ProcessingStatus
from app.schemas.resume import (
    ResumeExportRequest, ResumeExportResponse, ResumeExportListResponse
)
from app.services.export_service import ExportService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/export", tags=["Resume Export"])

# Initialize service
export_service = ExportService()


@router.post(
    "/resumes/{resume_id}",
    response_model=ResumeExportResponse,
    summary="Export resume",
    description="Generate resume export in specified format"
)
async def export_resume(
    resume_id: uuid.UUID,
    export_data: ResumeExportRequest,
    current_user: User = Depends(get_current_verified_user),
    session: AsyncSession = Depends(get_db_session),
    request_id: str = Depends(get_request_id),
    _: None = Depends(check_rate_limit)
) -> ResumeExportResponse:
    """
    Generate resume export in specified format.
    
    - **resume_id**: Resume ID to export
    - **export_format**: Export format (pdf, docx, json, html)
    - **template_id**: Template to use for export (optional)
    - **export_settings**: Export configuration (optional)
    
    Returns export information with download URL when ready.
    The export is processed in background for larger files.
    """
    try:
        export_record = await export_service.create_export(
            session, resume_id, current_user.id, export_data
        )
        
        logger.info(f"Export created: {export_record.id} for resume {resume_id} by user {current_user.id} - Request: {request_id}")
        return ResumeExportResponse.from_orm(export_record)
        
    except ResumeNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resume not found"
        )
    except UnsupportedExportFormatException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except ValidationException as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Export creation failed: resume {resume_id}, user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Export creation failed"
        )


@router.get(
    "/status/{export_id}",
    response_model=ResumeExportResponse,
    summary="Get export status",
    description="Check the status of a resume export"
)
async def get_export_status(
    export_id: uuid.UUID,
    current_user: User = Depends(get_current_verified_user),
    session: AsyncSession = Depends(get_db_session)
) -> ResumeExportResponse:
    """
    Check the status of a resume export.
    
    - **export_id**: Export ID
    
    Returns current export status and download information if ready.
    """
    try:
        export_record = await export_service.get_export(
            session, export_id, current_user.id
        )
        
        return ResumeExportResponse.from_orm(export_record)
        
    except ResumeNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Export not found"
        )
    except Exception as e:
        logger.error(f"Failed to get export status: {export_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve export status"
        )


@router.get(
    "/download/{export_id}",
    summary="Download exported resume",
    description="Download the exported resume file"
)
async def download_export(
    export_id: uuid.UUID,
    current_user: User = Depends(get_current_verified_user),
    session: AsyncSession = Depends(get_db_session)
):
    """
    Download the exported resume file.
    
    - **export_id**: Export ID
    
    Returns the file for download if export is completed.
    Increments download count for tracking.
    """
    try:
        file_response = await export_service.download_export(
            session, export_id, current_user.id
        )
        
        if not file_response:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Export file not found or expired"
            )
        
        logger.info(f"Export downloaded: {export_id} by user {current_user.id}")
        return file_response
        
    except ResumeNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Export not found"
        )
    except ExportFailedException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Export download failed: {export_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Export download failed"
        )


@router.get(
    "/resumes/{resume_id}/exports",
    response_model=List[ResumeExportResponse],
    summary="Get resume exports",
    description="Get all exports for a specific resume"
)
async def get_resume_exports(
    resume_id: uuid.UUID,
    limit: int = Query(10, ge=1, le=50, description="Number of exports to return"),
    current_user: User = Depends(get_current_verified_user),
    session: AsyncSession = Depends(get_db_session)
) -> List[ResumeExportResponse]:
    """
    Get all exports for a specific resume.
    
    - **resume_id**: Resume ID
    - **limit**: Maximum number of exports to return
    
    Returns list of exports ordered by creation date (newest first).
    """
    try:
        exports = await export_service.get_resume_exports(
            session, resume_id, current_user.id, limit
        )
        
        return [ResumeExportResponse.from_orm(export) for export in exports]
        
    except ResumeNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resume not found"
        )
    except Exception as e:
        logger.error(f"Failed to get resume exports: {resume_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve resume exports"
        )


@router.get(
    "/my-exports",
    response_model=ResumeExportListResponse,
    summary="Get user exports",
    description="Get all exports for current user with pagination"
)
async def get_user_exports(
    export_format: Optional[str] = Query(None, description="Filter by export format"),
    status: Optional[ProcessingStatus] = Query(None, description="Filter by export status"),
    pagination: PaginationParams = Depends(get_pagination_params),
    current_user: User = Depends(get_current_verified_user),
    session: AsyncSession = Depends(get_db_session)
) -> ResumeExportListResponse:
    """
    Get all exports for current user with filtering.
    
    - **export_format**: Filter by format (pdf, docx, json, html)
    - **status**: Filter by export status
    - **page**: Page number
    - **page_size**: Items per page
    
    Returns paginated list of user's exports.
    """
    try:
        filters = {
            "export_format": export_format,
            "status": status
        }
        
        exports, total_count = await export_service.get_user_exports(
            session, current_user.id, pagination, filters
        )
        
        total_pages = (total_count + pagination.page_size - 1) // pagination.page_size
        
        return ResumeExportListResponse(
            exports=[ResumeExportResponse.from_orm(export) for export in exports],
            total_count=total_count,
            page=pagination.page,
            page_size=pagination.page_size,
            total_pages=total_pages
        )
        
    except Exception as e:
        logger.error(f"Failed to get user exports for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve exports"
        )


@router.delete(
    "/{export_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete export",
    description="Delete an export record and file"
)
async def delete_export(
    export_id: uuid.UUID,
    current_user: User = Depends(get_current_verified_user),
    session: AsyncSession = Depends(get_db_session),
    request_id: str = Depends(get_request_id)
):
    """
    Delete an export record and associated file.
    
    - **export_id**: Export ID to delete
    
    This will permanently delete the export file and record.
    """
    try:
        success = await export_service.delete_export(
            session, export_id, current_user.id
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Export deletion failed"
            )
        
        logger.info(f"Export deleted: {export_id} by user {current_user.id} - Request: {request_id}")
        
    except ResumeNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Export not found"
        )
    except Exception as e:
        logger.error(f"Export deletion failed: {export_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Export deletion failed"
        )


@router.post(
    "/bulk",
    response_model=List[ResumeExportResponse],
    summary="Bulk export resumes",
    description="Export multiple resumes in batch"
)
async def bulk_export_resumes(
    resume_ids: List[uuid.UUID],
    export_format: str = Query(..., regex="^(pdf|docx|json|html)$", description="Export format"),
    template_id: Optional[uuid.UUID] = Query(None, description="Template to use"),
    current_user: User = Depends(get_current_verified_user),
    session: AsyncSession = Depends(get_db_session),
    request_id: str = Depends(get_request_id),
    _: None = Depends(check_rate_limit)
) -> List[ResumeExportResponse]:
    """
    Export multiple resumes in batch.
    
    - **resume_ids**: List of resume IDs to export (max 10)
    - **export_format**: Export format for all resumes
    - **template_id**: Template to use for all exports (optional)
    
    Returns list of export records for tracking.
    Premium feature with higher limits.
    """
    try:
        # Check limits
        max_bulk = 10 if current_user.is_premium else 3
        if len(resume_ids) > max_bulk:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Maximum {max_bulk} resumes allowed in bulk export"
            )
        
        exports = await export_service.bulk_export_resumes(
            session, resume_ids, current_user.id, export_format, template_id
        )
        
        logger.info(f"Bulk export created: {len(exports)} resumes by user {current_user.id} - Request: {request_id}")
        return [ResumeExportResponse.from_orm(export) for export in exports]
        
    except ValidationException as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Bulk export failed for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Bulk export failed"
        )


@router.post(
    "/templates/{template_id}/preview",
    summary="Preview template export",
    description="Generate preview of how resume will look with specific template"
)
async def preview_template_export(
    template_id: uuid.UUID,
    resume_id: uuid.UUID,
    export_format: str = Query("pdf", regex="^(pdf|html)$", description="Preview format"),
    current_user: User = Depends(get_current_verified_user),
    session: AsyncSession = Depends(get_db_session),
    _: None = Depends(check_rate_limit)
):
    """
    Generate preview of resume with specific template.
    
    - **template_id**: Template ID to preview
    - **resume_id**: Resume ID to use for preview
    - **export_format**: Preview format (pdf or html)
    
    Returns preview file for immediate viewing.
    """
    try:
        preview_response = await export_service.generate_template_preview(
            session, template_id, resume_id, current_user.id, export_format
        )
        
        return preview_response
        
    except ResumeNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resume or template not found"
        )
    except UnsupportedExportFormatException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Template preview failed: template {template_id}, resume {resume_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Template preview failed"
        )


@router.get(
    "/formats",
    response_model=List[dict],
    summary="Get supported export formats",
    description="Get list of supported export formats and their capabilities"
)
async def get_export_formats(
    current_user: User = Depends(get_current_verified_user)
) -> List[dict]:
    """
    Get supported export formats and their capabilities.
    
    Returns list of available export formats with features and limitations.
    """
    try:
        formats = await export_service.get_supported_formats(current_user.is_premium)
        return formats
        
    except Exception as e:
        logger.error(f"Failed to get export formats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve export formats"
        )


@router.get(
    "/stats",
    response_model=dict,
    summary="Get export statistics",
    description="Get user's export statistics and usage"
)
async def get_export_stats(
    current_user: User = Depends(get_current_verified_user),
    session: AsyncSession = Depends(get_db_session)
) -> dict:
    """
    Get user's export statistics.
    
    Returns comprehensive statistics about user's export activity and usage.
    """
    try:
        stats = await export_service.get_export_stats(session, current_user.id)
        return stats
        
    except Exception as e:
        logger.error(f"Failed to get export stats for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve export statistics"
        )


@router.post(
    "/cleanup",
    response_model=dict,
    summary="Cleanup expired exports",
    description="Clean up user's expired export files"
)
async def cleanup_expired_exports(
    current_user: User = Depends(get_current_verified_user),
    session: AsyncSession = Depends(get_db_session),
    request_id: str = Depends(get_request_id)
) -> dict:
    """
    Clean up user's expired export files.
    
    Removes expired export files to free up storage space.
    Returns count of cleaned up exports.
    """
    try:
        cleaned_count = await export_service.cleanup_user_expired_exports(
            session, current_user.id
        )
        
        logger.info(f"User export cleanup: {cleaned_count} files cleaned for user {current_user.id} - Request: {request_id}")
        
        return {
            "message": f"Cleaned up {cleaned_count} expired exports",
            "cleaned_count": cleaned_count
        }
        
    except Exception as e:
        logger.error(f"Export cleanup failed for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Export cleanup failed"
        )


@router.get(
    "/quota",
    response_model=dict,
    summary="Get export quota",
    description="Get user's export quota and usage limits"
)
async def get_export_quota(
    current_user: User = Depends(get_current_verified_user),
    session: AsyncSession = Depends(get_db_session)
) -> dict:
    """
    Get user's export quota and current usage.
    
    Returns export limits and current usage for the user's subscription level.
    """
    try:
        quota_info = await export_service.get_user_export_quota(
            session, current_user.id
        )
        
        return quota_info
        
    except Exception as e:
        logger.error(f"Failed to get export quota for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve export quota"
        )