"""
Celery background tasks for resume analysis, optimization, and export.
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
import uuid
import asyncio

from celery import Celery
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession

from app.config import settings
from app.models.resume import Resume, ResumeAnalysis, ResumeExport, ProcessingStatus
from app.models.job_description import JobDescription
from app.services.ai_service import AIService
from app.services.export_service import ExportService

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create Celery app
celery_app = Celery(
    "resume_builder",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.workers.tasks"]
)

# Celery configuration
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutes
    task_soft_time_limit=25 * 60,  # 25 minutes
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
)

# Create async database engine for tasks
engine = create_async_engine(settings.DATABASE_URL)

async def get_async_session():
    """Get async database session for tasks."""
    async with AsyncSession(engine) as session:
        try:
            yield session
        finally:
            await session.close()


@celery_app.task(bind=True, name="analyze_resume_task")
def analyze_resume_task(self, resume_id: str, job_description_id: Optional[str] = None):
    """
    Background task to analyze a resume.
    
    Args:
        resume_id: Resume ID to analyze
        job_description_id: Optional job description ID for targeted analysis
    """
    try:
        # Run async analysis in sync context
        result = asyncio.run(_analyze_resume_async(resume_id, job_description_id))
        return result
        
    except Exception as e:
        logger.error(f"Resume analysis task failed: {resume_id}, error: {e}")
        # Update analysis status to failed
        asyncio.run(_update_analysis_status(resume_id, ProcessingStatus.FAILED, str(e)))
        raise self.retry(exc=e, countdown=60, max_retries=3)


@celery_app.task(bind=True, name="optimize_resume_task")
def optimize_resume_task(self, resume_id: str, job_description_id: str, optimization_type: str = "full"):
    """
    Background task to optimize a resume for a specific job.
    
    Args:
        resume_id: Resume ID to optimize
        job_description_id: Target job description ID
        optimization_type: Type of optimization
    """
    try:
        result = asyncio.run(_optimize_resume_async(resume_id, job_description_id, optimization_type))
        return result
        
    except Exception as e:
        logger.error(f"Resume optimization task failed: {resume_id}, error: {e}")
        raise self.retry(exc=e, countdown=60, max_retries=3)


@celery_app.task(bind=True, name="generate_resume_export")
def generate_resume_export(self, export_id: str):
    """
    Background task to generate resume export.
    
    Args:
        export_id: Export ID to process
    """
    try:
        result = asyncio.run(_generate_export_async(export_id))
        return result
        
    except Exception as e:
        logger.error(f"Resume export task failed: {export_id}, error: {e}")
        # Update export status to failed
        asyncio.run(_update_export_status(export_id, ProcessingStatus.FAILED, str(e)))
        raise self.retry(exc=e, countdown=60, max_retries=3)


@celery_app.task(bind=True, name="bulk_resume_analysis")
def bulk_resume_analysis(self, resume_ids: List[str], analysis_type: str = "general"):
    """
    Background task for bulk resume analysis.
    
    Args:
        resume_ids: List of resume IDs to analyze
        analysis_type: Type of analysis
    """
    try:
        results = []
        for resume_id in resume_ids:
            try:
                result = asyncio.run(_analyze_resume_async(resume_id, None, analysis_type))
                results.append({"resume_id": resume_id, "status": "completed", "result": result})
            except Exception as e:
                logger.error(f"Bulk analysis failed for resume {resume_id}: {e}")
                results.append({"resume_id": resume_id, "status": "failed", "error": str(e)})
        
        return {
            "total_processed": len(resume_ids),
            "successful": len([r for r in results if r["status"] == "completed"]),
            "failed": len([r for r in results if r["status"] == "failed"]),
            "results": results
        }
        
    except Exception as e:
        logger.error(f"Bulk analysis task failed: {e}")
        raise self.retry(exc=e, countdown=60, max_retries=2)


@celery_app.task(bind=True, name="analyze_job_description_task")
def analyze_job_description_task(self, job_id: str):
    """
    Background task to analyze a job description.
    
    Args:
        job_id: Job description ID to analyze
    """
    try:
        result = asyncio.run(_analyze_job_description_async(job_id))
        return result
        
    except Exception as e:
        logger.error(f"Job description analysis task failed: {job_id}, error: {e}")
        raise self.retry(exc=e, countdown=60, max_retries=3)


@celery_app.task(bind=True, name="extract_job_from_url_task")
def extract_job_from_url_task(self, url: str, user_id: str):
    """
    Background task to extract job information from URL.
    
    Args:
        url: Job posting URL
        user_id: User ID
    """
    try:
        result = asyncio.run(_extract_job_from_url_async(url, user_id))
        return result
        
    except Exception as e:
        logger.error(f"Job URL extraction task failed: {url}, error: {e}")
        raise self.retry(exc=e, countdown=60, max_retries=2)


@celery_app.task(bind=True, name="cleanup_expired_exports")
def cleanup_expired_exports(self):
    """
    Periodic task to clean up expired exports.
    """
    try:
        result = asyncio.run(_cleanup_expired_exports_async())
        logger.info(f"Cleanup completed: {result}")
        return result
        
    except Exception as e:
        logger.error(f"Export cleanup task failed: {e}")
        raise


@celery_app.task(bind=True, name="send_analysis_notification")
def send_analysis_notification(self, user_email: str, user_name: str, resume_title: str, analysis_score: float):
    """
    Background task to send analysis completion notification.
    
    Args:
        user_email: User email address
        user_name: User name
        resume_title: Resume title
        analysis_score: Analysis score
    """
    try:
        from app.services.email_service import EmailService
        email_service = EmailService()
        
        result = asyncio.run(
            email_service.send_resume_analysis_complete_email(
                user_email, user_name, resume_title, analysis_score, 5  # mock recommendations count
            )
        )
        return {"email_sent": result, "recipient": user_email}
        
    except Exception as e:
        logger.error(f"Notification task failed: {user_email}, error: {e}")
        raise


# Async helper functions

async def _analyze_resume_async(resume_id: str, job_description_id: Optional[str] = None, analysis_type: str = "general"):
    """Async helper for resume analysis."""
    async with AsyncSession(engine) as session:
        try:
            # Get resume
            resume_result = await session.execute(
                select(Resume).where(Resume.id == uuid.UUID(resume_id))
            )
            resume = resume_result.scalar_one_or_none()
            
            if not resume:
                raise ValueError(f"Resume not found: {resume_id}")
            
            if not resume.raw_text:
                raise ValueError("Resume has no content to analyze")
            
            # Get job description if provided
            job_text = None
            if job_description_id:
                job_result = await session.execute(
                    select(JobDescription).where(JobDescription.id == uuid.UUID(job_description_id))
                )
                job_description = job_result.scalar_one_or_none()
                if job_description:
                    job_text = job_description.description
            
            # Create or get analysis record
            analysis_result = await session.execute(
                select(ResumeAnalysis).where(
                    ResumeAnalysis.resume_id == uuid.UUID(resume_id)
                ).order_by(ResumeAnalysis.created_at.desc())
            )
            analysis = analysis_result.scalar_one_or_none()
            
            if not analysis:
                analysis = ResumeAnalysis(
                    resume_id=uuid.UUID(resume_id),
                    job_description_id=uuid.UUID(job_description_id) if job_description_id else None,
                    analysis_type=analysis_type,
                    status=ProcessingStatus.IN_PROGRESS
                )
                session.add(analysis)
                await session.flush()
            
            # Perform AI analysis
            ai_service = AIService()
            ai_result = await ai_service.analyze_resume(resume.raw_text, job_text, analysis_type)
            
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
            analysis.ai_model_used = ai_result.get("ai_provider", "unknown")
            analysis.status = ProcessingStatus.COMPLETED
            
            # Update resume scores
            if analysis.overall_score:
                resume.analysis_score = analysis.overall_score
            if analysis.ats_score:
                resume.ats_score = analysis.ats_score
            resume.last_analyzed_at = datetime.utcnow()
            
            await session.commit()
            
            logger.info(f"Resume analysis completed: {resume_id}")
            return {
                "analysis_id": str(analysis.id),
                "overall_score": analysis.overall_score,
                "status": "completed"
            }
            
        except Exception as e:
            await session.rollback()
            logger.error(f"Resume analysis failed: {resume_id}, error: {e}")
            raise


async def _optimize_resume_async(resume_id: str, job_description_id: str, optimization_type: str):
    """Async helper for resume optimization."""
    async with AsyncSession(engine) as session:
        try:
            # Get resume and job description
            resume_result = await session.execute(
                select(Resume).where(Resume.id == uuid.UUID(resume_id))
            )
            resume = resume_result.scalar_one_or_none()
            
            job_result = await session.execute(
                select(JobDescription).where(JobDescription.id == uuid.UUID(job_description_id))
            )
            job_description = job_result.scalar_one_or_none()
            
            if not resume or not job_description:
                raise ValueError("Resume or job description not found")
            
            # Perform AI optimization
            ai_service = AIService()
            optimization_result = await ai_service.optimize_resume(
                resume.raw_text,
                job_description.description,
                optimization_type
            )
            
            # Create optimized resume version
            optimized_resume = Resume(
                user_id=resume.user_id,
                title=f"{resume.title} (Optimized for {job_description.title})",
                description=f"Optimized version for {job_description.company} - {job_description.title}",
                status=resume.status,
                resume_type="optimized",
                parent_resume_id=resume.id,
                version=_get_next_version(resume.version),
                raw_text=optimization_result.get("optimized_content", resume.raw_text),
                structured_data=resume.structured_data.copy() if resume.structured_data else {},
                word_count=len(optimization_result.get("optimized_content", "").split()),
                page_count=resume.page_count
            )
            
            session.add(optimized_resume)
            await session.commit()
            
            logger.info(f"Resume optimization completed: {resume_id} -> {optimized_resume.id}")
            return {
                "optimized_resume_id": str(optimized_resume.id),
                "improvements": optimization_result.get("improvements_made", []),
                "status": "completed"
            }
            
        except Exception as e:
            await session.rollback()
            logger.error(f"Resume optimization failed: {resume_id}, error: {e}")
            raise


async def _generate_export_async(export_id: str):
    """Async helper for export generation."""
    async with AsyncSession(engine) as session:
        try:
            # Get export record
            export_result = await session.execute(
                select(ResumeExport).where(ResumeExport.id == uuid.UUID(export_id))
            )
            export_record = export_result.scalar_one_or_none()
            
            if not export_record:
                raise ValueError(f"Export record not found: {export_id}")
            
            export_record.status = ProcessingStatus.IN_PROGRESS
            export_record.started_at = datetime.utcnow()
            
            # Get resume
            resume_result = await session.execute(
                select(Resume).where(Resume.id == export_record.resume_id)
            )
            resume = resume_result.scalar_one_or_none()
            
            if not resume:
                raise ValueError("Resume not found for export")
            
            # Generate export file (simplified implementation)
            export_service = ExportService()
            file_path = await _generate_export_file(
                resume, 
                export_record.export_format,
                export_record.export_settings
            )
            
            # Update export record
            export_record.file_path = str(file_path)
            export_record.file_size = file_path.stat().st_size if file_path.exists() else 0
            export_record.status = ProcessingStatus.COMPLETED
            export_record.completed_at = datetime.utcnow()
            export_record.processing_time = (
                export_record.completed_at - export_record.started_at
            ).total_seconds()
            
            await session.commit()
            
            logger.info(f"Resume export completed: {export_id}")
            return {
                "export_id": export_id,
                "file_path": str(file_path),
                "status": "completed"
            }
            
        except Exception as e:
            await session.rollback()
            logger.error(f"Resume export failed: {export_id}, error: {e}")
            raise


async def _analyze_job_description_async(job_id: str):
    """Async helper for job description analysis."""
    async with AsyncSession(engine) as session:
        try:
            # Get job description
            job_result = await session.execute(
                select(JobDescription).where(JobDescription.id == uuid.UUID(job_id))
            )
            job_description = job_result.scalar_one_or_none()
            
            if not job_description:
                raise ValueError(f"Job description not found: {job_id}")
            
            # Perform AI analysis
            ai_service = AIService()
            analysis_result = await ai_service.extract_job_requirements(job_description.description)
            
            # Update job description with analysis results
            if analysis_result.get("required_skills"):
                job_description.required_skills = analysis_result["required_skills"]
            
            if analysis_result.get("preferred_skills"):
                job_description.preferred_skills = analysis_result["preferred_skills"]
            
            if analysis_result.get("keywords"):
                job_description.keywords = analysis_result["keywords"]
            
            job_description.structured_data = analysis_result
            job_description.analysis_score = analysis_result.get("completeness_score", 0)
            job_description.complexity_score = analysis_result.get("clarity_score", 0)
            job_description.last_analyzed_at = datetime.utcnow()
            
            await session.commit()
            
            logger.info(f"Job description analysis completed: {job_id}")
            return {
                "job_id": job_id,
                "analysis_score": job_description.analysis_score,
                "status": "completed"
            }
            
        except Exception as e:
            await session.rollback()
            logger.error(f"Job description analysis failed: {job_id}, error: {e}")
            raise


async def _extract_job_from_url_async(url: str, user_id: str):
    """Async helper for job URL extraction."""
    # Simplified implementation - in production, use web scraping
    return {
        "url": url,
        "extracted_data": {
            "title": "Extracted Job Title",
            "company": "Extracted Company",
            "description": "Extracted job description...",
            "location": "Remote"
        },
        "status": "completed"
    }


async def _cleanup_expired_exports_async():
    """Async helper for cleaning up expired exports."""
    async with AsyncSession(engine) as session:
        try:
            from pathlib import Path
            
            # Get expired exports
            cutoff_date = datetime.utcnow()
            
            expired_exports = await session.execute(
                select(ResumeExport).where(
                    ResumeExport.expires_at < cutoff_date,
                    ResumeExport.status == ProcessingStatus.COMPLETED
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
            
            return {"cleaned_exports": cleaned_count}
            
        except Exception as e:
            await session.rollback()
            logger.error(f"Export cleanup failed: {e}")
            raise


async def _update_analysis_status(resume_id: str, status: ProcessingStatus, error_message: Optional[str] = None):
    """Update analysis status."""
    async with AsyncSession(engine) as session:
        try:
            analysis_result = await session.execute(
                select(ResumeAnalysis).where(
                    ResumeAnalysis.resume_id == uuid.UUID(resume_id)
                ).order_by(ResumeAnalysis.created_at.desc())
            )
            analysis = analysis_result.scalar_one_or_none()
            
            if analysis:
                analysis.status = status
                if error_message:
                    analysis.error_message = error_message
                await session.commit()
                
        except Exception as e:
            logger.error(f"Failed to update analysis status: {e}")


async def _update_export_status(export_id: str, status: ProcessingStatus, error_message: Optional[str] = None):
    """Update export status."""
    async with AsyncSession(engine) as session:
        try:
            export_result = await session.execute(
                select(ResumeExport).where(ResumeExport.id == uuid.UUID(export_id))
            )
            export_record = export_result.scalar_one_or_none()
            
            if export_record:
                export_record.status = status
                if error_message:
                    export_record.error_message = error_message
                await session.commit()
                
        except Exception as e:
            logger.error(f"Failed to update export status: {e}")


# Helper functions

async def _generate_export_file(resume: Resume, export_format: str, export_settings: Dict[str, Any]):
    """Generate export file (simplified implementation)."""
    from pathlib import Path
    import tempfile
    
    # Create temporary file
    with tempfile.NamedTemporaryFile(
        mode='w', 
        suffix=f'.{export_format}', 
        delete=False
    ) as temp_file:
        if export_format == "txt":
            temp_file.write(resume.raw_text or "")
        elif export_format == "json":
            import json
            export_data = {
                "title": resume.title,
                "content": resume.raw_text,
                "structured_data": resume.structured_data,
                "created_at": resume.created_at.isoformat()
            }
            json.dump(export_data, temp_file, indent=2)
        else:
            # For PDF/DOCX, would use proper libraries
            temp_file.write(f"Export format {export_format} - {resume.title}\n\n{resume.raw_text or ''}")
        
        return Path(temp_file.name)


def _get_next_version(current_version: str) -> str:
    """Generate next version number."""
    try:
        major, minor = current_version.split(".")
        return f"{major}.{int(minor) + 1}"
    except:
        return "1.1"


# Periodic tasks setup
@celery_app.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    """Setup periodic tasks."""
    
    # Clean up expired exports daily at 2 AM
    sender.add_periodic_task(
        24 * 60 * 60,  # 24 hours
        cleanup_expired_exports.s(),
        name="cleanup_expired_exports_daily"
    )


# Export tasks
__all__ = [
    "analyze_resume_task",
    "optimize_resume_task", 
    "generate_resume_export",
    "bulk_resume_analysis",
    "analyze_job_description_task",
    "extract_job_from_url_task",
    "cleanup_expired_exports",
    "send_analysis_notification"
]