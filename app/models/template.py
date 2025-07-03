"""
Resume template related database models.
"""

from enum import Enum
from typing import Optional, List

from sqlalchemy import (
    Column, String, Boolean, DateTime, Integer, Text, Float,
    ForeignKey, Index, CheckConstraint, UniqueConstraint
)
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY
from sqlalchemy.orm import relationship, validates
from sqlalchemy.sql import func

from app.models.base import BaseModel, SoftDeleteModel, create_enum_field, create_json_field


class TemplateCategory(str, Enum):
    """Template category enumeration."""
    MODERN = "modern"
    CLASSIC = "classic"
    CREATIVE = "creative"
    TECHNICAL = "technical"
    EXECUTIVE = "executive"
    ACADEMIC = "academic"
    ENTRY_LEVEL = "entry_level"
    MINIMAL = "minimal"


class TemplateStatus(str, Enum):
    """Template status enumeration."""
    ACTIVE = "active"
    DRAFT = "draft"
    DEPRECATED = "deprecated"
    PREMIUM = "premium"


class TemplateType(str, Enum):
    """Template type enumeration."""
    SYSTEM = "system"
    USER_CREATED = "user_created"
    PREMIUM = "premium"
    CUSTOM = "custom"


class ResumeTemplate(BaseModel):
    """Resume template model."""
    
    __tablename__ = "resume_templates"
    
    # Basic Information
    name = Column(
        String(100),
        nullable=False,
        comment="Template name"
    )
    
    description = Column(
        Text,
        nullable=True,
        comment="Template description"
    )
    
    category = create_enum_field(
        TemplateCategory,
        "category",
        default=TemplateCategory.MODERN,
        comment="Template category"
    )
    
    status = create_enum_field(
        TemplateStatus,
        "status",
        default=TemplateStatus.ACTIVE,
        comment="Template status"
    )
    
    template_type = create_enum_field(
        TemplateType,
        "template_type",
        default=TemplateType.SYSTEM,
        comment="Template type"
    )
    
    # Creator Information
    created_by = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="Template creator (null for system templates)"
    )
    
    # Template Configuration
    layout_config = create_json_field(
        "layout_config",
        default=dict,
        comment="Layout configuration"
    )
    
    style_config = create_json_field(
        "style_config", 
        default=dict,
        comment="Style configuration (colors, fonts, etc.)"
    )
    
    section_config = create_json_field(
        "section_config",
        default=dict,
        comment="Section configuration and ordering"
    )
    
    # Template Assets
    preview_image_url = Column(
        String(500),
        nullable=True,
        comment="Preview image URL"
    )
    
    thumbnail_url = Column(
        String(500),
        nullable=True,
        comment="Thumbnail image URL"
    )
    
    html_template = Column(
        Text,
        nullable=True,
        comment="HTML template content"
    )
    
    css_styles = Column(
        Text,
        nullable=True,
        comment="CSS styles"
    )
    
    # Metadata
    version = Column(
        String(20),
        default="1.0",
        nullable=False,
        comment="Template version"
    )
    
    tags = Column(
        ARRAY(String),
        nullable=True,
        comment="Template tags for filtering"
    )
    
    industries = Column(
        ARRAY(String),
        nullable=True,
        comment="Suitable industries"
    )
    
    job_levels = Column(
        ARRAY(String),
        nullable=True,
        comment="Suitable job levels"
    )
    
    # Features
    supports_photo = Column(
        Boolean,
        default=True,
        nullable=False,
        comment="Supports profile photo"
    )
    
    supports_colors = Column(
        Boolean,
        default=True,
        nullable=False,
        comment="Supports color customization"
    )
    
    supports_fonts = Column(
        Boolean,
        default=True,
        nullable=False,
        comment="Supports font customization"
    )
    
    is_ats_friendly = Column(
        Boolean,
        default=True,
        nullable=False,
        comment="ATS-friendly design"
    )
    
    max_pages = Column(
        Integer,
        default=2,
        nullable=False,
        comment="Maximum recommended pages"
    )
    
    # Pricing (for premium templates)
    is_premium = Column(
        Boolean,
        default=False,
        nullable=False,
        comment="Premium template flag"
    )
    
    price = Column(
        Float,
        nullable=True,
        comment="Template price (if premium)"
    )
    
    currency = Column(
        String(10),
        default="USD",
        nullable=False,
        comment="Price currency"
    )
    
    # Usage Statistics
    usage_count = Column(
        Integer,
        default=0,
        nullable=False,
        comment="Number of times used"
    )
    
    download_count = Column(
        Integer,
        default=0,
        nullable=False,
        comment="Number of downloads"
    )
    
    rating_average = Column(
        Float,
        nullable=True,
        comment="Average user rating (1-5)"
    )
    
    rating_count = Column(
        Integer,
        default=0,
        nullable=False,
        comment="Number of ratings"
    )
    
    # Relationships
    creator = relationship("User")
    resumes = relationship("Resume", back_populates="template")
    ratings = relationship("TemplateRating", back_populates="template", cascade="all, delete-orphan")
    customizations = relationship("TemplateCustomization", back_populates="template", cascade="all, delete-orphan")
    
    # Constraints
    __table_args__ = (
        CheckConstraint("max_pages > 0 AND max_pages <= 10", name="check_max_pages"),
        CheckConstraint("price >= 0", name="check_price"),
        CheckConstraint("rating_average >= 1 AND rating_average <= 5", name="check_rating_average"),
        CheckConstraint("rating_count >= 0", name="check_rating_count"),
        CheckConstraint("usage_count >= 0", name="check_usage_count"),
        CheckConstraint("download_count >= 0", name="check_download_count"),
        Index("idx_template_category_status", "category", "status"),
        Index("idx_template_type_premium", "template_type", "is_premium"),
        Index("idx_template_creator", "created_by"),
        Index("idx_template_rating", "rating_average", "rating_count"),
        Index("idx_template_usage", "usage_count"),
        Index("idx_template_tags", "tags", postgresql_using="gin"),
        Index("idx_template_industries", "industries", postgresql_using="gin"),
    )
    
    @validates("name")
    def validate_name(self, key, name):
        if not name or len(name.strip()) < 1:
            raise ValueError("Template name is required")
        return name.strip()
    
    @validates("version")
    def validate_version(self, key, version):
        if not version:
            return "1.0"
        return version
    
    @validates("currency")
    def validate_currency(self, key, currency):
        valid_currencies = ["USD", "EUR", "GBP", "CAD", "AUD"]
        if currency not in valid_currencies:
            return "USD"
        return currency
    
    @property
    def is_active(self) -> bool:
        """Check if template is active."""
        return self.status == TemplateStatus.ACTIVE
    
    @property
    def is_free(self) -> bool:
        """Check if template is free."""
        return not self.is_premium or (self.price is None or self.price == 0)
    
    @property
    def formatted_price(self) -> str:
        """Get formatted price string."""
        if self.is_free:
            return "Free"
        return f"{self.currency} {self.price:.2f}"
    
    @property
    def rating_stars(self) -> str:
        """Get star rating display."""
        if not self.rating_average:
            return "No ratings"
        return "★" * int(round(self.rating_average)) + "☆" * (5 - int(round(self.rating_average)))
    
    def increment_usage(self):
        """Increment usage count."""
        self.usage_count += 1
    
    def increment_downloads(self):
        """Increment download count."""
        self.download_count += 1
    
    def update_rating(self, new_rating: float):
        """Update average rating with new rating."""
        if self.rating_count == 0:
            self.rating_average = new_rating
            self.rating_count = 1
        else:
            total_rating = self.rating_average * self.rating_count + new_rating
            self.rating_count += 1
            self.rating_average = total_rating / self.rating_count
    
    def __repr__(self) -> str:
        return f"<ResumeTemplate(id={self.id}, name='{self.name}', category='{self.category}')>"


