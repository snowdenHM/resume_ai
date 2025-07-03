"""
Resume service for managing resume CRUD operations, analysis, and optimization.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
import uuid
import asyncio

from fastapi import UploadFile
from sqlalchemy import select, update, and_, desc, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, joinedload

from app.config import settings
from app.exceptions import (
    ResumeNotFoundException, ResumeQuotaExceededException, 
    ValidationException, AIServiceException, FileProcessingException
)
from app.models.resume import (
    Resume, ResumeSection, ResumeAnalysis, ResumeExport,
    ResumeStatus, ResumeType, ProcessingStatus
)
from app.models.user import User
from app.models.job_description import JobDescription, JobMatch
from app.services.file_service import FileService
from app.services.ai_service import AIService
from app.workers.celery_app import analyze_resume_task, optimize_resume_task

logger = logging.getLogger(__name__)


class ResumeService:
    """Service for resume management and processing."""
    
    def __init__(self):
        self.file_service = FileService()
        self.ai_service = AIService()
    
    async def create_resume(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        title: str,
        description: Optional[str] = None
    ) -> Resume:
        """
        Create a new empty resume.
        
        Args:
            session: Database session
            user_id: User ID
            title: Resume title
            description: Optional description
            
        Returns:
            Created resume
        """
        try:
            # Check user's resume quota
            user = await self._get_user_with_resume_count(session, user_id)
            if not user.can_create_resume():
                max_resumes = 3 if not user.is_premium else settings.MAX_RESUME_VERSIONS
                raise ResumeQuotaExceededException(max_resumes)
            
            # Create resume
            resume = Resume(
                user_id=user_id,
                title=title,
                description=description,
                status=ResumeStatus.DRAFT,
                resume_type=ResumeType.ORIGINAL,
                version="1.0"
            )
            
            session.add(resume)
            await session.flush()
            
            # Create default sections
            await self._create_default_sections(session, resume.id)
            
            await session.commit()
            
            logger.info(f"Resume created: {resume.id} for user {user_id}")
            return resume
            
        except Exception as e:
            await session.rollback()
            if isinstance(e, (ResumeQuotaExceededException, ValidationException)):
                raise
            logger.error(f"Resume creation failed for user {user_id}: {e}")
            raise ValidationException(f"Resume creation failed: {str(e)}")
    
    async def upload_resume(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        file: UploadFile,
        title: str,
        description: Optional[str] = None
    ) -> Resume:
        """
        Upload and parse a resume file.
        
        Args:
            session: Database session
            user_id: User ID
            file: Uploaded resume file
            title: Resume title
            description: Optional description
            
        Returns:
            Created resume with parsed content
        """
        try:
            # Check user's resume quota
            user = await self._get_user_with_resume_count(session, user_id)
            if not user.can_create_resume():
                max_resumes = 3 if not user.is_premium else settings.MAX_RESUME_VERSIONS
                raise ResumeQuotaExceededException(max_resumes)
            
            # Create resume record
            resume = Resume(
                user_id=user_id,
                title=title,
                description=description,
                status=ResumeStatus.PROCESSING,
                resume_type=ResumeType.ORIGINAL,
                version="1.0",
                original_filename=file.filename
            )
            
            session.add(resume)
            await session.flush()
            
            try:
                # Upload and parse file
                file_result = await self.file_service.upload_resume(file, user_id, resume.id)
                
                # Update resume with file information
                resume.file_path = file_result["file_path"]
                resume.file_size = file_result["file_size"]
                resume.file_type = file_result["mime_type"]
                resume.raw_text = file_result["raw_text"]
                resume.structured_data = file_result["structured_data"]
                resume.word_count = file_result["word_count"]
                resume.page_count = file_result["page_count"]
                resume.status = ResumeStatus.COMPLETED
                
                # Extract skills and keywords
                if file_result["structured_data"]:
                    resume.skills = file_result["structured_data"].get("skills", [])
                    resume.keywords = file_result["structured_data"].get("keywords", [])
                
                # Create sections from structured data
                await self._create_sections_from_data(session, resume.id, file_result["structured_data"])
                
                await session.commit()
                
                # Trigger background analysis
                if resume.raw_text:
                    analyze_resume_task.delay(str(resume.id))
                
                logger.info(f"Resume uploaded and parsed: {resume.id} for user {user_id}")
                return resume
                
            except Exception as e:
                # Update resume status to error
                resume.status = ResumeStatus.ERROR
                await session.commit()
                raise FileProcessingException(f"File processing failed: {str(e)}")
                
        except Exception as e:
            await session.rollback()
            if isinstance(e, (ResumeQuotaExceededException, FileProcessingException)):
                raise
            logger.error(f"Resume upload failed for user {user_id}: {e}")
            raise ValidationException(f"Resume upload failed: {str(e)}")
    
    async def get_resume(
        self,
        session: AsyncSession,
        resume_id: uuid.UUID,
        user_id: Optional[uuid.UUID] = None
    ) -> Resume:
        """
        Get resume by ID.
        
        Args:
            session: Database session
            resume_id: Resume ID
            user_id: Optional user ID for ownership check
            
        Returns:
            Resume with sections loaded
        """
        query = (
            select(Resume)
            .options(
                selectinload(Resume.sections),
                selectinload(Resume.analyses),
                joinedload(Resume.template),
                joinedload(Resume.user)
            )
            .where(Resume.id == resume_id)
        )
        
        if user_id:
            query = query.where(Resume.user_id == user_id)
        
        result = await session.execute(query)
        resume = result.scalar_one_or_none()
        
        if not resume:
            raise ResumeNotFoundException(str(resume_id))
        
        return resume
    
    async def get_user_resumes(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        limit: int = 20,
        offset: int = 0,
        status: Optional[ResumeStatus] = None,
        resume_type: Optional[ResumeType] = None
    ) -> Tuple[List[Resume], int]:
        """
        Get user's resumes with pagination.
        
        Args:
            session: Database session
            user_id: User ID
            limit: Number of resumes to return
            offset: Offset for pagination
            status: Optional status filter
            resume_type: Optional type filter
            
        Returns:
            Tuple of (resumes, total_count)
        """
        query = (
            select(Resume)
            .options(selectinload(Resume.sections))
            .where(and_(Resume.user_id == user_id, Resume.is_deleted == False))
            .order_by(desc(Resume.updated_at))
        )
        
        if status:
            query = query.where(Resume.status == status)
        
        if resume_type:
            query = query.where(Resume.resume_type == resume_type)
        
        # Get total count
        count_query = select(func.count(Resume.id)).where(
            and_(Resume.user_id == user_id, Resume.is_deleted == False)
        )
        if status:
            count_query = count_query.where(Resume.status == status)
        if resume_type:
            count_query = count_query.where(Resume.resume_type == resume_type)
        
        total_result = await session.execute(count_query)
        total_count = total_result.scalar()
        
        # Get resumes with pagination
        resumes_result = await session.execute(query.limit(limit).offset(offset))
        resumes = resumes_result.scalars().all()
        
        return list(resumes), total_count
    
    async def update_resume(
        self,
        session: AsyncSession,
        resume_id: uuid.UUID,
        user_id: uuid.UUID,
        title: Optional[str] = None,
        description: Optional[str] = None,
        sections_data: Optional[Dict[str, Any]] = None
    ) -> Resume:
        """
        Update resume information.
        
        Args:
            session: Database session
            resume_id: Resume ID
            user_id: User ID
            title: Optional new title
            description: Optional new description
            sections_data: Optional sections to update
            
        Returns:
            Updated resume
        """
        try:
            resume = await self.get_resume(session, resume_id, user_id)
            
            # Update basic fields
            if title is not None:
                resume.title = title
            if description is not None:
                resume.description = description
            
            # Update sections
            if sections_data:
                await self._update_resume_sections(session, resume_id, sections_data)
            
            await session.commit()
            
            logger.info(f"Resume updated: {resume_id}")
            return resume
            
        except Exception as e:
            await session.rollback()
            if isinstance(e, ResumeNotFoundException):
                raise
            logger.error(f"Resume update failed: {resume_id}, error: {e}")
            raise ValidationException(f"Resume update failed: {str(e)}")
    
    async def delete_resume(
        self,
        session: AsyncSession,
        resume_id: uuid.UUID,
        user_id: uuid.UUID,
        hard_delete: bool = False
    ) -> bool:
        """
        Delete resume (soft delete by default).
        
        Args:
            session: Database session
            resume_id: Resume ID
            user_id: User ID
            hard_delete: Whether to permanently delete
            
        Returns:
            True if successful
        """
        try:
            resume = await self.get_resume(session, resume_id, user_id)
            
            if hard_delete:
                # Delete associated file
                if resume.file_path:
                    await self.file_service.delete_file(resume.file_path)
                
                # Hard delete from database
                await session.delete(resume)
            else:
                # Soft delete
                resume.soft_delete()
            
            await session.commit()
            
            logger.info(f"Resume deleted: {resume_id} (hard={hard_delete})")
            return True
            
        except Exception as e:
            await session.rollback()
            if isinstance(e, ResumeNotFoundException):
                raise
            logger.error(f"Resume deletion failed: {resume_id}, error: {e}")
            return False
    
    async def analyze_resume(
        self,
        session: AsyncSession,
        resume_id: uuid.UUID,
        user_id: uuid.UUID,
        job_description_id: Optional[uuid.UUID] = None,
        analysis_type: str = "general"
    ) -> ResumeAnalysis:
        """
        Analyze resume with AI.
        
        Args:
            session: Database session
            resume_id: Resume ID
            user_id: User ID
            job_description_id: Optional job description for targeted analysis
            analysis_type: Type of analysis
            
        Returns:
            Analysis results
        """
        try:
            resume = await self.get_resume(session, resume_id, user_id)
            
            if not resume.raw_text:
                raise ValidationException("Resume has no text content to analyze")
            
            # Get job description if provided
            job_text = None
            if job_description_id:
                job_result = await session.execute(
                    select(JobDescription).where(
                        and_(
                            JobDescription.id == job_description_id,
                            JobDescription.user_id == user_id
                        )
                    )
                )
                job_description = job_result.scalar_one_or_none()
                if job_description:
                    job_text = job_description.description
            
            # Create analysis record
            analysis = ResumeAnalysis(
                resume_id=resume_id,
                job_description_id=job_description_id,
                analysis_type=analysis_type,
                status=ProcessingStatus.IN_PROGRESS,
                ai_model_used=settings.AI_MODEL
            )
            
            session.add(analysis)
            await session.flush()
            
            try:
                # Perform AI analysis
                ai_result = await self.ai_service.analyze_resume(
                    resume.raw_text, job_text, analysis_type
                )
                
                # Update analysis with results
                analysis.overall_score = ai_result.get("overall_score")
                analysis.ats_score = ai_result.get("ats_score")
                analysis.content_score = ai_result.get("content_score")
                analysis.keyword_score = ai_result.get("keyword_score")
                analysis.format_score = ai_result.get("format_score")
                analysis.strengths = ai_result.get("strengths", [])
                analysis.weaknesses = ai_result.get("weaknesses", [])
                analysis.recommendations = ai_result.get("recommendations", [])
                analysis.missing_keywords = ai_result.get("missing_keywords", [])
                analysis.extracted_skills = ai_result.get("extracted_skills", [])
                analysis.analysis_data = ai_result
                analysis.processing_time = ai_result.get("processing_time")
                analysis.status = ProcessingStatus.COMPLETED
                
                # Update resume scores
                if analysis.overall_score:
                    resume.analysis_score = analysis.overall_score
                if analysis.ats_score:
                    resume.ats_score = analysis.ats_score
                resume.last_analyzed_at = datetime.utcnow()
                
                await session.commit()
                
                logger.info(f"Resume analysis completed: {resume_id}")
                return analysis
                
            except Exception as e:
                analysis.status = ProcessingStatus.FAILED
                analysis.error_message = str(e)
                await session.commit()
                raise AIServiceException(f"Analysis failed: {str(e)}")
                
        except Exception as e:
            await session.rollback()
            if isinstance(e, (ResumeNotFoundException, ValidationException, AIServiceException)):
                raise
            logger.error(f"Resume analysis failed: {resume_id}, error: {e}")
            raise AIServiceException(f"Analysis failed: {str(e)}")
    
    async def optimize_resume(
        self,
        session: AsyncSession,
        resume_id: uuid.UUID,
        user_id: uuid.UUID,
        job_description_id: uuid.UUID,
        optimization_type: str = "full"
    ) -> Resume:
        """
        Optimize resume for specific job description.
        
        Args:
            session: Database session
            resume_id: Resume ID
            user_id: User ID
            job_description_id: Target job description ID
            optimization_type: Type of optimization
            
        Returns:
            Optimized resume (new version)
        """
        try:
            # Get original resume and job description
            original_resume = await self.get_resume(session, resume_id, user_id)
            job_result = await session.execute(
                select(JobDescription).where(
                    and_(
                        JobDescription.id == job_description_id,
                        JobDescription.user_id == user_id
                    )
                )
            )
            job_description = job_result.scalar_one_or_none()
            
            if not job_description:
                raise ValidationException("Job description not found")
            
            if not original_resume.raw_text:
                raise ValidationException("Resume has no content to optimize")
            
            # Create optimized resume version
            optimized_resume = Resume(
                user_id=user_id,
                title=f"{original_resume.title} (Optimized for {job_description.title})",
                description=f"Optimized version for {job_description.company} - {job_description.title}",
                status=ResumeStatus.PROCESSING,
                resume_type=ResumeType.OPTIMIZED,
                parent_resume_id=original_resume.id,
                version=self._get_next_version(original_resume.version),
                template_id=original_resume.template_id
            )
            
            session.add(optimized_resume)
            await session.flush()
            
            try:
                # Perform AI optimization
                ai_result = await self.ai_service.optimize_resume(
                    original_resume.raw_text,
                    job_description.description,
                    optimization_type
                )
                
                # Update optimized resume
                optimized_resume.raw_text = ai_result.get("optimized_content", original_resume.raw_text)
                optimized_resume.structured_data = original_resume.structured_data.copy() if original_resume.structured_data else {}
                optimized_resume.word_count = len(optimized_resume.raw_text.split())
                optimized_resume.page_count = original_resume.page_count
                optimized_resume.status = ResumeStatus.COMPLETED
                
                # Create sections from optimized content
                await self._create_sections_from_data(
                    session, 
                    optimized_resume.id, 
                    optimized_resume.structured_data
                )
                
                await session.commit()
                
                # Trigger background analysis of optimized resume
                analyze_resume_task.delay(str(optimized_resume.id))
                
                logger.info(f"Resume optimized: {resume_id} -> {optimized_resume.id}")
                return optimized_resume
                
            except Exception as e:
                optimized_resume.status = ResumeStatus.ERROR
                await session.commit()
                raise AIServiceException(f"Optimization failed: {str(e)}")
                
        except Exception as e:
            await session.rollback()
            if isinstance(e, (ResumeNotFoundException, ValidationException, AIServiceException)):
                raise
            logger.error(f"Resume optimization failed: {resume_id}, error: {e}")
            raise AIServiceException(f"Optimization failed: {str(e)}")
    
    # Helper Methods
    async def _get_user_with_resume_count(self, session: AsyncSession, user_id: uuid.UUID) -> User:
        """Get user with resume count."""
        result = await session.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        if not user:
            raise ValidationException("User not found")
        return user
    
    async def _create_default_sections(self, session: AsyncSession, resume_id: uuid.UUID) -> None:
        """Create default resume sections."""
        default_sections = [
            ("personal_info", "Personal Information", 1),
            ("summary", "Professional Summary", 2),
            ("experience", "Work Experience", 3),
            ("education", "Education", 4),
            ("skills", "Skills", 5),
        ]
        
        for section_type, title, order in default_sections:
            section = ResumeSection(
                resume_id=resume_id,
                section_type=section_type,
                title=title,
                content="",
                order_index=order
            )
            session.add(section)
    
    async def _create_sections_from_data(
        self,
        session: AsyncSession,
        resume_id: uuid.UUID,
        structured_data: Dict[str, Any]
    ) -> None:
        """Create resume sections from structured data."""
        if not structured_data:
            await self._create_default_sections(session, resume_id)
            return
        
        section_mapping = {
            "personal_info": ("Personal Information", 1),
            "summary": ("Professional Summary", 2),
            "experience": ("Work Experience", 3),
            "education": ("Education", 4),
            "skills": ("Skills", 5),
            "certifications": ("Certifications", 6),
            "projects": ("Projects", 7),
            "achievements": ("Achievements", 8),
            "languages": ("Languages", 9)
        }
        
        for section_key, (title, order) in section_mapping.items():
            if section_key in structured_data and structured_data[section_key]:
                content = self._format_section_content(structured_data[section_key])
                
                section = ResumeSection(
                    resume_id=resume_id,
                    section_type=section_key,
                    title=title,
                    content=content,
                    structured_content=structured_data[section_key] if isinstance(structured_data[section_key], dict) else {},
                    order_index=order
                )
                session.add(section)
    
    def _format_section_content(self, section_data: Any) -> str:
        """Format section data into readable content."""
        if isinstance(section_data, str):
            return section_data
        elif isinstance(section_data, list):
            return "\n".join(f"• {item}" for item in section_data)
        elif isinstance(section_data, dict):
            formatted = []
            for key, value in section_data.items():
                if isinstance(value, list):
                    formatted.append(f"{key.title()}:\n" + "\n".join(f"• {item}" for item in value))
                else:
                    formatted.append(f"{key.title()}: {value}")
            return "\n\n".join(formatted)
        else:
            return str(section_data)
    
    async def _update_resume_sections(
        self,
        session: AsyncSession,
        resume_id: uuid.UUID,
        sections_data: Dict[str, Any]
    ) -> None:
        """Update resume sections."""
        for section_type, content in sections_data.items():
            result = await session.execute(
                select(ResumeSection).where(
                    and_(
                        ResumeSection.resume_id == resume_id,
                        ResumeSection.section_type == section_type
                    )
                )
            )
            section = result.scalar_one_or_none()
            
            if section:
                section.content = content if isinstance(content, str) else self._format_section_content(content)
                section.structured_content = content if isinstance(content, dict) else {}
            else:
                # Create new section
                section = ResumeSection(
                    resume_id=resume_id,
                    section_type=section_type,
                    title=section_type.replace("_", " ").title(),
                    content=content if isinstance(content, str) else self._format_section_content(content),
                    structured_content=content if isinstance(content, dict) else {},
                    order_index=len(sections_data)
                )
                session.add(section)
    
    def _get_next_version(self, current_version: str) -> str:
        """Generate next version number."""
        try:
            major, minor = current_version.split(".")
            return f"{major}.{int(minor) + 1}"
        except:
            return "1.1"


# Export service
__all__ = ["ResumeService"]