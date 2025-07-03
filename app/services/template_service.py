"""
Template service for managing resume templates, customization, and recommendations.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
import uuid
import json

from sqlalchemy import select, update, and_, desc, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, joinedload

from app.config import settings
from app.exceptions import (
    TemplateNotFoundException, ValidationException, DatabaseException,
    PermissionDeniedException
)
from app.models.template import (
    ResumeTemplate, TemplateCustomization, TemplateRating, TemplateSection,
    TemplateCategory, TemplateStatus, TemplateType
)
from app.models.user import User
from app.schemas.template import (
    TemplateCreateRequest, TemplateUpdateRequest, TemplateCustomizationRequest,
    TemplateRatingRequest, TemplateSearchRequest, TemplateResponse,
    TemplateListResponse, TemplateCustomizationResponse, TemplatePreviewResponse,
    TemplateRatingResponse, TemplateStatsResponse, TemplateRecommendationResponse
)

logger = logging.getLogger(__name__)


class TemplateService:
    """Service for template management and customization."""
    
    def __init__(self):
        pass
    
    async def create_template(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        template_data: TemplateCreateRequest
    ) -> ResumeTemplate:
        """
        Create a new template (admin only).
        
        Args:
            session: Database session
            user_id: User ID (must be admin)
            template_data: Template data
            
        Returns:
            Created template
        """
        try:
            # Check if user is admin
            user_result = await session.execute(
                select(User).where(User.id == user_id)
            )
            user = user_result.scalar_one_or_none()
            
            if not user or not user.is_admin:
                raise PermissionDeniedException("Admin access required")
            
            # Create template
            template = ResumeTemplate(
                name=template_data.name,
                description=template_data.description,
                category=template_data.category,
                template_type=template_data.template_type,
                status=template_data.status,
                created_by=user_id,
                tags=template_data.tags or [],
                industries=template_data.industries or [],
                job_levels=template_data.job_levels or [],
                layout_config=template_data.layout_config,
                style_config=template_data.style_config,
                section_config=template_data.section_config,
                html_template=template_data.html_template,
                css_styles=template_data.css_styles,
                preview_image_url=template_data.preview_image_url,
                thumbnail_url=template_data.thumbnail_url,
                version=template_data.version,
                supports_photo=template_data.supports_photo,
                supports_colors=template_data.supports_colors,
                supports_fonts=template_data.supports_fonts,
                is_ats_friendly=template_data.is_ats_friendly,
                max_pages=template_data.max_pages,
                is_premium=template_data.is_premium,
                price=template_data.price,
                currency=template_data.currency
            )
            
            session.add(template)
            await session.flush()
            
            # Create default sections
            await self._create_default_template_sections(session, template.id, template_data.section_config)
            
            await session.commit()
            
            logger.info(f"Template created: {template.id}")
            return template
            
        except Exception as e:
            await session.rollback()
            if isinstance(e, PermissionDeniedException):
                raise
            logger.error(f"Template creation failed: {e}")
            raise DatabaseException(f"Template creation failed: {str(e)}")
    
    async def get_template(
        self,
        session: AsyncSession,
        template_id: uuid.UUID,
        user_id: Optional[uuid.UUID] = None
    ) -> ResumeTemplate:
        """
        Get template by ID.
        
        Args:
            session: Database session
            template_id: Template ID
            user_id: Optional user ID for permission check
            
        Returns:
            Template
        """
        query = (
            select(ResumeTemplate)
            .options(selectinload(ResumeTemplate.sections))
            .where(ResumeTemplate.id == template_id)
        )
        
        result = await session.execute(query)
        template = result.scalar_one_or_none()
        
        if not template:
            raise TemplateNotFoundException(str(template_id))
        
        # Check if user can access premium template
        if template.is_premium and user_id:
            user_result = await session.execute(
                select(User).where(User.id == user_id)
            )
            user = user_result.scalar_one_or_none()
            
            if not user or not user.is_premium:
                raise PermissionDeniedException("Premium subscription required")
        
        # Increment usage count
        template.usage_count += 1
        await session.commit()
        
        return template
    
    async def search_templates(
        self,
        session: AsyncSession,
        search_request: TemplateSearchRequest,
        user_id: Optional[uuid.UUID] = None
    ) -> Tuple[List[ResumeTemplate], int]:
        """
        Search and filter templates.
        
        Args:
            session: Database session
            search_request: Search parameters
            user_id: Optional user ID for premium filtering
            
        Returns:
            Tuple of (templates, total_count)
        """
        try:
            # Get user to check premium status
            is_premium = False
            if user_id:
                user_result = await session.execute(
                    select(User).where(User.id == user_id)
                )
                user = user_result.scalar_one_or_none()
                is_premium = user and user.is_premium
            
            # Build base query
            query = (
                select(ResumeTemplate)
                .where(ResumeTemplate.status == TemplateStatus.ACTIVE)
            )
            
            # Filter premium templates if user is not premium
            if not is_premium and not search_request.is_premium:
                query = query.where(ResumeTemplate.is_premium == False)
            
            # Apply text search
            if search_request.query:
                search_terms = f"%{search_request.query}%"
                query = query.where(
                    or_(
                        ResumeTemplate.name.ilike(search_terms),
                        ResumeTemplate.description.ilike(search_terms),
                        ResumeTemplate.tags.contains([search_request.query.lower()])
                    )
                )
            
            # Apply category filter
            if search_request.categories:
                query = query.where(ResumeTemplate.category.in_(search_request.categories))
            
            # Apply type filter
            if search_request.template_types:
                query = query.where(ResumeTemplate.template_type.in_(search_request.template_types))
            
            # Apply industry filter
            if search_request.industries:
                # Check if any of the search industries are in the template's industries
                for industry in search_request.industries:
                    query = query.where(ResumeTemplate.industries.contains([industry]))
            
            # Apply job level filter
            if search_request.job_levels:
                for level in search_request.job_levels:
                    query = query.where(ResumeTemplate.job_levels.contains([level]))
            
            # Apply tag filter
            if search_request.tags:
                for tag in search_request.tags:
                    query = query.where(ResumeTemplate.tags.contains([tag]))
            
            # Apply feature filters
            if search_request.supports_photo is not None:
                query = query.where(ResumeTemplate.supports_photo == search_request.supports_photo)
            
            if search_request.supports_colors is not None:
                query = query.where(ResumeTemplate.supports_colors == search_request.supports_colors)
            
            if search_request.supports_fonts is not None:
                query = query.where(ResumeTemplate.supports_fonts == search_request.supports_fonts)
            
            if search_request.is_ats_friendly is not None:
                query = query.where(ResumeTemplate.is_ats_friendly == search_request.is_ats_friendly)
            
            # Apply pricing filters
            if search_request.is_free is not None:
                if search_request.is_free:
                    query = query.where(
                        or_(
                            ResumeTemplate.is_premium == False,
                            ResumeTemplate.price == 0
                        )
                    )
                else:
                    query = query.where(
                        and_(
                            ResumeTemplate.is_premium == True,
                            ResumeTemplate.price > 0
                        )
                    )
            
            if search_request.max_price is not None:
                query = query.where(
                    or_(
                        ResumeTemplate.price <= search_request.max_price,
                        ResumeTemplate.price.is_(None)
                    )
                )
            
            # Apply quality filters
            if search_request.min_rating is not None:
                query = query.where(ResumeTemplate.rating_average >= search_request.min_rating)
            
            if search_request.min_usage_count is not None:
                query = query.where(ResumeTemplate.usage_count >= search_request.min_usage_count)
            
            # Get total count
            count_query = select(func.count()).select_from(query.subquery())
            total_result = await session.execute(count_query)
            total_count = total_result.scalar()
            
            # Apply sorting
            if search_request.sort_by == "name":
                sort_field = ResumeTemplate.name
            elif search_request.sort_by == "created_at":
                sort_field = ResumeTemplate.created_at
            elif search_request.sort_by == "usage_count":
                sort_field = ResumeTemplate.usage_count
            elif search_request.sort_by == "rating_average":
                sort_field = ResumeTemplate.rating_average
            elif search_request.sort_by == "price":
                sort_field = ResumeTemplate.price
            else:
                sort_field = ResumeTemplate.rating_average
            
            if search_request.sort_order == "asc":
                query = query.order_by(sort_field.asc())
            else:
                query = query.order_by(sort_field.desc())
            
            # Apply pagination
            paginated_query = query.limit(search_request.page_size).offset(
                (search_request.page - 1) * search_request.page_size
            )
            
            result = await session.execute(paginated_query)
            templates = result.scalars().all()
            
            return list(templates), total_count
            
        except Exception as e:
            logger.error(f"Template search failed: {e}")
            raise DatabaseException(f"Template search failed: {str(e)}")
    
    async def update_template(
        self,
        session: AsyncSession,
        template_id: uuid.UUID,
        user_id: uuid.UUID,
        template_data: TemplateUpdateRequest
    ) -> ResumeTemplate:
        """
        Update template (admin only).
        
        Args:
            session: Database session
            template_id: Template ID
            user_id: User ID (must be admin)
            template_data: Updated template data
            
        Returns:
            Updated template
        """
        try:
            # Check if user is admin
            user_result = await session.execute(
                select(User).where(User.id == user_id)
            )
            user = user_result.scalar_one_or_none()
            
            if not user or not user.is_admin:
                raise PermissionDeniedException("Admin access required")
            
            template = await self.get_template(session, template_id)
            
            # Update fields that are provided
            for field, value in template_data.dict(exclude_unset=True).items():
                if hasattr(template, field):
                    setattr(template, field, value)
            
            await session.commit()
            
            logger.info(f"Template updated: {template_id}")
            return template
            
        except Exception as e:
            await session.rollback()
            if isinstance(e, (TemplateNotFoundException, PermissionDeniedException)):
                raise
            logger.error(f"Template update failed: {template_id}, error: {e}")
            raise DatabaseException(f"Template update failed: {str(e)}")
    
    async def delete_template(
        self,
        session: AsyncSession,
        template_id: uuid.UUID,
        user_id: uuid.UUID
    ) -> bool:
        """
        Delete template (admin only).
        
        Args:
            session: Database session
            template_id: Template ID
            user_id: User ID (must be admin)
            
        Returns:
            True if successful
        """
        try:
            # Check if user is admin
            user_result = await session.execute(
                select(User).where(User.id == user_id)
            )
            user = user_result.scalar_one_or_none()
            
            if not user or not user.is_admin:
                raise PermissionDeniedException("Admin access required")
            
            template = await self.get_template(session, template_id)
            
            # Soft delete by setting status to inactive
            template.status = TemplateStatus.INACTIVE
            
            await session.commit()
            
            logger.info(f"Template deleted: {template_id}")
            return True
            
        except Exception as e:
            await session.rollback()
            if isinstance(e, (TemplateNotFoundException, PermissionDeniedException)):
                raise
            logger.error(f"Template deletion failed: {template_id}, error: {e}")
            return False
    
    async def customize_template(
        self,
        session: AsyncSession,
        template_id: uuid.UUID,
        user_id: uuid.UUID,
        customization_data: TemplateCustomizationRequest
    ) -> TemplateCustomization:
        """
        Create template customization for user.
        
        Args:
            session: Database session
            template_id: Template ID
            user_id: User ID
            customization_data: Customization data
            
        Returns:
            Created customization
        """
        try:
            # Verify template exists and user can access it
            template = await self.get_template(session, template_id, user_id)
            
            # Check if customization with same name exists for user
            existing = await session.execute(
                select(TemplateCustomization).where(
                    and_(
                        TemplateCustomization.template_id == template_id,
                        TemplateCustomization.user_id == user_id,
                        TemplateCustomization.name == customization_data.name
                    )
                )
            )
            
            if existing.scalar_one_or_none():
                raise ValidationException("Customization with this name already exists")
            
            # If setting as default, remove default from other customizations
            if customization_data.is_default:
                await session.execute(
                    update(TemplateCustomization)
                    .where(
                        and_(
                            TemplateCustomization.user_id == user_id,
                            TemplateCustomization.template_id == template_id
                        )
                    )
                    .values(is_default=False)
                )
            
            # Create customization
            customization = TemplateCustomization(
                template_id=template_id,
                user_id=user_id,
                name=customization_data.name,
                color_scheme=customization_data.color_scheme or {},
                font_settings=customization_data.font_settings or {},
                layout_modifications=customization_data.layout_modifications or {},
                section_settings=customization_data.section_settings or {},
                custom_css=customization_data.custom_css,
                is_default=customization_data.is_default
            )
            
            session.add(customization)
            await session.commit()
            
            logger.info(f"Template customization created: {customization.id}")
            return customization
            
        except Exception as e:
            await session.rollback()
            if isinstance(e, (TemplateNotFoundException, ValidationException, PermissionDeniedException)):
                raise
            logger.error(f"Template customization failed: {template_id}, error: {e}")
            raise DatabaseException(f"Template customization failed: {str(e)}")
    
    async def rate_template(
        self,
        session: AsyncSession,
        template_id: uuid.UUID,
        user_id: uuid.UUID,
        rating_data: TemplateRatingRequest
    ) -> TemplateRating:
        """
        Rate a template.
        
        Args:
            session: Database session
            template_id: Template ID
            user_id: User ID
            rating_data: Rating data
            
        Returns:
            Created/updated rating
        """
        try:
            # Verify template exists
            template = await self.get_template(session, template_id, user_id)
            
            # Check if user already rated this template
            existing_rating = await session.execute(
                select(TemplateRating).where(
                    and_(
                        TemplateRating.template_id == template_id,
                        TemplateRating.user_id == user_id
                    )
                )
            )
            rating = existing_rating.scalar_one_or_none()
            
            if rating:
                # Update existing rating
                rating.rating = rating_data.rating
                rating.review = rating_data.review
            else:
                # Create new rating
                rating = TemplateRating(
                    template_id=template_id,
                    user_id=user_id,
                    rating=rating_data.rating,
                    review=rating_data.review
                )
                session.add(rating)
            
            await session.flush()
            
            # Update template rating statistics
            await self._update_template_rating_stats(session, template_id)
            
            await session.commit()
            
            logger.info(f"Template rated: {template_id}, rating: {rating_data.rating}")
            return rating
            
        except Exception as e:
            await session.rollback()
            if isinstance(e, (TemplateNotFoundException, PermissionDeniedException)):
                raise
            logger.error(f"Template rating failed: {template_id}, error: {e}")
            raise DatabaseException(f"Template rating failed: {str(e)}")
    
    async def get_template_recommendations(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        limit: int = 10
    ) -> TemplateRecommendationResponse:
        """
        Get personalized template recommendations for user.
        
        Args:
            session: Database session
            user_id: User ID
            limit: Number of recommendations
            
        Returns:
            Template recommendations
        """
        try:
            # Get user profile for personalization
            user_result = await session.execute(
                select(User).where(User.id == user_id)
            )
            user = user_result.scalar_one_or_none()
            
            if not user:
                raise ValidationException("User not found")
            
            # Build recommendation query
            query = (
                select(ResumeTemplate)
                .where(ResumeTemplate.status == TemplateStatus.ACTIVE)
                .order_by(desc(ResumeTemplate.rating_average), desc(ResumeTemplate.usage_count))
            )
            
            # Filter premium templates if user is not premium
            if not user.is_premium:
                query = query.where(ResumeTemplate.is_premium == False)
            
            # Add industry-based filtering
            if user.industry:
                query = query.where(
                    or_(
                        ResumeTemplate.industries.contains([user.industry]),
                        ResumeTemplate.industries == []  # Generic templates
                    )
                )
            
            # Get recommended templates
            result = await session.execute(query.limit(limit))
            recommended_templates = result.scalars().all()
            
            # Generate recommendation reasons
            recommendation_reasons = {}
            industry_match = {}
            experience_level_match = {}
            style_preference_match = {}
            
            for template in recommended_templates:
                reasons = []
                
                # Industry match
                if user.industry and user.industry in (template.industries or []):
                    reasons.append(f"Matches your {user.industry} industry")
                    industry_match[str(template.id)] = 1.0
                else:
                    industry_match[str(template.id)] = 0.0
                
                # Experience level match
                if user.experience_years:
                    if user.experience_years < 3 and "entry" in (template.job_levels or []):
                        reasons.append("Perfect for entry-level positions")
                        experience_level_match[str(template.id)] = 1.0
                    elif user.experience_years >= 10 and "senior" in (template.job_levels or []):
                        reasons.append("Ideal for senior-level roles")
                        experience_level_match[str(template.id)] = 1.0
                    else:
                        experience_level_match[str(template.id)] = 0.5
                else:
                    experience_level_match[str(template.id)] = 0.5
                
                # High rating
                if template.rating_average and template.rating_average >= 4.5:
                    reasons.append("Highly rated by users")
                
                # Popular template
                if template.usage_count > 100:
                    reasons.append("Popular choice among job seekers")
                
                # ATS friendly
                if template.is_ats_friendly:
                    reasons.append("ATS-friendly design")
                
                # Style preference (simplified)
                style_preference_match[str(template.id)] = 0.8
                
                recommendation_reasons[str(template.id)] = reasons[:3]  # Top 3 reasons
            
            return TemplateRecommendationResponse(
                recommended_templates=[TemplateResponse.from_orm(t) for t in recommended_templates],
                recommendation_reasons=recommendation_reasons,
                user_preferences={
                    "industry": user.industry,
                    "experience_years": user.experience_years,
                    "is_premium": user.is_premium
                },
                industry_match=industry_match,
                experience_level_match=experience_level_match,
                style_preference_match=style_preference_match,
                generated_at=datetime.utcnow()
            )
            
        except Exception as e:
            if isinstance(e, ValidationException):
                raise
            logger.error(f"Template recommendations failed for user {user_id}: {e}")
            raise DatabaseException(f"Failed to generate recommendations: {str(e)}")
    
    async def get_template_statistics(
        self,
        session: AsyncSession,
        admin_user_id: Optional[uuid.UUID] = None
    ) -> TemplateStatsResponse:
        """
        Get template statistics (admin only).
        
        Args:
            session: Database session
            admin_user_id: Admin user ID (optional, for permission check)
            
        Returns:
            Template statistics
        """
        try:
            # If user ID provided, verify admin status
            if admin_user_id:
                user_result = await session.execute(
                    select(User).where(User.id == admin_user_id)
                )
                user = user_result.scalar_one_or_none()
                
                if not user or not user.is_admin:
                    raise PermissionDeniedException("Admin access required")
            
            # Total templates
            total_templates = await session.execute(
                select(func.count(ResumeTemplate.id))
            )
            total_templates = total_templates.scalar()
            
            # Templates by category
            templates_by_category = await session.execute(
                select(ResumeTemplate.category, func.count(ResumeTemplate.id))
                .group_by(ResumeTemplate.category)
            )
            category_counts = dict(templates_by_category.fetchall())
            
            # Templates by type
            templates_by_type = await session.execute(
                select(ResumeTemplate.template_type, func.count(ResumeTemplate.id))
                .group_by(ResumeTemplate.template_type)
            )
            type_counts = dict(templates_by_type.fetchall())
            
            # Usage statistics
            total_usage = await session.execute(
                select(func.sum(ResumeTemplate.usage_count))
            )
            total_usage = total_usage.scalar() or 0
            
            total_downloads = await session.execute(
                select(func.sum(ResumeTemplate.download_count))
            )
            total_downloads = total_downloads.scalar() or 0
            
            # Most used templates
            most_used = await session.execute(
                select(ResumeTemplate.name, ResumeTemplate.usage_count)
                .order_by(desc(ResumeTemplate.usage_count))
                .limit(5)
            )
            most_used_templates = [
                {"name": name, "usage_count": count}
                for name, count in most_used.fetchall()
            ]
            
            # Rating statistics
            avg_rating = await session.execute(
                select(func.avg(ResumeTemplate.rating_average))
                .where(ResumeTemplate.rating_average.isnot(None))
            )
            average_rating = float(avg_rating.scalar() or 0)
            
            total_ratings = await session.execute(
                select(func.sum(ResumeTemplate.rating_count))
            )
            total_ratings = total_ratings.scalar() or 0
            
            # Top rated templates
            top_rated = await session.execute(
                select(ResumeTemplate.name, ResumeTemplate.rating_average)
                .where(ResumeTemplate.rating_average.isnot(None))
                .order_by(desc(ResumeTemplate.rating_average))
                .limit(5)
            )
            top_rated_templates = [
                {"name": name, "rating": float(rating)}
                for name, rating in top_rated.fetchall()
            ]
            
            # Premium statistics
            premium_count = await session.execute(
                select(func.count(ResumeTemplate.id))
                .where(ResumeTemplate.is_premium == True)
            )
            premium_templates = premium_count.scalar()
            
            free_count = await session.execute(
                select(func.count(ResumeTemplate.id))
                .where(ResumeTemplate.is_premium == False)
            )
            free_templates = free_count.scalar()
            
            # Recent activity
            month_ago = datetime.utcnow() - timedelta(days=30)
            
            templates_added_this_month = await session.execute(
                select(func.count(ResumeTemplate.id))
                .where(ResumeTemplate.created_at >= month_ago)
            )
            templates_added_this_month = templates_added_this_month.scalar()
            
            return TemplateStatsResponse(
                total_templates=total_templates,
                templates_by_category=category_counts,
                templates_by_type=type_counts,
                total_usage=total_usage,
                total_downloads=total_downloads,
                most_used_templates=most_used_templates,
                average_rating=average_rating,
                total_ratings=total_ratings,
                top_rated_templates=top_rated_templates,
                premium_templates=premium_templates,
                free_templates=free_templates,
                total_revenue=None,  # Can be calculated from purchases
                templates_added_this_month=templates_added_this_month,
                usage_this_month=0,  # Can be tracked separately
                downloads_this_month=0,  # Can be tracked separately
                last_updated=datetime.utcnow()
            )
            
        except Exception as e:
            if isinstance(e, PermissionDeniedException):
                raise
            logger.error(f"Template statistics failed: {e}")
            raise DatabaseException(f"Failed to retrieve statistics: {str(e)}")
    
    # Private helper methods
    async def _create_default_template_sections(
        self,
        session: AsyncSession,
        template_id: uuid.UUID,
        section_config: Dict[str, Any]
    ) -> None:
        """Create default template sections."""
        default_sections = [
            ("personal_info", "Personal Information", 1, True, True),
            ("summary", "Professional Summary", 2, True, True),
            ("experience", "Work Experience", 3, True, True),
            ("education", "Education", 4, True, True),
            ("skills", "Skills", 5, True, True),
            ("certifications", "Certifications", 6, False, False),
            ("projects", "Projects", 7, False, False),
            ("achievements", "Achievements", 8, False, False),
        ]
        
        for section_type, name, order, required, visible in default_sections:
            section = TemplateSection(
                template_id=template_id,
                section_type=section_type,
                section_name=name,
                order_index=order,
                is_required=required,
                is_visible=visible,
                layout_config=section_config.get(section_type, {}),
                style_config={},
                field_config={}
            )
            session.add(section)
    
    async def _update_template_rating_stats(
        self,
        session: AsyncSession,
        template_id: uuid.UUID
    ) -> None:
        """Update template rating statistics."""
        # Calculate average rating and count
        rating_stats = await session.execute(
            select(
                func.avg(TemplateRating.rating),
                func.count(TemplateRating.id)
            )
            .where(TemplateRating.template_id == template_id)
        )
        
        avg_rating, rating_count = rating_stats.first()
        
        # Update template
        await session.execute(
            update(ResumeTemplate)
            .where(ResumeTemplate.id == template_id)
            .values(
                rating_average=float(avg_rating) if avg_rating else None,
                rating_count=rating_count
            )
        )


# Export service
__all__ = ["TemplateService"]