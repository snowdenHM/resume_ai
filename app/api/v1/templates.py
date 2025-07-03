"""
Resume template API endpoints for template management and customization.
"""

import logging
from typing import List, Optional
import uuid

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    get_db_session, get_current_verified_user, get_current_admin_user,
    get_pagination_params, PaginationParams, check_rate_limit, get_request_id
)
from app.exceptions import (
    TemplateNotFoundException, ValidationException, AuthorizationException
)
from app.models.user import User
from app.models.template import TemplateCategory, TemplateStatus, TemplateType
from app.schemas.template import (
    TemplateResponse, TemplateListResponse, TemplateCreateRequest,
    TemplateUpdateRequest, TemplateCustomizationResponse, TemplateRatingRequest,
    TemplateSearchRequest, TemplatePreviewResponse
)
from app.services.template_service import TemplateService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/templates", tags=["Resume Templates"])

# Initialize service
template_service = TemplateService()


@router.get(
    "/",
    response_model=TemplateListResponse,
    summary="Get resume templates",
    description="Get available resume templates with filtering and pagination"
)
async def get_templates(
    category: Optional[TemplateCategory] = Query(None, description="Filter by template category"),
    template_type: Optional[TemplateType] = Query(None, description="Filter by template type"),
    is_premium: Optional[bool] = Query(None, description="Filter by premium status"),
    industry: Optional[str] = Query(None, description="Filter by suitable industry"),
    job_level: Optional[str] = Query(None, description="Filter by suitable job level"),
    pagination: PaginationParams = Depends(get_pagination_params),
    current_user: User = Depends(get_current_verified_user),
    session: AsyncSession = Depends(get_db_session)
) -> TemplateListResponse:
    """
    Get available resume templates with filtering.
    
    - **category**: Template category (modern, classic, creative, etc.)
    - **template_type**: Template type (system, premium, user_created)
    - **is_premium**: Filter by premium status
    - **industry**: Filter by suitable industry
    - **job_level**: Filter by suitable job level
    - **page**: Page number
    - **page_size**: Items per page
    
    Returns paginated list of templates with preview information.
    """
    try:
        filters = {
            "category": category,
            "template_type": template_type,
            "is_premium": is_premium,
            "industry": industry,
            "job_level": job_level
        }
        
        templates, total_count = await template_service.get_templates(
            session, current_user.id, pagination, filters
        )
        
        total_pages = (total_count + pagination.page_size - 1) // pagination.page_size
        
        return TemplateListResponse(
            templates=[TemplateResponse.from_orm(template) for template in templates],
            total_count=total_count,
            page=pagination.page,
            page_size=pagination.page_size,
            total_pages=total_pages
        )
        
    except Exception as e:
        logger.error(f"Failed to get templates: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve templates"
        )


@router.get(
    "/{template_id}",
    response_model=TemplateResponse,
    summary="Get template details",
    description="Get detailed template information including sections and customization options"
)
async def get_template(
    template_id: uuid.UUID,
    current_user: User = Depends(get_current_verified_user),
    session: AsyncSession = Depends(get_db_session)
) -> TemplateResponse:
    """
    Get detailed template information.
    
    - **template_id**: Template ID
    
    Returns complete template data including configuration and customization options.
    """
    try:
        template = await template_service.get_template(
            session, template_id, current_user.id
        )
        
        return TemplateResponse.from_orm(template)
        
    except TemplateNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found"
        )
    except Exception as e:
        logger.error(f"Failed to get template {template_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve template"
        )


@router.get(
    "/{template_id}/preview",
    response_model=TemplatePreviewResponse,
    summary="Preview template",
    description="Generate template preview with sample data"
)
async def preview_template(
    template_id: uuid.UUID,
    current_user: User = Depends(get_current_verified_user),
    session: AsyncSession = Depends(get_db_session)
) -> TemplatePreviewResponse:
    """
    Generate template preview with sample data.
    
    - **template_id**: Template ID
    
    Returns rendered template preview with placeholder content.
    """
    try:
        preview = await template_service.generate_template_preview(
            session, template_id, current_user.id
        )
        
        return preview
        
    except TemplateNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found"
        )
    except Exception as e:
        logger.error(f"Failed to preview template {template_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate template preview"
        )


