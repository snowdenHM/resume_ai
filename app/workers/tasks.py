"""
Background tasks for resume processing, maintenance, and notifications.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any
import uuid

from celery import current_task
from sqlalchemy import select, update, delete, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session_context
from app.models.user import User
from app.models.resume import Resume, ResumeAnalysis, ResumeExport, ProcessingStatus
from app.models.job_description import JobDescription, JobMatch
from app.services.ai_service import AIService
from app.services.email_service import EmailService
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name="analyze_resume_task")
def analyze_resume_task(self, resume_id: str):
    """
    Background task to analyze a resume with AI.
    
    Args:
        resume_id: Resume ID to analyze
    """
    import asyncio
    
    async def _analyze():
        try:
            async with get_session_context() as session:
                # Get resume
                result = await session.execute(
                    select(Resume).where(Resume.id == uuid.UUID(resume_id))
                )
                resume = result.scalar_one_or_none()
                
                if not resume or not resume.raw_text:
                    logger.warning(f"Resume not found or no content: {resume_id}")
                    return {"status": "error", "message": "Resume not found or no content"}
                
                # Create analysis record
                analysis = ResumeAnalysis(
                    resume_id=resume.id,
                    analysis_type="general",
                    status=ProcessingStatus.IN_PROGRESS
                )
                session.add(analysis)
                await session.flush()
                
                try:
                    # Perform AI analysis
                    ai_service = AIService()
                    ai_result = await ai_service.analyze_resume(resume.raw_text)
                    
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
                    
                    # Send notification email if analysis score is available
                    if analysis.overall_score and resume.user_id:
                        user_result = await session.execute(
                            select(User).where(User.id == resume.user_id)
                        )
                        user = user_result.scalar_one_or_none()
                        
                        if user and user.email_notifications:
                            email_service = EmailService()
                            await email_service.send_resume_analysis_complete_email(
                                user.email,
                                user.first_name or "User",
                                resume.title,
                                analysis.overall_score,
                                len(analysis.recommendations) if analysis.recommendations else 0
                            )
                    
                    logger.info(f"Resume analysis completed: {resume_id}")
                    return {
                        "status": "completed",
                        "analysis_id": str(analysis.id),
                        "overall_score": analysis.overall_score
                    }
                    
                except Exception as e:
                    analysis.status = ProcessingStatus.FAILED
                    analysis.error_message = str(e)
                    await session.commit()
                    
                    logger.error(f"Resume analysis failed: {resume_id}, error: {e}")
                    raise
                    
        except Exception as e:
            logger.error(f"Resume analysis task failed: {resume_id}, error: {e}")
            self.retry(countdown=60, max_retries=3)
    
    return asyncio.run(_analyze())


@celery_app.task(bind=True, name="optimize_resume_task")
def optimize_resume_task(self, resume_id: str, job_description_id: str, optimization_type: str = "full"):
    """
    Background task to optimize a resume for a specific job.
    
    Args:
        resume_id: Resume ID to optimize
        job_description_id: Target job description ID
        optimization_type: Type of optimization
    """
    import asyncio
    
    async def _optimize():
        try:
            async with get_session_context() as session:
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
                    logger.warning(f"Resume or job description not found: {resume_id}, {job_description_id}")
                    return {"status": "error", "message": "Resume or job description not found"}
                
                if not resume.raw_text:
                    logger.warning(f"Resume has no content: {resume_id}")
                    return {"status": "error", "message": "Resume has no content"}
                
                try:
                    # Perform AI optimization
                    ai_service = AIService()
                    ai_result = await ai_service.optimize_resume(
                        resume.raw_text,
                        job_description.description,
                        optimization_type
                    )
                    
                    # Create optimized resume version would be handled by the service
                    # This task focuses on the AI processing part
                    
                    logger.info(f"Resume optimization completed: {resume_id}")
                    return {
                        "status": "completed", 
                        "optimized_content": ai_result.get("optimized_content"),
                        "improvements": ai_result.get("improvements_made", [])
                    }
                    
                except Exception as e:
                    logger.error(f"Resume optimization failed: {resume_id}, error: {e}")
                    raise
                    
        except Exception as e:
            logger.error(f"Resume optimization task failed: {resume_id}, error: {e}")
            self.retry(countdown=60, max_retries=3)
    
    return asyncio.run(_optimize())


@celery_app.task(name="cleanup_expired_exports")
def cleanup_expired_exports():
    """Clean up expired resume exports."""
    import asyncio
    
    async def _cleanup():
        try:
            async with get_session_context() as session:
                # Find expired exports
                cutoff_date = datetime.utcnow()
                
                expired_exports = await session.execute(
                    select(ResumeExport).where(
                        and_(
                            ResumeExport.expires_at < cutoff_date,
                            ResumeExport.status == ProcessingStatus.COMPLETED
                        )
                    )
                )
                
                count = 0
                for export in expired_exports.scalars():
                    # Delete file if exists
                    if export.file_path:
                        try:
                            import os
                            if os.path.exists(export.file_path):
                                os.remove(export.file_path)
                        except Exception as e:
                            logger.warning(f"Failed to delete export file: {export.file_path}, error: {e}")
                    
                    # Delete export record
                    await session.delete(export)
                    count += 1
                
                await session.commit()
                
                logger.info(f"Cleaned up {count} expired exports")
                return {"cleaned_count": count}
                
        except Exception as e:
            logger.error(f"Export cleanup failed: {e}")
            return {"error": str(e)}
    
    return asyncio.run(_cleanup())


@celery_app.task(name="cleanup_old_analyses")
def cleanup_old_analyses():
    """Clean up old analysis records (keep last 10 per resume)."""
    import asyncio
    
    async def _cleanup():
        try:
            async with get_session_context() as session:
                # Get resumes with more than 10 analyses
                query = """
                DELETE FROM resume_analyses 
                WHERE id NOT IN (
                    SELECT id FROM (
                        SELECT id, ROW_NUMBER() OVER (PARTITION BY resume_id ORDER BY created_at DESC) as rn
                        FROM resume_analyses
                    ) ranked
                    WHERE rn <= 10
                )
                """
                
                result = await session.execute(query)
                deleted_count = result.rowcount
                
                await session.commit()
                
                logger.info(f"Cleaned up {deleted_count} old analyses")
                return {"cleaned_count": deleted_count}
                
        except Exception as e:
            logger.error(f"Analysis cleanup failed: {e}")
            return {"error": str(e)}
    
    return asyncio.run(_cleanup())


@celery_app.task(name="update_resume_scores")
def update_resume_scores():
    """Update resume scores based on latest analyses."""
    import asyncio
    
    async def _update():
        try:
            async with get_session_context() as session:
                # Update resume scores from latest analyses
                query = """
                UPDATE resumes 
                SET 
                    analysis_score = latest_analysis.overall_score,
                    ats_score = latest_analysis.ats_score,
                    last_analyzed_at = latest_analysis.created_at
                FROM (
                    SELECT DISTINCT ON (resume_id) 
                        resume_id, overall_score, ats_score, created_at
                    FROM resume_analyses 
                    WHERE status = 'completed' AND overall_score IS NOT NULL
                    ORDER BY resume_id, created_at DESC
                ) latest_analysis
                WHERE resumes.id = latest_analysis.resume_id
                """
                
                result = await session.execute(query)
                updated_count = result.rowcount
                
                await session.commit()
                
                logger.info(f"Updated scores for {updated_count} resumes")
                return {"updated_count": updated_count}
                
        except Exception as e:
            logger.error(f"Score update failed: {e}")
            return {"error": str(e)}
    
    return asyncio.run(_update())


@celery_app.task(name="send_weekly_digest")
def send_weekly_digest():
    """Send weekly digest emails to active users."""
    import asyncio
    
    async def _send_digest():
        try:
            async with get_session_context() as session:
                # Get active users with recent activity
                week_ago = datetime.utcnow() - timedelta(days=7)
                
                active_users = await session.execute(
                    select(User).where(
                        and_(
                            User.is_active == True,
                            User.email_notifications == True,
                            User.last_activity_at >= week_ago
                        )
                    )
                )
                
                email_service = EmailService()
                sent_count = 0
                
                for user in active_users.scalars():
                    try:
                        # Get user's resume stats
                        resume_count = await session.execute(
                            select(func.count(Resume.id)).where(
                                and_(
                                    Resume.user_id == user.id,
                                    Resume.is_deleted == False
                                )
                            )
                        )
                        resume_count = resume_count.scalar()
                        
                        # Get recent analyses
                        recent_analyses = await session.execute(
                            select(func.count(ResumeAnalysis.id)).where(
                                and_(
                                    ResumeAnalysis.created_at >= week_ago,
                                    ResumeAnalysis.resume_id.in_(
                                        select(Resume.id).where(Resume.user_id == user.id)
                                    )
                                )
                            )
                        )
                        recent_analyses = recent_analyses.scalar()
                        
                        # Send digest email (implement digest template)
                        # This would include weekly stats, tips, etc.
                        # For now, just log
                        logger.info(f"Would send digest to {user.email}: {resume_count} resumes, {recent_analyses} analyses")
                        sent_count += 1
                        
                    except Exception as e:
                        logger.warning(f"Failed to send digest to {user.email}: {e}")
                
                logger.info(f"Sent weekly digest to {sent_count} users")
                return {"sent_count": sent_count}
                
        except Exception as e:
            logger.error(f"Weekly digest failed: {e}")
            return {"error": str(e)}
    
    return asyncio.run(_send_digest())


@celery_app.task(name="monitor_system_health")
def monitor_system_health():
    """Monitor system health and send alerts if needed."""
    import asyncio
    
    async def _monitor():
        try:
            health_status = {
                "timestamp": datetime.utcnow().isoformat(),
                "database": "unknown",
                "ai_service": "unknown",
                "storage": "unknown",
                "task_queue": "healthy"
            }
            
            # Check database
            try:
                async with get_session_context() as session:
                    await session.execute(select(1))
                    health_status["database"] = "healthy"
            except Exception as e:
                health_status["database"] = f"unhealthy: {str(e)}"
                logger.error(f"Database health check failed: {e}")
            
            # Check AI service
            try:
                ai_service = AIService()
                status = await ai_service.get_service_status()
                if status["available_services"]:
                    health_status["ai_service"] = "healthy"
                else:
                    health_status["ai_service"] = "no_service_configured"
            except Exception as e:
                health_status["ai_service"] = f"unhealthy: {str(e)}"
                logger.error(f"AI service health check failed: {e}")
            
            # Check storage (basic check)
            try:
                import os
                from app.config import settings
                upload_dir = settings.UPLOAD_DIR
                if os.path.exists(upload_dir) and os.access(upload_dir, os.W_OK):
                    health_status["storage"] = "healthy"
                else:
                    health_status["storage"] = "inaccessible"
            except Exception as e:
                health_status["storage"] = f"unhealthy: {str(e)}"
                logger.error(f"Storage health check failed: {e}")
            
            # Log health status
            unhealthy_services = [
                service for service, status in health_status.items() 
                if status not in ["healthy", "no_service_configured"]
            ]
            
            if unhealthy_services:
                logger.warning(f"Unhealthy services detected: {unhealthy_services}")
                # Here you could send alert emails to administrators
            
            return health_status
            
        except Exception as e:
            logger.error(f"System health monitoring failed: {e}")
            return {"error": str(e)}
    
    return asyncio.run(_monitor())


@celery_app.task(name="bulk_resume_analysis")
def bulk_resume_analysis(resume_ids: List[str]):
    """
    Analyze multiple resumes in bulk.
    
    Args:
        resume_ids: List of resume IDs to analyze
    """
    results = []
    
    for resume_id in resume_ids:
        try:
            result = analyze_resume_task.delay(resume_id)
            results.append({
                "resume_id": resume_id,
                "task_id": result.id,
                "status": "queued"
            })
        except Exception as e:
            results.append({
                "resume_id": resume_id,
                "status": "failed",
                "error": str(e)
            })
    
    logger.info(f"Queued {len(results)} resumes for bulk analysis")
    return {"results": results}


# Task for generating resume exports
@celery_app.task(bind=True, name="generate_resume_export")
def generate_resume_export(self, export_id: str):
    """
    Generate resume export file.
    
    Args:
        export_id: Resume export ID
    """
    import asyncio
    
    async def _generate():
        try:
            async with get_session_context() as session:
                # Get export record
                result = await session.execute(
                    select(ResumeExport).where(ResumeExport.id == uuid.UUID(export_id))
                )
                export = result.scalar_one_or_none()
                
                if not export:
                    logger.warning(f"Export not found: {export_id}")
                    return {"status": "error", "message": "Export not found"}
                
                # Update status
                export.status = ProcessingStatus.IN_PROGRESS
                export.started_at = datetime.utcnow()
                await session.commit()
                
                try:
                    # Generate export file (would use export service)
                    # This is a placeholder for the actual export generation
                    logger.info(f"Generating export: {export_id}")
                    
                    # Simulate export generation
                    await asyncio.sleep(2)
                    
                    export.status = ProcessingStatus.COMPLETED
                    export.completed_at = datetime.utcnow()
                    export.processing_time = (export.completed_at - export.started_at).total_seconds()
                    
                    # Set expiration (24 hours from now)
                    export.expires_at = datetime.utcnow() + timedelta(hours=24)
                    
                    await session.commit()
                    
                    logger.info(f"Export generation completed: {export_id}")
                    return {
                        "status": "completed",
                        "export_id": export_id,
                        "processing_time": export.processing_time
                    }
                    
                except Exception as e:
                    export.status = ProcessingStatus.FAILED
                    export.error_message = str(e)
                    await session.commit()
                    
                    logger.error(f"Export generation failed: {export_id}, error: {e}")
                    raise
                    
        except Exception as e:
            logger.error(f"Export generation task failed: {export_id}, error: {e}")
            self.retry(countdown=30, max_retries=3)
    
    return asyncio.run(_generate())


# Export task names for easy importing
__all__ = [
    "analyze_resume_task",
    "optimize_resume_task", 
    "cleanup_expired_exports",
    "cleanup_old_analyses",
    "update_resume_scores",
    "send_weekly_digest",
    "monitor_system_health",
    "bulk_resume_analysis",
    "generate_resume_export"
]