class TemplateRating(BaseModel):
    """Template user ratings."""
    
    __tablename__ = "template_ratings"
    
    template_id = Column(
        UUID(as_uuid=True),
        ForeignKey("resume_templates.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Template ID"
    )
    
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="User who rated"
    )
    
    rating = Column(
        Float,
        nullable=False,
        comment="Rating (1-5)"
    )
    
    review = Column(
        Text,
        nullable=True,
        comment="Written review"
    )
    
    # Relationships
    template = relationship("ResumeTemplate", back_populates="ratings")
    user = relationship("User")
    
    # Constraints
    __table_args__ = (
        CheckConstraint("rating >= 1 AND rating <= 5", name="check_rating_value"),
        UniqueConstraint("template_id", "user_id", name="uq_template_user_rating"),
        Index("idx_rating_template_rating", "template_id", "rating"),
        Index("idx_rating_user", "user_id"),
    )
    
    @validates("rating")
    def validate_rating(self, key, rating):
        if rating < 1 or rating > 5:
            raise ValueError("Rating must be between 1 and 5")
        return rating
    
    def __repr__(self) -> str:
        return f"<TemplateRating(id={self.id}, rating={self.rating}, template_id={self.template_id})>"


class TemplateCustomization(BaseModel):
    """User template customizations."""
    
    __tablename__ = "template_customizations"
    
    template_id = Column(
        UUID(as_uuid=True),
        ForeignKey("resume_templates.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Base template ID"
    )
    
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="User who customized"
    )
    
    name = Column(
        String(100),
        nullable=False,
        comment="Customization name"
    )
    
    # Customization Data
    color_scheme = create_json_field(
        "color_scheme",
        default=dict,
        comment="Custom color scheme"
    )
    
    font_settings = create_json_field(
        "font_settings",
        default=dict,
        comment="Custom font settings"
    )
    
    layout_modifications = create_json_field(
        "layout_modifications",
        default=dict,
        comment="Layout modifications"
    )
    
    section_settings = create_json_field(
        "section_settings",
        default=dict,
        comment="Section-specific settings"
    )
    
    custom_css = Column(
        Text,
        nullable=True,
        comment="Custom CSS overrides"
    )
    
    # Status
    is_active = Column(
        Boolean,
        default=True,
        nullable=False,
        comment="Customization active status"
    )
    
    is_default = Column(
        Boolean,
        default=False,
        nullable=False,
        comment="User's default customization"
    )
    
    # Relationships
    template = relationship("ResumeTemplate", back_populates="customizations")
    user = relationship("User")
    
    # Constraints
    __table_args__ = (
        Index("idx_customization_user_template", "user_id", "template_id"),
        Index("idx_customization_default", "user_id", "is_default"),
    )
    
    @validates("name")
    def validate_name(self, key, name):
        if not name or len(name.strip()) < 1:
            raise ValueError("Customization name is required")
        return name.strip()
    
    def __repr__(self) -> str:
        return f"<TemplateCustomization(id={self.id}, name='{self.name}', user_id={self.user_id})>"