@router.post(
    "/{template_id}/customize",
    response_model=TemplateCustomizationResponse,
    summary="Customize template",
    description="Create customized version of template with personal preferences"
)
async def customize_template(
    template_id: uuid.UUID,
    customization_data: dict,
    current_user: User = Depends(get_current_verified_user),
    session: AsyncSession = Depends(get_db_session),
    request_id: str = Depends(get_request_id)
) -> TemplateCustomizationResponse:
    """
    Create customized version of template.
    
    - **template_id**: Base template ID
    - **customization_data**: Customization settings (colors, fonts, layout, etc.)
    
    Returns customized template configuration.
    Premium users get advanced customization options.
    """
    try:
        customization = await template_service.customize_template(
            session, template_id, current_user.id, customization_data
        )
        
        logger.info(f"Template customized: {template_id} by user {current_user.id} - Request: {request_id}")
        return TemplateCustomizationResponse.from_orm(customization)
        
    except TemplateNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found"
        )
    except ValidationException as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Template customization failed: {template_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Template customization failed"
        )


@router.get(
    "/customizations/my",
    response_model=List[TemplateCustomizationResponse],
    summary="Get user customizations",
    description="Get user's template customizations"
)
async def get_user_customizations(
    current_user: User = Depends(get_current_verified_user),
    session: AsyncSession = Depends(get_db_session)
) -> List[TemplateCustomizationResponse]:
    """
    Get user's template customizations.
    
    Returns list of user's custom template configurations.
    """
    try:
        customizations = await template_service.get_user_customizations(
            session, current_user.id
        )
        
        return [TemplateCustomizationResponse.from_orm(c) for c in customizations]
        
    except Exception as e:
        logger.error(f"Failed to get customizations for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve customizations"
        )


@router.post(
    "/{template_id}/rate",
    response_model=dict,
    summary="Rate template",
    description="Rate and review a template"
)
async def rate_template(
    template_id: uuid.UUID,
    rating_data: TemplateRatingRequest,
    current_user: User = Depends(get_current_verified_user),
    session: AsyncSession = Depends(get_db_session),
    request_id: str = Depends(get_request_id)
) -> dict:
    """
    Rate and review a template.
    
    - **template_id**: Template ID
    - **rating**: Rating from 1-5 stars
    - **review**: Optional written review
    
    Returns confirmation of rating submission.
    """
    try:
        await template_service.rate_template(
            session, template_id, current_user.id, rating_data
        )
        
        logger.info(f"Template rated: {template_id} by user {current_user.id} - Request: {request_id}")
        return {"message": "Template rating submitted successfully"}
        
    except TemplateNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found"
        )
    except ValidationException as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Template rating failed: {template_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Template rating failed"
        )


@router.post(
    "/search",
    response_model=TemplateListResponse,
    summary="Search templates",
    description="Search templates with advanced filtering and recommendations"
)
async def search_templates(
    search_params: TemplateSearchRequest,
    current_user: User = Depends(get_current_verified_user),
    session: AsyncSession = Depends(get_db_session)
) -> TemplateListResponse:
    """
    Search templates with advanced filtering.
    
    - **query**: Text search query
    - **categories**: Template categories
    - **industries**: Suitable industries
    - **job_levels**: Suitable job levels
    - **features**: Required features (supports_photo, ats_friendly, etc.)
    - **price_range**: Price range filter
    - **min_rating**: Minimum rating filter
    
    Returns matching templates ranked by relevance and rating.
    """
    try:
        templates, total_count = await template_service.search_templates(
            session, current_user.id, search_params
        )
        
        total_pages = (total_count + search_params.page_size - 1) // search_params.page_size
        
        return TemplateListResponse(
            templates=[TemplateResponse.from_orm(template) for template in templates],
            total_count=total_count,
            page=search_params.page,
            page_size=search_params.page_size,
            total_pages=total_pages
        )
        
    except Exception as e:
        logger.error(f"Template search failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Template search failed"
        )


