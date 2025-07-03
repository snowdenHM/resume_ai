"""
Template-related Pydantic schemas for request/response validation.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
import uuid

from pydantic import BaseModel, Field, validator

from app.models.template import TemplateCategory, TemplateStatus, TemplateType


# Base schemas
class TemplateBase(BaseModel):
    """Base template schema with common fields."""
    
    name: str = Field(..., min_length=1, max_length=100, description="Template name")
    description: Optional[str] = Field(None, description="Template description")
    category: TemplateCategory = Field(..., description="Template category")
    tags: Optional[List[str]] = Field(None, description="Template tags")
    industries: Optional[List[str]] = Field(None, description="Suitable industries")
    job_levels: Optional[List[str]] = Field(None, description="Suitable job levels")


# Request schemas
class TemplateCreateRequest(TemplateBase):
    """Schema for creating a template (admin only)."""
    
    template_type: TemplateType = Field(TemplateType.SYSTEM, description="Template type")
    status: TemplateStatus = Field(TemplateStatus.ACTIVE, description="Template status")
    
    # Template configuration
    layout_config: Dict[str, Any] = Field(default_factory=dict, description="Layout configuration")
    style_config: Dict[str, Any] = Field(default_factory=dict, description="Style configuration")
    section_config: Dict[str, Any] = Field(default_factory=dict, description="Section configuration")
    
    # Template assets
    html_template: Optional[str] = Field(None, description="HTML template content")
    css_styles: Optional[str] = Field(None, description="CSS styles")
    preview_image_url: Optional[str] = Field(None, description="Preview image URL")
    thumbnail_url: Optional[str] = Field(None, description="Thumbnail image URL")
    
    # Version
    version: str = Field("1.0", description="Template version")
    
    # Features
    supports_photo: bool = Field(True, description="Supports profile photo")
    supports_colors: bool = Field(True, description="Supports color customization")
    supports_fonts: bool = Field(True, description="Supports font customization")
    is_ats_friendly: bool = Field(True, description="ATS-friendly design")
    max_pages: int = Field(2, ge=1, le=10, description="Maximum recommended pages")
    
    # Pricing
    is_premium: bool = Field(False, description="Premium template flag")
    price: Optional[float] = Field(None, ge=0, description="Template price")
    currency: str = Field("USD", description="Price currency")


class TemplateUpdateRequest(BaseModel):
    """Schema for updating a template (admin only)."""
    
    name: Optional[str] = Field(None, min_length=1, max_length=100, description="Template name")
    description: Optional[str] = Field(None, description="Template description")
    category: Optional[TemplateCategory] = Field(None, description="Template category")
    status: Optional[TemplateStatus] = Field(None, description="Template status")
    tags: Optional[List[str]] = Field(None, description="Template tags")
    industries: Optional[List[str]] = Field(None, description="Suitable industries")
    job_levels: Optional[List[str]] = Field(None, description="Suitable job levels")
    
    # Template configuration
    layout_config: Optional[Dict[str, Any]] = Field(None, description="Layout configuration")
    style_config: Optional[Dict[str, Any]] = Field(None, description="Style configuration")
    section_config: Optional[Dict[str, Any]] = Field(None, description="Section configuration")
    
    # Template assets
    html_template: Optional[str] = Field(None, description="HTML template content")
    css_styles: Optional[str] = Field(None, description="CSS styles")
    preview_image_url: Optional[str] = Field(None, description="Preview image URL")
    thumbnail_url: Optional[str] = Field(None, description="Thumbnail image URL")
    
    # Version
    version: Optional[str] = Field(None, description="Template version")
    
    # Features
    supports_photo: Optional[bool] = Field(None, description="Supports profile photo")
    supports_colors: Optional[bool] = Field(None, description="Supports color customization")
    supports_fonts: Optional[bool] = Field(None, description="Supports font customization")
    is_ats_friendly: Optional[bool] = Field(None, description="ATS-friendly design")
    max_pages: Optional[int] = Field(None, ge=1, le=10, description="Maximum recommended pages")
    
    # Pricing
    is_premium: Optional[bool] = Field(None, description="Premium template flag")
    price: Optional[float] = Field(None, ge=0, description="Template price")
    currency: Optional[str] = Field(None, description="Price currency")


class TemplateCustomizationRequest(BaseModel):
    """Schema for template customization request."""
    
    name: str = Field(..., min_length=1, max_length=100, description="Customization name")
    
    # Customization data
    color_scheme: Optional[Dict[str, Any]] = Field(None, description="Custom color scheme")
    font_settings: Optional[Dict[str, Any]] = Field(None, description="Custom font settings")
    layout_modifications: Optional[Dict[str, Any]] = Field(None, description="Layout modifications")
    section_settings: Optional[Dict[str, Any]] = Field(None, description="Section-specific settings")
    custom_css: Optional[str] = Field(None, description="Custom CSS overrides")
    
    # Status
    is_default: bool = Field(False, description="Set as default customization")


class TemplateRatingRequest(BaseModel):
    """Schema for rating a template."""
    
    rating: float = Field(..., ge=1, le=5, description="Rating from 1-5 stars")
    review: Optional[str] = Field(None, max_length=1000, description="Written review")
    
    @validator("rating")
    def validate_rating(cls, v):
        if not 1 <= v <= 5:
            raise ValueError("Rating must be between 1 and 5")
        return v


# Response schemas
class TemplateResponse(TemplateBase):
    """Schema for template response."""
    
    id: uuid.UUID = Field(..., description="Template ID")
    template_type: TemplateType = Field(..., description="Template type")
    status: TemplateStatus = Field(..., description="Template status")
    created_by: Optional[uuid.UUID] = Field(None, description="Creator user ID")
    
    # Template configuration
    layout_config: Dict[str, Any] = Field(..., description="Layout configuration")
    style_config: Dict[str, Any] = Field(..., description="Style configuration")
    section_config: Dict[str, Any] = Field(..., description="Section configuration")
    
    # Template assets
    preview_image_url: Optional[str] = Field(None, description="Preview image URL")
    thumbnail_url: Optional[str] = Field(None, description="Thumbnail image URL")
    html_template: Optional[str] = Field(None, description="HTML template content")
    css_styles: Optional[str] = Field(None, description="CSS styles")
    
    # Version and metadata
    version: str = Field(..., description="Template version")
    
    # Features
    supports_photo: bool = Field(..., description="Supports profile photo")
    supports_colors: bool = Field(..., description="Supports color customization")
    supports_fonts: bool = Field(..., description="Supports font customization")
    is_ats_friendly: bool = Field(..., description="ATS-friendly design")
    max_pages: int = Field(..., description="Maximum recommended pages")
    
    # Pricing
    is_premium: bool = Field(..., description="Premium template flag")
    price: Optional[float] = Field(None, description="Template price")
    currency: str = Field(..., description="Price currency")
    formatted_price: Optional[str] = Field(None, description="Formatted price string")
    is_free: Optional[bool] = Field(None, description="Whether template is free")
    
    # Usage statistics
    usage_count: int = Field(..., description="Number of times used")
    download_count: int = Field(..., description="Number of downloads")
    rating_average: Optional[float] = Field(None, description="Average user rating")
    rating_count: int = Field(..., description="Number of ratings")
    rating_stars: Optional[str] = Field(None, description="Star rating display")
    
    # Computed properties
    is_active: Optional[bool] = Field(None, description="Whether template is active")
    
    # Timestamps
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    
    class Config:
        from_attributes = True


class TemplateListResponse(BaseModel):
    """Schema for paginated template list response."""
    
    templates: List[TemplateResponse] = Field(..., description="List of templates")
    total_count: int = Field(..., description="Total number of templates")
    page: int = Field(..., description="Current page number")
    page_size: int = Field(..., description="Page size")
    total_pages: int = Field(..., description="Total number of pages")


class TemplateCustomizationResponse(BaseModel):
    """Schema for template customization response."""
    
    id: uuid.UUID = Field(..., description="Customization ID")
    template_id: uuid.UUID = Field(..., description="Base template ID")
    user_id: uuid.UUID = Field(..., description="User who customized")
    name: str = Field(..., description="Customization name")
    
    # Customization data
    color_scheme: Dict[str, Any] = Field(..., description="Custom color scheme")
    font_settings: Dict[str, Any] = Field(..., description="Custom font settings")
    layout_modifications: Dict[str, Any] = Field(..., description="Layout modifications")
    section_settings: Dict[str, Any] = Field(..., description="Section settings")
    custom_css: Optional[str] = Field(None, description="Custom CSS overrides")
    
    # Status
    is_active: bool = Field(..., description="Customization active status")
    is_default: bool = Field(..., description="User's default customization")
    
    # Timestamps
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    
    class Config:
        from_attributes = True


class TemplatePreviewResponse(BaseModel):
    """Schema for template preview response."""
    
    template_id: uuid.UUID = Field(..., description="Template ID")
    preview_type: str = Field(..., description="Type of preview")
    
    # Preview content
    html_content: str = Field(..., description="Rendered HTML content")
    css_content: str = Field(..., description="Applied CSS styles")
    preview_image_url: Optional[str] = Field(None, description="Generated preview image")
    
    # Sample data used
    sample_data: Dict[str, Any] = Field(..., description="Sample data used for preview")
    
    # Metadata
    generated_at: datetime = Field(..., description="Preview generation timestamp")
    expires_at: Optional[datetime] = Field(None, description="Preview expiration time")


class TemplateRatingResponse(BaseModel):
    """Schema for template rating response."""
    
    id: uuid.UUID = Field(..., description="Rating ID")
    template_id: uuid.UUID = Field(..., description="Template ID")
    user_id: uuid.UUID = Field(..., description="User who rated")
    rating: float = Field(..., description="Rating value")
    review: Optional[str] = Field(None, description="Written review")
    created_at: datetime = Field(..., description="Rating timestamp")
    
    class Config:
        from_attributes = True


# Search and filter schemas
class TemplateSearchRequest(BaseModel):
    """Schema for template search request."""
    
    query: Optional[str] = Field(None, description="Text search query")
    categories: Optional[List[TemplateCategory]] = Field(None, description="Template categories")
    template_types: Optional[List[TemplateType]] = Field(None, description="Template types")
    industries: Optional[List[str]] = Field(None, description="Suitable industries")
    job_levels: Optional[List[str]] = Field(None, description="Suitable job levels")
    tags: Optional[List[str]] = Field(None, description="Template tags")
    
    # Feature filters
    features: Optional[List[str]] = Field(None, description="Required features")
    supports_photo: Optional[bool] = Field(None, description="Supports profile photo")
    supports_colors: Optional[bool] = Field(None, description="Supports color customization")
    supports_fonts: Optional[bool] = Field(None, description="Supports font customization")
    is_ats_friendly: Optional[bool] = Field(None, description="ATS-friendly design")
    
    # Pricing filters
    price_range: Optional[str] = Field(None, description="Price range filter")
    is_free: Optional[bool] = Field(None, description="Free templates only")
    is_premium: Optional[bool] = Field(None, description="Premium templates only")
    max_price: Optional[float] = Field(None, ge=0, description="Maximum price")
    
    # Quality filters
    min_rating: Optional[float] = Field(None, ge=1, le=5, description="Minimum rating")
    min_usage_count: Optional[int] = Field(None, ge=0, description="Minimum usage count")
    
    # Pagination and sorting
    page: int = Field(1, ge=1, description="Page number")
    page_size: int = Field(20, ge=1, le=100, description="Page size")
    sort_by: str = Field("rating_average", description="Sort field")
    sort_order: str = Field("desc", regex="^(asc|desc)$", description="Sort order")


# Section configuration schemas
class TemplateSectionResponse(BaseModel):
    """Schema for template section response."""
    
    id: uuid.UUID = Field(..., description="Section ID")
    template_id: uuid.UUID = Field(..., description="Template ID")
    section_type: str = Field(..., description="Section type")
    section_name: str = Field(..., description="Display name")
    order_index: int = Field(..., description="Display order")
    is_required: bool = Field(..., description="Required section")
    is_visible: bool = Field(..., description="Visible by default")
    
    # Configuration
    layout_config: Dict[str, Any] = Field(..., description="Section layout config")
    style_config: Dict[str, Any] = Field(..., description="Section style config")
    field_config: Dict[str, Any] = Field(..., description="Field configuration")
    
    class Config:
        from_attributes = True


# Analytics and statistics schemas
class TemplateStatsResponse(BaseModel):
    """Schema for template statistics response."""
    
    total_templates: int = Field(..., description="Total number of templates")
    templates_by_category: Dict[str, int] = Field(..., description="Templates by category")
    templates_by_type: Dict[str, int] = Field(..., description="Templates by type")
    
    # Usage statistics
    total_usage: int = Field(..., description="Total template usage")
    total_downloads: int = Field(..., description="Total downloads")
    most_used_templates: List[Dict[str, Any]] = Field(..., description="Most used templates")
    
    # Rating statistics
    average_rating: float = Field(..., description="Average rating across all templates")
    total_ratings: int = Field(..., description="Total number of ratings")
    top_rated_templates: List[Dict[str, Any]] = Field(..., description="Top rated templates")
    
    # Premium statistics
    premium_templates: int = Field(..., description="Number of premium templates")
    free_templates: int = Field(..., description="Number of free templates")
    total_revenue: Optional[float] = Field(None, description="Total revenue from premium templates")
    
    # Recent activity
    templates_added_this_month: int = Field(..., description="Templates added this month")
    usage_this_month: int = Field(..., description="Usage this month")
    downloads_this_month: int = Field(..., description="Downloads this month")
    
    last_updated: datetime = Field(..., description="Statistics last updated")


# Recommendation schemas
class TemplateRecommendationResponse(BaseModel):
    """Schema for template recommendation response."""
    
    recommended_templates: List[TemplateResponse] = Field(..., description="Recommended templates")
    recommendation_reasons: Dict[str, List[str]] = Field(..., description="Reasons for each recommendation")
    user_preferences: Dict[str, Any] = Field(..., description="User preferences used")
    
    # Personalization factors
    industry_match: Dict[str, float] = Field(..., description="Industry match scores")
    experience_level_match: Dict[str, float] = Field(..., description="Experience level match")
    style_preference_match: Dict[str, float] = Field(..., description="Style preference match")
    
    generated_at: datetime = Field(..., description="Recommendation generation time")


# Export all schemas
__all__ = [
    # Base schemas
    "TemplateBase",
    
    # Request schemas
    "TemplateCreateRequest",
    "TemplateUpdateRequest",
    "TemplateCustomizationRequest",
    "TemplateRatingRequest",
    "TemplateSearchRequest",
    
    # Response schemas
    "TemplateResponse",
    "TemplateListResponse",
    "TemplateCustomizationResponse",
    "TemplatePreviewResponse",
    "TemplateRatingResponse",
    "TemplateSectionResponse",
    "TemplateStatsResponse",
    "TemplateRecommendationResponse"
]