"""
Export service for generating and managing resume exports in various formats.
"""

import logging
import os
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
import uuid

from fastapi import HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy import select, update, and_, desc, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, joinedload

from app.config import settings
from app.exceptions import (
    ResumeNotFoundException, ExportFailedException, UnsupportedExportFormatException,
    ValidationException, TemplateNotFoundException
)
from app.models.resume import Resume, ResumeExport, ProcessingStatus
from app.models.template import ResumeTemplate
from app.models.user import User
from app.schemas.resume import ResumeExportRequest, ResumeExportResponse

logger = logging.getLogger(__name__)


class ExportService:
    """Service for resume export generation and management."""
    
    def __init__(self):
        self.supported_formats = ["pdf", "docx", "json", "html", "txt"]
        self.export_dir = Path(settings.UPLOAD_DIR) / "exports"
        self.export_dir.mkdir(parents=True, exist_ok=True)
    
    async def create_export(
        self,
        session: AsyncSession,
        resume_id: uuid.UUID,
        user_id: uuid.UUID,
        export_data: ResumeExportRequest
    ) -> ResumeExport:
        """
        Create a new resume export.
        
        Args:
            session: Database session
            resume_id: Resume ID to export
            user_id: User ID for ownership check
            export_data: Export configuration
            
        Returns:
            Created export record
        """
        try:
            # Validate export format
            if export_data.export_format not in self.supported_formats:
                raise UnsupportedExportFormatException(
                    export_data.export_format, self.supported_formats
                )
            
            # Get resume with user check
            resume_result = await session.execute(
                select(Resume).where(
                    and_(Resume.id == resume_id, Resume.user_id == user_id)
                )
            )
            resume = resume_result.scalar_one_or_none()
            
            if not resume:
                raise ResumeNotFoundException(str(resume_id))
            
            # Validate template if provided
            template = None
            if export_data.template_id:
                template_result = await session.execute(
                    select(ResumeTemplate).where(ResumeTemplate.id == export_data.template_id)
                )
                template = template_result.scalar_one_or_none()
                
                if not template:
                    raise TemplateNotFoundException(str(export_data.template_id))
                
                # Check if user can use premium template
                user_result = await session.execute(
                    select(User).where(User.id == user_id)
                )
                user = user_result.scalar_one_or_none()
                
                if template.is_premium and not (user and user.is_premium):
                    raise ValidationException("Premium subscription required for this template")
            
            # Create export record
            export_record = ResumeExport(
                resume_id=resume_id,
                user_id=user_id,
                export_format=export_data.export_format,
                template_id=export_data.template_id,
                export_settings=export_data.export_settings or {},
                status=ProcessingStatus.PENDING,
                started_at=datetime.utcnow(),
                expires_at=datetime.utcnow() + timedelta(hours=24)
            )
            
            session.add(export_record)
            await session.flush()

            from app.workers.celery_app import generate_resume_export
            
            # Queue export generation
            generate_resume_export.delay(str(export_record.id))
            
            await session.commit()
            
            logger.info(f"Export created: {export_record.id} for resume {resume_id}")
            return export_record
            
        except Exception as e:
            await session.rollback()
            if isinstance(e, (ResumeNotFoundException, UnsupportedExportFormatException, 
                            TemplateNotFoundException, ValidationException)):
                raise
            logger.error(f"Export creation failed: resume {resume_id}, error: {e}")
            raise ExportFailedException(export_data.export_format, str(e))
    
    async def get_export(
        self,
        session: AsyncSession,
        export_id: uuid.UUID,
        user_id: uuid.UUID
    ) -> ResumeExport:
        """
        Get export by ID with user ownership check.
        
        Args:
            session: Database session
            export_id: Export ID
            user_id: User ID for ownership check
            
        Returns:
            Export record
        """
        try:
            export_result = await session.execute(
                select(ResumeExport)
                .options(
                    joinedload(ResumeExport.resume),
                    joinedload(ResumeExport.template)
                )
                .where(
                    and_(ResumeExport.id == export_id, ResumeExport.user_id == user_id)
                )
            )
            export_record = export_result.scalar_one_or_none()
            
            if not export_record:
                raise ResumeNotFoundException(str(export_id))
            
            return export_record
            
        except Exception as e:
            if isinstance(e, ResumeNotFoundException):
                raise
            logger.error(f"Failed to get export {export_id}: {e}")
            raise ExportFailedException("unknown", str(e))
    
    async def download_export(
        self,
        session: AsyncSession,
        export_id: uuid.UUID,
        user_id: uuid.UUID
    ) -> Optional[FileResponse]:
        """
        Download exported resume file.
        
        Args:
            session: Database session
            export_id: Export ID
            user_id: User ID for ownership check
            
        Returns:
            File response for download
        """
        try:
            export_record = await self.get_export(session, export_id, user_id)
            
            # Check if export is completed
            if export_record.status != ProcessingStatus.COMPLETED:
                raise ExportFailedException(
                    export_record.export_format,
                    f"Export is not ready. Status: {export_record.status}"
                )
            
            # Check if file exists and not expired
            if not export_record.file_path or export_record.is_expired:
                raise ExportFailedException(
                    export_record.export_format,
                    "Export file not found or expired"
                )
            
            file_path = Path(export_record.file_path)
            if not file_path.exists():
                raise ExportFailedException(
                    export_record.export_format,
                    "Export file not found on disk"
                )
            
            # Increment download count
            export_record.increment_download_count()
            await session.commit()
            
            # Determine content type
            content_type = self._get_content_type(export_record.export_format)
            
            # Generate filename
            filename = f"{export_record.resume.title}_{export_record.export_format}_{export_record.created_at.strftime('%Y%m%d')}.{export_record.export_format}"
            
            return FileResponse(
                path=str(file_path),
                filename=filename,
                media_type=content_type
            )
            
        except Exception as e:
            if isinstance(e, (ResumeNotFoundException, ExportFailedException)):
                raise
            logger.error(f"Export download failed: {export_id}, error: {e}")
            raise ExportFailedException("unknown", str(e))
    
    async def get_resume_exports(
        self,
        session: AsyncSession,
        resume_id: uuid.UUID,
        user_id: uuid.UUID,
        limit: int = 10
    ) -> List[ResumeExport]:
        """
        Get all exports for a specific resume.
        
        Args:
            session: Database session
            resume_id: Resume ID
            user_id: User ID for ownership check
            limit: Maximum number of exports
            
        Returns:
            List of exports
        """
        try:
            # Verify resume ownership
            resume_result = await session.execute(
                select(Resume).where(
                    and_(Resume.id == resume_id, Resume.user_id == user_id)
                )
            )
            resume = resume_result.scalar_one_or_none()
            
            if not resume:
                raise ResumeNotFoundException(str(resume_id))
            
            # Get exports
            exports_result = await session.execute(
                select(ResumeExport)
                .options(joinedload(ResumeExport.template))
                .where(ResumeExport.resume_id == resume_id)
                .order_by(desc(ResumeExport.created_at))
                .limit(limit)
            )
            exports = exports_result.scalars().all()
            
            return list(exports)
            
        except Exception as e:
            if isinstance(e, ResumeNotFoundException):
                raise
            logger.error(f"Failed to get resume exports: {resume_id}, error: {e}")
            raise ExportFailedException("unknown", str(e))
    
    async def get_user_exports(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        pagination: Any,
        filters: Dict[str, Any]
    ) -> Tuple[List[ResumeExport], int]:
        """
        Get all exports for a user with filtering.
        
        Args:
            session: Database session
            user_id: User ID
            pagination: Pagination parameters
            filters: Filter criteria
            
        Returns:
            Tuple of (exports, total_count)
        """
        try:
            # Build query with filters
            query = (
                select(ResumeExport)
                .options(
                    joinedload(ResumeExport.resume),
                    joinedload(ResumeExport.template)
                )
                .where(ResumeExport.user_id == user_id)
                .order_by(desc(ResumeExport.created_at))
            )
            
            # Apply filters
            if filters.get("export_format"):
                query = query.where(ResumeExport.export_format == filters["export_format"])
            
            if filters.get("status"):
                query = query.where(ResumeExport.status == filters["status"])
            
            # Get total count
            count_query = select(func.count(ResumeExport.id)).select_from(
                query.subquery()
            )
            total_result = await session.execute(count_query)
            total_count = total_result.scalar()
            
            # Get paginated results
            paginated_query = query.limit(pagination.limit).offset(pagination.offset)
            exports_result = await session.execute(paginated_query)
            exports = exports_result.scalars().all()
            
            return list(exports), total_count
            
        except Exception as e:
            logger.error(f"Failed to get user exports: {user_id}, error: {e}")
            raise ExportFailedException("unknown", str(e))
    
    async def delete_export(
        self,
        session: AsyncSession,
        export_id: uuid.UUID,
        user_id: uuid.UUID
    ) -> bool:
        """
        Delete an export record and file.
        
        Args:
            session: Database session
            export_id: Export ID
            user_id: User ID for ownership check
            
        Returns:
            True if successful
        """
        try:
            export_record = await self.get_export(session, export_id, user_id)
            
            # Delete file if exists
            if export_record.file_path:
                try:
                    file_path = Path(export_record.file_path)
                    if file_path.exists():
                        file_path.unlink()
                except Exception as e:
                    logger.warning(f"Failed to delete export file: {export_record.file_path}, error: {e}")
            
            # Delete record
            await session.delete(export_record)
            await session.commit()
            
            logger.info(f"Export deleted: {export_id}")
            return True
            
        except Exception as e:
            await session.rollback()
            if isinstance(e, ResumeNotFoundException):
                raise
            logger.error(f"Export deletion failed: {export_id}, error: {e}")
            return False
    
    async def bulk_export_resumes(
        self,
        session: AsyncSession,
        resume_ids: List[uuid.UUID],
        user_id: uuid.UUID,
        export_format: str,
        template_id: Optional[uuid.UUID] = None
    ) -> List[ResumeExport]:
        """
        Export multiple resumes in batch.
        
        Args:
            session: Database session
            resume_ids: List of resume IDs
            user_id: User ID
            export_format: Export format
            template_id: Optional template ID
            
        Returns:
            List of created export records
        """
        try:
            # Validate export format
            if export_format not in self.supported_formats:
                raise UnsupportedExportFormatException(export_format, self.supported_formats)
            
            # Validate resume ownership
            resumes_result = await session.execute(
                select(Resume).where(
                    and_(
                        Resume.id.in_(resume_ids),
                        Resume.user_id == user_id,
                        Resume.is_deleted == False
                    )
                )
            )
            resumes = resumes_result.scalars().all()
            
            if len(resumes) != len(resume_ids):
                missing_ids = set(resume_ids) - {r.id for r in resumes}
                raise ValidationException(f"Resumes not found: {missing_ids}")
            
            # Validate template if provided
            if template_id:
                template_result = await session.execute(
                    select(ResumeTemplate).where(ResumeTemplate.id == template_id)
                )
                template = template_result.scalar_one_or_none()
                
                if not template:
                    raise TemplateNotFoundException(str(template_id))
            
            # Create export records
            export_records = []
            for resume in resumes:
                export_record = ResumeExport(
                    resume_id=resume.id,
                    user_id=user_id,
                    export_format=export_format,
                    template_id=template_id,
                    export_settings={},
                    status=ProcessingStatus.PENDING,
                    started_at=datetime.utcnow(),
                    expires_at=datetime.utcnow() + timedelta(hours=24)
                )
                
                session.add(export_record)
                export_records.append(export_record)
            
            await session.flush()

            from app.workers.celery_app import generate_resume_export
            
            # Queue export generation for each
            for export_record in export_records:
                generate_resume_export.delay(str(export_record.id))
            
            await session.commit()
            
            logger.info(f"Bulk export created: {len(export_records)} exports for user {user_id}")
            return export_records
            
        except Exception as e:
            await session.rollback()
            if isinstance(e, (UnsupportedExportFormatException, ValidationException, TemplateNotFoundException)):
                raise
            logger.error(f"Bulk export failed for user {user_id}: {e}")
            raise ExportFailedException(export_format, str(e))
    
    async def generate_template_preview(
        self,
        session: AsyncSession,
        template_id: uuid.UUID,
        resume_id: uuid.UUID,
        user_id: uuid.UUID,
        export_format: str = "pdf"
    ) -> StreamingResponse:
        """
        Generate preview of resume with specific template.
        
        Args:
            session: Database session
            template_id: Template ID
            resume_id: Resume ID
            user_id: User ID
            export_format: Preview format
            
        Returns:
            Preview file response
        """
        try:
            # Get template and resume
            template_result = await session.execute(
                select(ResumeTemplate).where(ResumeTemplate.id == template_id)
            )
            template = template_result.scalar_one_or_none()
            
            resume_result = await session.execute(
                select(Resume).where(
                    and_(Resume.id == resume_id, Resume.user_id == user_id)
                )
            )
            resume = resume_result.scalar_one_or_none()
            
            if not template:
                raise TemplateNotFoundException(str(template_id))
            if not resume:
                raise ResumeNotFoundException(str(resume_id))
            
            # Generate preview (simplified implementation)
            preview_content = await self._generate_preview_content(
                resume, template, export_format
            )
            
            # Return as streaming response
            content_type = self._get_content_type(export_format)
            filename = f"preview_{template.name}_{export_format}"
            
            return StreamingResponse(
                io.BytesIO(preview_content),
                media_type=content_type,
                headers={"Content-Disposition": f"attachment; filename={filename}"}
            )
            
        except Exception as e:
            if isinstance(e, (TemplateNotFoundException, ResumeNotFoundException)):
                raise
            logger.error(f"Template preview failed: template {template_id}, resume {resume_id}, error: {e}")
            raise ExportFailedException(export_format, str(e))
    
    async def get_supported_formats(self, is_premium: bool = False) -> List[Dict[str, Any]]:
        """
        Get list of supported export formats.
        
        Args:
            is_premium: Whether user has premium subscription
            
        Returns:
            List of format information
        """
        formats = [
            {
                "format": "pdf",
                "name": "PDF",
                "description": "Portable Document Format",
                "premium_required": False,
                "features": ["Professional formatting", "Print-ready", "Universal compatibility"]
            },
            {
                "format": "docx",
                "name": "Microsoft Word",
                "description": "Word Document Format",
                "premium_required": False,
                "features": ["Editable format", "Wide compatibility", "Professional layouts"]
            },
            {
                "format": "json",
                "name": "JSON",
                "description": "Structured Data Format",
                "premium_required": True,
                "features": ["Machine readable", "API integration", "Data portability"]
            },
            {
                "format": "html",
                "name": "HTML",
                "description": "Web Page Format",
                "premium_required": is_premium,
                "features": ["Web compatible", "Interactive elements", "Custom styling"]
            },
            {
                "format": "txt",
                "name": "Plain Text",
                "description": "Simple Text Format",
                "premium_required": False,
                "features": ["Universal compatibility", "Small file size", "Basic formatting"]
            }
        ]
        
        # Filter based on premium status
        if not is_premium:
            formats = [f for f in formats if not f["premium_required"]]
        
        return formats
    
    async def get_export_stats(
        self,
        session: AsyncSession,
        user_id: uuid.UUID
    ) -> Dict[str, Any]:
        """
        Get user's export statistics.
        
        Args:
            session: Database session
            user_id: User ID
            
        Returns:
            Export statistics
        """
        try:
            # Total exports
            total_exports = await session.execute(
                select(func.count(ResumeExport.id))
                .where(ResumeExport.user_id == user_id)
            )
            total_exports = total_exports.scalar()
            
            # Exports by format
            exports_by_format = await session.execute(
                select(ResumeExport.export_format, func.count(ResumeExport.id))
                .where(ResumeExport.user_id == user_id)
                .group_by(ResumeExport.export_format)
            )
            format_counts = dict(exports_by_format.fetchall())
            
            # Exports by status
            exports_by_status = await session.execute(
                select(ResumeExport.status, func.count(ResumeExport.id))
                .where(ResumeExport.user_id == user_id)
                .group_by(ResumeExport.status)
            )
            status_counts = dict(exports_by_status.fetchall())
            
            # Recent activity
            week_ago = datetime.utcnow() - timedelta(days=7)
            recent_exports = await session.execute(
                select(func.count(ResumeExport.id))
                .where(
                    and_(
                        ResumeExport.user_id == user_id,
                        ResumeExport.created_at >= week_ago
                    )
                )
            )
            recent_exports = recent_exports.scalar()
            
            # Total downloads
            total_downloads = await session.execute(
                select(func.sum(ResumeExport.download_count))
                .where(ResumeExport.user_id == user_id)
            )
            total_downloads = total_downloads.scalar() or 0
            
            return {
                "total_exports": total_exports,
                "exports_by_format": format_counts,
                "exports_by_status": status_counts,
                "recent_exports": recent_exports,
                "total_downloads": total_downloads,
                "last_updated": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to get export stats for user {user_id}: {e}")
            raise ExportFailedException("unknown", str(e))
    
    async def cleanup_user_expired_exports(
        self,
        session: AsyncSession,
        user_id: uuid.UUID
    ) -> int:
        """
        Clean up user's expired export files.
        
        Args:
            session: Database session
            user_id: User ID
            
        Returns:
            Number of cleaned up exports
        """
        try:
            # Get expired exports
            cutoff_date = datetime.utcnow()
            
            expired_exports = await session.execute(
                select(ResumeExport).where(
                    and_(
                        ResumeExport.user_id == user_id,
                        ResumeExport.expires_at < cutoff_date,
                        ResumeExport.status == ProcessingStatus.COMPLETED
                    )
                )
            )
            
            cleaned_count = 0
            for export in expired_exports.scalars():
                # Delete file if exists
                if export.file_path:
                    try:
                        file_path = Path(export.file_path)
                        if file_path.exists():
                            file_path.unlink()
                    except Exception as e:
                        logger.warning(f"Failed to delete expired export file: {export.file_path}, error: {e}")
                
                # Delete export record
                await session.delete(export)
                cleaned_count += 1
            
            await session.commit()
            
            logger.info(f"Cleaned up {cleaned_count} expired exports for user {user_id}")
            return cleaned_count
            
        except Exception as e:
            await session.rollback()
            logger.error(f"Export cleanup failed for user {user_id}: {e}")
            return 0
    
    async def get_user_export_quota(
        self,
        session: AsyncSession,
        user_id: uuid.UUID
    ) -> Dict[str, Any]:
        """
        Get user's export quota and current usage.
        
        Args:
            session: Database session
            user_id: User ID
            
        Returns:
            Quota information
        """
        try:
            # Get user to check subscription
            user_result = await session.execute(
                select(User).where(User.id == user_id)
            )
            user = user_result.scalar_one_or_none()
            
            if not user:
                raise ValidationException("User not found")
            
            # Define quotas based on subscription
            if user.is_premium:
                daily_limit = 50
                monthly_limit = 500
            else:
                daily_limit = 5
                monthly_limit = 20
            
            # Get current usage
            today = datetime.utcnow().date()
            month_start = today.replace(day=1)
            
            daily_usage = await session.execute(
                select(func.count(ResumeExport.id))
                .where(
                    and_(
                        ResumeExport.user_id == user_id,
                        func.date(ResumeExport.created_at) == today
                    )
                )
            )
            daily_usage = daily_usage.scalar()
            
            monthly_usage = await session.execute(
                select(func.count(ResumeExport.id))
                .where(
                    and_(
                        ResumeExport.user_id == user_id,
                        ResumeExport.created_at >= month_start
                    )
                )
            )
            monthly_usage = monthly_usage.scalar()
            
            return {
                "daily_limit": daily_limit,
                "daily_usage": daily_usage,
                "daily_remaining": max(0, daily_limit - daily_usage),
                "monthly_limit": monthly_limit,
                "monthly_usage": monthly_usage,
                "monthly_remaining": max(0, monthly_limit - monthly_usage),
                "is_premium": user.is_premium,
                "can_export": daily_usage < daily_limit and monthly_usage < monthly_limit
            }
            
        except Exception as e:
            logger.error(f"Failed to get export quota for user {user_id}: {e}")
            raise ExportFailedException("unknown", str(e))
    
    # Private helper methods
    def _get_content_type(self, export_format: str) -> str:
        """Get MIME content type for export format."""
        content_types = {
            "pdf": "application/pdf",
            "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "json": "application/json",
            "html": "text/html",
            "txt": "text/plain"
        }
        return content_types.get(export_format, "application/octet-stream")
    
    async def _generate_preview_content(
        self,
        resume: Resume,
        template: ResumeTemplate,
        export_format: str
    ) -> bytes:
        """Generate preview content for template."""
        # This is a simplified implementation
        # In a real application, you would use proper template rendering
        
        if export_format == "html":
            content = f"""
            <html>
            <head>
                <title>{resume.title} - {template.name}</title>
                <style>{template.css_styles or ''}</style>
            </head>
            <body>
                <h1>Preview: {resume.title}</h1>
                <p>Template: {template.name}</p>
                <div>{resume.raw_text[:500]}...</div>
            </body>
            </html>
            """
            return content.encode('utf-8')
        else:
            # For other formats, return simple text
            content = f"Preview: {resume.title}\nTemplate: {template.name}\n\n{resume.raw_text[:500]}..."
            return content.encode('utf-8')


# Export service
__all__ = ["ExportService"]