class TemplateSection(BaseModel):
    """Template section definitions."""
    
    __tablename__ = "template_sections"
    
    template_id = Column(
        UUID(as_uuid=True),
        ForeignKey("resume_templates.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Template ID"
    )
    
    section_type = Column(
        String(50),
        nullable=False,
        comment="Section type"
    )
    
    section_name = Column(
        String(100),
        nullable=False,
        comment="Display name"
    )
    
    order_index = Column(
        Integer,
        default=0,
        nullable=False,
        comment="Display order"
    )
    
    is_required = Column(
        Boolean,
        default=False,
        nullable=False,
        comment="Required section"
    )
    
    is_visible = Column(
        Boolean,
        default=True,
        nullable=False,
        comment="Visible by default"
    )
    
    # Section Configuration
    layout_config = create_json_field(
        "layout_config",
        default=dict,
        comment="Section layout configuration"
    )
    
    style_config = create_json_field(
        "style_config",
        default=dict,
        comment="Section style configuration"
    )
    
    field_config = create_json_field(
        "field_config",
        default=dict,
        comment="Field configuration"
    )
    
    # Relationships
    template = relationship("ResumeTemplate")
    
    # Constraints
    __table_args__ = (
        UniqueConstraint("template_id", "section_type", name="uq_template_section_type"),
        Index("idx_section_template_order", "template_id", "order_index"),
        Index("idx_section_type", "section_type"),
    )
    
    @validates("section_type")
    def validate_section_type(self, key, section_type):
        valid_types = [
            "personal_info", "summary", "objective", "experience", "education",
            "skills", "certifications", "projects", "achievements", "languages",
            "references", "publications", "awards", "volunteer", "interests"
        ]
        if section_type not in valid_types:
            raise ValueError(f"Invalid section type: {section_type}")
        return section_type
    
    def __repr__(self) -> str:
        return f"<TemplateSection(id={self.id}, type='{self.section_type}', template_id={self.template_id})>"


# Export all models
__all__ = [
    "ResumeTemplate",
    "TemplateRating",
    "TemplateCustomization", 
    "TemplateSection",
    "TemplateCategory",
    "TemplateStatus",
    "TemplateType"
]