@router.get(
    "/recommendations/for-me",
    response_model=List[TemplateResponse],
    summary="Get template recommendations",
    description="Get personalized template recommendations based on user profile and resume history"
)
async def get_template_recommendations(
    limit: int = Query(10, ge=1, le=20, description="Number of recommendations"),
    current_user: User = Depends(get_current_verified_user),
    session: AsyncSession = Depends(get_db_session)
) -> List[TemplateResponse]:
    """
    Get personalized template recommendations.
    
    - **limit**: Number of recommendations to return
    
    Returns templates recommended based on user's industry, experience level, and preferences.
    """
    try:
        recommendations = await template_service.get_template_recommendations(
            session, current_user.id, limit
        )
        
        return [TemplateResponse.from_orm(template) for template in recommendations]
        
    except Exception as e:
        logger.error(f"Failed to get template recommendations for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get template recommendations"
        )


# Admin endpoints for template management
@router.post(
    "/admin/create",
    response_model=TemplateResponse,
    summary="Create template (Admin)",
    description="Create new resume template (Admin only)"
)
async def admin_create_template(
    template_data: TemplateCreateRequest,
    current_user: User = Depends(get_current_admin_user),
    session: AsyncSession = Depends(get_db_session),
    request_id: str = Depends(get_request_id)
) -> TemplateResponse:
    """
    Create new resume template (Admin only).
    
    - **name**: Template name
    - **description**: Template description
    - **category**: Template category
    - **layout_config**: Layout configuration
    - **style_config**: Style configuration
    - **section_config**: Section configuration
    - **html_template**: HTML template content
    - **css_styles**: CSS styles
    - **is_premium**: Premium template flag
    - **price**: Template price (if premium)
    
    Returns created template.
    """
    try:
        template = await template_service.admin_create_template(
            session, current_user.id, template_data
        )
        
        logger.info(f"Template created by admin: {template.id} by user {current_user.id} - Request: {request_id}")
        return TemplateResponse.from_orm(template)
        
    except ValidationException as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Admin template creation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Template creation failed"
        )


@router.put(
    "/admin/{template_id}",
    response_model=TemplateResponse,
    summary="Update template (Admin)",
    description="Update resume template (Admin only)"
)
async def admin_update_template(
    template_id: uuid.UUID,
    template_data: TemplateUpdateRequest,
    current_user: User = Depends(get_current_admin_user),
    session: AsyncSession = Depends(get_db_session),
    request_id: str = Depends(get_request_id)
) -> TemplateResponse:
    """
    Update resume template (Admin only).
    
    - **template_id**: Template ID to update
    - All fields are optional for partial updates
    
    Returns updated template.
    """
    try:
        template = await template_service.admin_update_template(
            session, template_id, template_data
        )
        
        logger.info(f"Template updated by admin: {template_id} by user {current_user.id} - Request: {request_id}")
        return TemplateResponse.from_orm(template)
        
    except TemplateNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found"
        )
    except ValidationException as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Admin template update failed: {template_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Template update failed"
        )


@router.delete(
    "/admin/{template_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete template (Admin)",
    description="Delete resume template (Admin only)"
)
async def admin_delete_template(
    template_id: uuid.UUID,
    current_user: User = Depends(get_current_admin_user),
    session: AsyncSession = Depends(get_db_session),
    request_id: str = Depends(get_request_id)
):
    """
    Delete resume template (Admin only).
    
    - **template_id**: Template ID to delete
    
    This will affect all users currently using this template.
    """
    try:
        success = await template_service.admin_delete_template(
            session, template_id
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Template deletion failed"
            )
        
        logger.info(f"Template deleted by admin: {template_id} by user {current_user.id} - Request: {request_id}")
        
    except TemplateNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found"
        )
    except Exception as e:
        logger.error(f"Admin template deletion failed: {template_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Template deletion failed"
        )


@router.get(
    "/admin/stats",
    response_model=dict,
    summary="Get template statistics (Admin)",
    description="Get comprehensive template usage statistics (Admin only)"
)
async def admin_get_template_stats(
    current_user: User = Depends(get_current_admin_user),
    session: AsyncSession = Depends(get_db_session)
) -> dict:
    """
    Get template usage statistics (Admin only).
    
    Returns comprehensive statistics about template usage, ratings, and performance.
    """
    try:
        stats = await template_service.admin_get_template_stats(session)
        return stats
        
    except Exception as e:
        logger.error(f"Admin template stats failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve template statistics"
        )