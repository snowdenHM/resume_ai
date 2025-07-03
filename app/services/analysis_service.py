"""
Analysis service for AI-powered resume analysis, insights, and trends.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
import uuid
import asyncio

from sqlalchemy import select, update, and_, desc, func, asc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, joinedload

from app.config import settings
from app.exceptions import (
    ResumeNotFoundException, JobDescriptionNotFoundException, AIServiceException,
    ValidationException, AnalysisNotFoundException
)
from app.models.resume import Resume, ResumeAnalysis, ProcessingStatus
from app.models.job_description import JobDescription, JobMatch
from app.models.user import User
from app.schemas.analysis import (
    AnalysisResponse, AnalysisListResponse, AnalysisComparisonResponse,
    AnalysisInsightsResponse, AnalysisTrendsResponse, BatchAnalysisRequest,
    BatchAnalysisResponse, AnalysisReportRequest, AnalysisReportResponse
)
from app.services.ai_service import AIService
from app.workers.celery_app import analyze_resume_task, bulk_resume_analysis

logger = logging.getLogger(__name__)


class AnalysisService:
    """Service for AI-powered resume analysis and insights."""
    
    def __init__(self):
        self.ai_service = AIService()
    
    async def analyze_resume(
        self,
        session: AsyncSession,
        resume_id: uuid.UUID,
        user_id: uuid.UUID,
        analysis_type: str = "comprehensive",
        job_description_id: Optional[uuid.UUID] = None,
        include_suggestions: bool = True
    ) -> AnalysisResponse:
        """
        Perform AI analysis of a resume.
        
        Args:
            session: Database session
            resume_id: Resume ID to analyze
            user_id: User ID for ownership check
            analysis_type: Type of analysis
            job_description_id: Optional job description for targeted analysis
            include_suggestions: Whether to include improvement suggestions
            
        Returns:
            Analysis results
        """
        try:
            # Get resume with user check
            resume_result = await session.execute(
                select(Resume).where(
                    and_(Resume.id == resume_id, Resume.user_id == user_id)
                )
            )
            resume = resume_result.scalar_one_or_none()
            
            if not resume:
                raise ResumeNotFoundException(str(resume_id))
            
            if not resume.raw_text:
                raise ValidationException("Resume has no content to analyze")
            
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
                else:
                    raise JobDescriptionNotFoundException(str(job_description_id))
            
            # Create analysis record
            analysis = ResumeAnalysis(
                resume_id=resume_id,
                job_description_id=job_description_id,
                analysis_type=analysis_type,
                status=ProcessingStatus.IN_PROGRESS
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
                analysis.recommendations = ai_result.get("recommendations", []) if include_suggestions else []
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
                return AnalysisResponse.from_orm(analysis)
                
            except Exception as e:
                analysis.status = ProcessingStatus.FAILED
                analysis.error_message = str(e)
                await session.commit()
                raise AIServiceException(f"Analysis failed: {str(e)}")
                
        except Exception as e:
            await session.rollback()
            if isinstance(e, (ResumeNotFoundException, JobDescriptionNotFoundException, AIServiceException)):
                raise
            logger.error(f"Resume analysis failed: {resume_id}, error: {e}")
            raise AIServiceException(f"Analysis failed: {str(e)}")
    
    async def analyze_job_match(
        self,
        session: AsyncSession,
        resume_id: uuid.UUID,
        job_id: uuid.UUID,
        user_id: uuid.UUID,
        detailed_analysis: bool = True
    ) -> AnalysisResponse:
        """
        Analyze compatibility between resume and job description.
        
        Args:
            session: Database session
            resume_id: Resume ID
            job_id: Job description ID
            user_id: User ID for ownership check
            detailed_analysis: Include detailed matching analysis
            
        Returns:
            Match analysis results
        """
        try:
            # Get resume and job description
            resume_result = await session.execute(
                select(Resume).where(
                    and_(Resume.id == resume_id, Resume.user_id == user_id)
                )
            )
            resume = resume_result.scalar_one_or_none()
            
            job_result = await session.execute(
                select(JobDescription).where(
                    and_(JobDescription.id == job_id, JobDescription.user_id == user_id)
                )
            )
            job_description = job_result.scalar_one_or_none()
            
            if not resume:
                raise ResumeNotFoundException(str(resume_id))
            if not job_description:
                raise JobDescriptionNotFoundException(str(job_id))
            
            if not resume.raw_text:
                raise ValidationException("Resume has no content to analyze")
            
            # Create job match analysis
            analysis = ResumeAnalysis(
                resume_id=resume_id,
                job_description_id=job_id,
                analysis_type="job_match",
                status=ProcessingStatus.IN_PROGRESS
            )
            
            session.add(analysis)
            await session.flush()
            
            try:
                # Perform AI job matching
                match_result = await self.ai_service.match_resume_to_job(
                    resume.raw_text,
                    job_description.description
                )
                
                # Update analysis with match results
                analysis.overall_score = match_result.get("overall_match_score")
                analysis.analysis_data = match_result
                analysis.processing_time = match_result.get("processing_time")
                analysis.status = ProcessingStatus.COMPLETED
                
                # Extract specific scores if available
                if detailed_analysis and match_result.get("breakdown"):
                    breakdown = match_result["breakdown"]
                    analysis.content_score = breakdown.get("skills_match_score")
                    analysis.keyword_score = breakdown.get("keyword_match_score")
                    analysis.format_score = breakdown.get("experience_match_score")
                
                # Extract recommendations and missing elements
                if match_result.get("recommendations"):
                    analysis.recommendations = match_result["recommendations"]
                
                if match_result.get("missing_elements"):
                    missing = match_result["missing_elements"]
                    analysis.missing_keywords = missing.get("keywords", [])
                    analysis.weaknesses = missing.get("skills", [])
                
                # Create or update job match record
                existing_match = await session.execute(
                    select(JobMatch).where(
                        and_(
                            JobMatch.resume_id == resume_id,
                            JobMatch.job_description_id == job_id,
                            JobMatch.user_id == user_id
                        )
                    )
                )
                job_match = existing_match.scalar_one_or_none()
                
                if job_match:
                    # Update existing match
                    job_match.overall_match_score = analysis.overall_score or 0
                    job_match.match_data = match_result
                    job_match.processing_time = analysis.processing_time
                else:
                    # Create new match record
                    job_match = JobMatch(
                        resume_id=resume_id,
                        job_description_id=job_id,
                        user_id=user_id,
                        overall_match_score=analysis.overall_score or 0,
                        match_data=match_result,
                        processing_time=analysis.processing_time,
                        status=ProcessingStatus.COMPLETED
                    )
                    session.add(job_match)
                
                await session.commit()
                
                logger.info(f"Job match analysis completed: resume {resume_id}, job {job_id}")
                return AnalysisResponse.from_orm(analysis)
                
            except Exception as e:
                analysis.status = ProcessingStatus.FAILED
                analysis.error_message = str(e)
                await session.commit()
                raise AIServiceException(f"Job match analysis failed: {str(e)}")
                
        except Exception as e:
            await session.rollback()
            if isinstance(e, (ResumeNotFoundException, JobDescriptionNotFoundException, AIServiceException)):
                raise
            logger.error(f"Job match analysis failed: resume {resume_id}, job {job_id}, error: {e}")
            raise AIServiceException(f"Job match analysis failed: {str(e)}")
    
    async def compare_resumes(
        self,
        session: AsyncSession,
        resume_ids: List[uuid.UUID],
        user_id: uuid.UUID,
        comparison_type: str = "comprehensive"
    ) -> AnalysisComparisonResponse:
        """
        Compare multiple resumes and analyze differences.
        
        Args:
            session: Database session
            resume_ids: List of resume IDs to compare
            user_id: User ID for ownership check
            comparison_type: Type of comparison
            
        Returns:
            Comparison analysis results
        """
        try:
            if len(resume_ids) < 2:
                raise ValidationException("At least 2 resumes required for comparison")
            
            if len(resume_ids) > 5:
                raise ValidationException("Maximum 5 resumes allowed for comparison")
            
            # Get resumes with latest analyses
            resumes_result = await session.execute(
                select(Resume)
                .options(selectinload(Resume.analyses))
                .where(
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
                raise ResumeNotFoundException(f"Resumes not found: {missing_ids}")
            
            # Get latest analysis for each resume
            resume_analyses = []
            for resume in resumes:
                latest_analysis = None
                if resume.analyses:
                    latest_analysis = max(resume.analyses, key=lambda a: a.created_at)
                
                if not latest_analysis:
                    # Trigger analysis if none exists
                    analysis = await self.analyze_resume(
                        session, resume.id, user_id, "comprehensive"
                    )
                    resume_analyses.append(analysis)
                else:
                    resume_analyses.append(AnalysisResponse.from_orm(latest_analysis))
            
            # Perform comparison analysis
            comparison_data = self._perform_resume_comparison(resume_analyses, comparison_type)
            
            comparison_id = str(uuid.uuid4())
            
            return AnalysisComparisonResponse(
                comparison_id=comparison_id,
                resume_analyses=resume_analyses,
                comparison_data=comparison_data,
                relative_strengths=comparison_data.get("relative_strengths", {}),
                improvement_priority=comparison_data.get("improvement_priority", []),
                best_practices=comparison_data.get("best_practices", [])
            )
            
        except Exception as e:
            if isinstance(e, (ResumeNotFoundException, ValidationException)):
                raise
            logger.error(f"Resume comparison failed: {resume_ids}, error: {e}")
            raise AIServiceException(f"Resume comparison failed: {str(e)}")
    
    async def get_resume_insights(
        self,
        session: AsyncSession,
        resume_id: uuid.UUID,
        user_id: uuid.UUID,
        insight_type: str = "all"
    ) -> AnalysisInsightsResponse:
        """
        Get AI-powered insights for resume improvement.
        
        Args:
            session: Database session
            resume_id: Resume ID
            user_id: User ID for ownership check
            insight_type: Type of insights
            
        Returns:
            Personalized insights and recommendations
        """
        try:
            # Get resume with analyses
            resume_result = await session.execute(
                select(Resume)
                .options(selectinload(Resume.analyses))
                .where(
                    and_(Resume.id == resume_id, Resume.user_id == user_id)
                )
            )
            resume = resume_result.scalar_one_or_none()
            
            if not resume:
                raise ResumeNotFoundException(str(resume_id))
            
            # Get user for personalization
            user_result = await session.execute(
                select(User).where(User.id == user_id)
            )
            user = user_result.scalar_one_or_none()
            
            # Get latest analysis
            latest_analysis = None
            if resume.analyses:
                latest_analysis = max(resume.analyses, key=lambda a: a.created_at)
            
            # Generate insights based on analysis and user profile
            insights = await self._generate_resume_insights(
                resume, latest_analysis, user, insight_type
            )
            
            return insights
            
        except Exception as e:
            if isinstance(e, ResumeNotFoundException):
                raise
            logger.error(f"Failed to get insights for resume {resume_id}: {e}")
            raise AIServiceException(f"Failed to generate insights: {str(e)}")
    
    async def get_analysis_trends(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        time_period: str = "3months",
        trend_type: str = "scores"
    ) -> AnalysisTrendsResponse:
        """
        Get analysis trends and patterns for user's resumes.
        
        Args:
            session: Database session
            user_id: User ID
            time_period: Time period for trends
            trend_type: Type of trends
            
        Returns:
            Trend analysis showing progress over time
        """
        try:
            # Calculate date range
            end_date = datetime.utcnow()
            if time_period == "1month":
                start_date = end_date - timedelta(days=30)
            elif time_period == "3months":
                start_date = end_date - timedelta(days=90)
            elif time_period == "6months":
                start_date = end_date - timedelta(days=180)
            elif time_period == "1year":
                start_date = end_date - timedelta(days=365)
            else:  # all
                start_date = datetime(2020, 1, 1)  # Far back date
            
            # Get analyses in time period
            analyses_result = await session.execute(
                select(ResumeAnalysis)
                .join(Resume, ResumeAnalysis.resume_id == Resume.id)
                .where(
                    and_(
                        Resume.user_id == user_id,
                        ResumeAnalysis.created_at >= start_date,
                        ResumeAnalysis.created_at <= end_date,
                        ResumeAnalysis.status == ProcessingStatus.COMPLETED
                    )
                )
                .order_by(ResumeAnalysis.created_at)
            )
            analyses = analyses_result.scalars().all()
            
            # Generate trends based on type
            trends_data = await self._generate_analysis_trends(
                analyses, time_period, trend_type
            )
            
            return trends_data
            
        except Exception as e:
            logger.error(f"Failed to get analysis trends for user {user_id}: {e}")
            raise AIServiceException(f"Failed to generate trends: {str(e)}")
    
    async def batch_analysis(
        self,
        session: AsyncSession,
        batch_request: BatchAnalysisRequest,
        user_id: uuid.UUID
    ) -> BatchAnalysisResponse:
        """
        Analyze multiple resumes in batch.
        
        Args:
            session: Database session
            batch_request: Batch analysis request
            user_id: User ID
            
        Returns:
            Batch analysis results
        """
        try:
            # Validate resume ownership
            resumes_result = await session.execute(
                select(Resume.id).where(
                    and_(
                        Resume.id.in_(batch_request.resume_ids),
                        Resume.user_id == user_id,
                        Resume.is_deleted == False
                    )
                )
            )
            valid_resume_ids = [str(r.id) for r in resumes_result.scalars().all()]
            
            if len(valid_resume_ids) != len(batch_request.resume_ids):
                invalid_ids = set(str(r) for r in batch_request.resume_ids) - set(valid_resume_ids)
                raise ValidationException(f"Invalid resume IDs: {invalid_ids}")
            
            # Queue batch analysis
            result = bulk_resume_analysis.delay(valid_resume_ids)
            
            batch_id = str(uuid.uuid4())
            estimated_completion = datetime.utcnow() + timedelta(
                minutes=len(valid_resume_ids) * 2  # Estimate 2 minutes per resume
            )
            
            return BatchAnalysisResponse(
                batch_id=batch_id,
                requested_count=len(batch_request.resume_ids),
                queued_count=len(valid_resume_ids),
                failed_count=len(batch_request.resume_ids) - len(valid_resume_ids),
                task_ids=[result.id],
                estimated_completion=estimated_completion,
                results=[{
                    "resume_id": rid,
                    "status": "queued",
                    "task_id": result.id
                } for rid in valid_resume_ids],
                batch_status="processing",
                created_at=datetime.utcnow()
            )
            
        except Exception as e:
            if isinstance(e, ValidationException):
                raise
            logger.error(f"Batch analysis failed for user {user_id}: {e}")
            raise AIServiceException(f"Batch analysis failed: {str(e)}")
    
    async def generate_analysis_report(
        self,
        session: AsyncSession,
        report_request: AnalysisReportRequest,
        user_id: uuid.UUID
    ) -> AnalysisReportResponse:
        """
        Generate comprehensive analysis report.
        
        Args:
            session: Database session
            report_request: Report request parameters
            user_id: User ID
            
        Returns:
            Generated report
        """
        try:
            # Get resumes and their analyses
            resumes_result = await session.execute(
                select(Resume)
                .options(selectinload(Resume.analyses))
                .where(
                    and_(
                        Resume.id.in_(report_request.resume_ids),
                        Resume.user_id == user_id,
                        Resume.is_deleted == False
                    )
                )
            )
            resumes = resumes_result.scalars().all()
            
            if len(resumes) != len(report_request.resume_ids):
                missing_ids = set(report_request.resume_ids) - {r.id for r in resumes}
                raise ValidationException(f"Resumes not found: {missing_ids}")
            
            # Generate report based on type
            report_data = await self._generate_analysis_report(
                resumes, report_request, user_id
            )
            
            report_id = str(uuid.uuid4())
            
            return AnalysisReportResponse(
                report_id=report_id,
                report_type=report_request.report_type,
                format=report_request.format,
                report_data=report_data,
                summary=report_data.get("executive_summary", {}),
                recommendations=report_data.get("key_recommendations", []),
                generated_at=datetime.utcnow(),
                expires_at=datetime.utcnow() + timedelta(days=30)
            )
            
        except Exception as e:
            if isinstance(e, ValidationException):
                raise
            logger.error(f"Report generation failed for user {user_id}: {e}")
            raise AIServiceException(f"Report generation failed: {str(e)}")
    
    async def get_analysis_history(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        pagination: Any,
        filters: Dict[str, Any]
    ) -> Tuple[List[AnalysisResponse], int]:
        """
        Get user's analysis history with filtering.
        
        Args:
            session: Database session
            user_id: User ID
            pagination: Pagination parameters
            filters: Filter criteria
            
        Returns:
            Tuple of (analyses, total_count)
        """
        try:
            # Build query with filters
            query = (
                select(ResumeAnalysis)
                .join(Resume, ResumeAnalysis.resume_id == Resume.id)
                .where(Resume.user_id == user_id)
                .order_by(desc(ResumeAnalysis.created_at))
            )
            
            # Apply filters
            if filters.get("resume_id"):
                query = query.where(ResumeAnalysis.resume_id == filters["resume_id"])
            
            if filters.get("analysis_type"):
                query = query.where(ResumeAnalysis.analysis_type == filters["analysis_type"])
            
            if filters.get("job_id"):
                query = query.where(ResumeAnalysis.job_description_id == filters["job_id"])
            
            # Get total count
            count_query = select(func.count(ResumeAnalysis.id)).select_from(
                query.subquery()
            )
            total_result = await session.execute(count_query)
            total_count = total_result.scalar()
            
            # Get paginated results
            paginated_query = query.limit(pagination.limit).offset(pagination.offset)
            analyses_result = await session.execute(paginated_query)
            analyses = analyses_result.scalars().all()
            
            return [AnalysisResponse.from_orm(a) for a in analyses], total_count
            
        except Exception as e:
            logger.error(f"Failed to get analysis history for user {user_id}: {e}")
            raise AIServiceException(f"Failed to retrieve analysis history: {str(e)}")
    
    async def delete_analysis(
        self,
        session: AsyncSession,
        analysis_id: uuid.UUID,
        user_id: uuid.UUID
    ) -> bool:
        """
        Delete an analysis record.
        
        Args:
            session: Database session
            analysis_id: Analysis ID to delete
            user_id: User ID for ownership check
            
        Returns:
            True if successful
        """
        try:
            # Get analysis with user check
            analysis_result = await session.execute(
                select(ResumeAnalysis)
                .join(Resume, ResumeAnalysis.resume_id == Resume.id)
                .where(
                    and_(
                        ResumeAnalysis.id == analysis_id,
                        Resume.user_id == user_id
                    )
                )
            )
            analysis = analysis_result.scalar_one_or_none()
            
            if not analysis:
                return False
            
            await session.delete(analysis)
            await session.commit()
            
            logger.info(f"Analysis deleted: {analysis_id}")
            return True
            
        except Exception as e:
            await session.rollback()
            logger.error(f"Analysis deletion failed: {analysis_id}, error: {e}")
            return False
    
    async def get_analysis_stats(
        self,
        session: AsyncSession,
        user_id: uuid.UUID
    ) -> Dict[str, Any]:
        """
        Get comprehensive analysis statistics for user.
        
        Args:
            session: Database session
            user_id: User ID
            
        Returns:
            Detailed statistics
        """
        try:
            # Get basic counts
            total_analyses = await session.execute(
                select(func.count(ResumeAnalysis.id))
                .join(Resume, ResumeAnalysis.resume_id == Resume.id)
                .where(Resume.user_id == user_id)
            )
            total_analyses = total_analyses.scalar()
            
            # Get analyses by type
            analyses_by_type = await session.execute(
                select(ResumeAnalysis.analysis_type, func.count(ResumeAnalysis.id))
                .join(Resume, ResumeAnalysis.resume_id == Resume.id)
                .where(Resume.user_id == user_id)
                .group_by(ResumeAnalysis.analysis_type)
            )
            type_counts = dict(analyses_by_type.fetchall())
            
            # Get recent activity
            week_ago = datetime.utcnow() - timedelta(days=7)
            recent_analyses = await session.execute(
                select(func.count(ResumeAnalysis.id))
                .join(Resume, ResumeAnalysis.resume_id == Resume.id)
                .where(
                    and_(
                        Resume.user_id == user_id,
                        ResumeAnalysis.created_at >= week_ago
                    )
                )
            )
            recent_analyses = recent_analyses.scalar()
            
            # Get average scores
            avg_scores = await session.execute(
                select(
                    func.avg(ResumeAnalysis.overall_score),
                    func.avg(ResumeAnalysis.ats_score),
                    func.avg(ResumeAnalysis.content_score)
                )
                .join(Resume, ResumeAnalysis.resume_id == Resume.id)
                .where(
                    and_(
                        Resume.user_id == user_id,
                        ResumeAnalysis.status == ProcessingStatus.COMPLETED
                    )
                )
            )
            avg_overall, avg_ats, avg_content = avg_scores.first()
            
            return {
                "total_analyses": total_analyses,
                "analyses_by_type": type_counts,
                "recent_analyses": recent_analyses,
                "average_scores": {
                    "overall": float(avg_overall) if avg_overall else None,
                    "ats": float(avg_ats) if avg_ats else None,
                    "content": float(avg_content) if avg_content else None
                },
                "last_updated": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to get analysis stats for user {user_id}: {e}")
            raise AIServiceException(f"Failed to retrieve statistics: {str(e)}")
    
    async def get_ai_service_status(self) -> Dict[str, Any]:
        """
        Get current status and capabilities of AI analysis services.
        
        Returns:
            AI service status information
        """
        try:
            return await self.ai_service.get_service_status()
        except Exception as e:
            logger.error(f"Failed to get AI service status: {e}")
            return {
                "available_services": [],
                "status": "error",
                "error": str(e)
            }
    
    # Private helper methods
    def _perform_resume_comparison(
        self,
        analyses: List[AnalysisResponse],
        comparison_type: str
    ) -> Dict[str, Any]:
        """Perform detailed comparison of resume analyses."""
        
        comparison_data = {
            "comparison_type": comparison_type,
            "resume_count": len(analyses),
            "score_comparison": {},
            "relative_strengths": {},
            "improvement_priority": [],
            "best_practices": []
        }
        
        # Compare scores
        if comparison_type in ["comprehensive", "scores"]:
            scores = {
                "overall": [a.overall_score for a in analyses if a.overall_score],
                "ats": [a.ats_score for a in analyses if a.ats_score],
                "content": [a.content_score for a in analyses if a.content_score],
                "keyword": [a.keyword_score for a in analyses if a.keyword_score]
            }
            
            for score_type, values in scores.items():
                if values:
                    comparison_data["score_comparison"][score_type] = {
                        "highest": max(values),
                        "lowest": min(values),
                        "average": sum(values) / len(values),
                        "range": max(values) - min(values)
                    }
        
        # Identify relative strengths
        for i, analysis in enumerate(analyses):
            resume_id = str(analysis.resume_id)
            strengths = []
            
            if analysis.overall_score and analysis.overall_score >= 80:
                strengths.append("High overall quality")
            
            if analysis.ats_score and analysis.ats_score >= 85:
                strengths.append("Excellent ATS compatibility")
            
            if analysis.strengths:
                strengths.extend(analysis.strengths[:3])  # Top 3 strengths
            
            comparison_data["relative_strengths"][resume_id] = strengths
        
        # Generate improvement priorities
        all_recommendations = []
        for analysis in analyses:
            if analysis.recommendations:
                all_recommendations.extend(analysis.recommendations)
        
        # Count recommendation frequency
        rec_counts = {}
        for rec in all_recommendations:
            rec_counts[rec] = rec_counts.get(rec, 0) + 1
        
        # Sort by frequency
        common_improvements = sorted(rec_counts.items(), key=lambda x: x[1], reverse=True)
        
        comparison_data["improvement_priority"] = [
            {
                "recommendation": rec,
                "frequency": count,
                "priority": "high" if count >= len(analyses) // 2 else "medium"
            }
            for rec, count in common_improvements[:10]
        ]
        
        # Identify best practices from highest scoring resume
        best_analysis = max(analyses, key=lambda a: a.overall_score or 0)
        if best_analysis.strengths:
            comparison_data["best_practices"] = best_analysis.strengths
        
        return comparison_data
    
    async def _generate_resume_insights(
        self,
        resume: Resume,
        analysis: Optional[ResumeAnalysis],
        user: Optional[User],
        insight_type: str
    ) -> AnalysisInsightsResponse:
        """Generate personalized insights for resume improvement."""
        
        # Base insights structure
        insights = {
            "content_quality": {},
            "ats_compatibility": {},
            "keyword_optimization": {},
            "quick_wins": [],
            "long_term_goals": [],
            "personalized_tips": []
        }
        
        if analysis:
            # Content quality insights
            insights["content_quality"] = {
                "score": analysis.content_score or 0,
                "assessment": self._get_score_assessment(analysis.content_score or 0),
                "strengths": analysis.strengths or [],
                "areas_for_improvement": analysis.weaknesses or []
            }
            
            # ATS compatibility insights
            insights["ats_compatibility"] = {
                "score": analysis.ats_score or 0,
                "assessment": self._get_score_assessment(analysis.ats_score or 0),
                "keyword_density": analysis.keyword_score or 0,
                "missing_keywords": analysis.missing_keywords or []
            }
            
            # Quick wins (easy improvements)
            if analysis.recommendations:
                quick_wins = [r for r in analysis.recommendations if any(
                    keyword in r.lower() for keyword in 
                    ["add", "include", "mention", "format", "organize"]
                )]
                insights["quick_wins"] = quick_wins[:5]
            
            # Long-term goals (strategic improvements)
            if analysis.recommendations:
                long_term = [r for r in analysis.recommendations if any(
                    keyword in r.lower() for keyword in 
                    ["develop", "build", "strengthen", "expand", "enhance"]
                )]
                insights["long_term_goals"] = long_term[:5]
        
        # Personalized tips based on user profile
        if user:
            personalized_tips = []
            
            if user.industry:
                personalized_tips.append(f"Highlight {user.industry}-specific achievements and skills")
            
            if user.experience_years:
                if user.experience_years < 3:
                    personalized_tips.append("Focus on education, projects, and transferable skills")
                elif user.experience_years > 10:
                    personalized_tips.append("Emphasize leadership experience and strategic contributions")
            
            insights["personalized_tips"] = personalized_tips
        
        return AnalysisInsightsResponse(
            resume_id=resume.id,
            insight_type=insight_type,
            **insights,
            generated_at=datetime.utcnow()
        )
    
    async def _generate_analysis_trends(
        self,
        analyses: List[ResumeAnalysis],
        time_period: str,
        trend_type: str
    ) -> AnalysisTrendsResponse:
        """Generate trend analysis from historical analyses."""
        
        if not analyses:
            return AnalysisTrendsResponse(
                user_id=uuid.uuid4(),  # Will be set by caller
                time_period=time_period,
                trend_type=trend_type,
                score_trends={},
                improvement_rate=0.0,
                analysis_frequency={},
                most_improved_areas=[],
                areas_needing_attention=[],
                total_analyses=0,
                average_score_improvement=0.0,
                consistency_score=0.0,
                trend_insights=[],
                recommendations=[],
                generated_at=datetime.utcnow()
            )
        
        # Calculate score trends
        score_trends = {}
        if trend_type in ["scores", "all"]:
            for score_type in ["overall_score", "ats_score", "content_score"]:
                trend_data = []
                for analysis in analyses:
                    score = getattr(analysis, score_type)
                    if score is not None:
                        trend_data.append({
                            "date": analysis.created_at.isoformat(),
                            "score": score,
                            "analysis_id": str(analysis.id)
                        })
                score_trends[score_type] = trend_data
        
        # Calculate improvement rate
        improvement_rate = 0.0
        if len(analyses) >= 2:
            first_analysis = analyses[0]
            last_analysis = analyses[-1]
            
            if first_analysis.overall_score and last_analysis.overall_score:
                improvement_rate = (
                    (last_analysis.overall_score - first_analysis.overall_score) /
                    first_analysis.overall_score * 100
                )
        
        # Analysis frequency by month
        frequency = {}
        for analysis in analyses:
            month_key = analysis.created_at.strftime("%Y-%m")
            frequency[month_key] = frequency.get(month_key, 0) + 1
        
        # Generate insights and recommendations
        insights = []
        recommendations = []
        
        if improvement_rate > 10:
            insights.append("Strong upward trend in resume quality")
            recommendations.append("Continue with current improvement strategy")
        elif improvement_rate < -5:
            insights.append("Declining trend detected")
            recommendations.append("Review recent changes and focus on core strengths")
        
        if len(analyses) > 5:
            insights.append("Consistent analysis activity shows commitment to improvement")
        
        return AnalysisTrendsResponse(
            user_id=uuid.uuid4(),  # Will be set by caller
            time_period=time_period,
            trend_type=trend_type,
            score_trends=score_trends,
            improvement_rate=improvement_rate,
            analysis_frequency=frequency,
            most_improved_areas=["Overall Quality", "ATS Compatibility"],  # Simplified
            areas_needing_attention=["Keyword Optimization"],  # Simplified
            total_analyses=len(analyses),
            average_score_improvement=improvement_rate,
            consistency_score=80.0,  # Simplified calculation
            trend_insights=insights,
            recommendations=recommendations,
            generated_at=datetime.utcnow()
        )
    
    async def _generate_analysis_report(
        self,
        resumes: List[Resume],
        report_request: AnalysisReportRequest,
        user_id: uuid.UUID
    ) -> Dict[str, Any]:
        """Generate comprehensive analysis report."""
        
        report_data = {
            "report_type": report_request.report_type,
            "resumes_analyzed": len(resumes),
            "generation_date": datetime.utcnow().isoformat(),
            "user_id": str(user_id)
        }
        
        # Executive summary
        total_analyses = sum(len(r.analyses) for r in resumes)
        avg_score = 0
        if total_analyses > 0:
            all_scores = [
                a.overall_score for r in resumes for a in r.analyses 
                if a.overall_score is not None
            ]
            avg_score = sum(all_scores) / len(all_scores) if all_scores else 0
        
        report_data["executive_summary"] = {
            "total_resumes": len(resumes),
            "total_analyses": total_analyses,
            "average_score": avg_score,
            "score_range": self._get_score_assessment(avg_score)
        }
        
        # Key recommendations
        all_recommendations = []
        for resume in resumes:
            for analysis in resume.analyses:
                if analysis.recommendations:
                    all_recommendations.extend(analysis.recommendations)
        
        # Get most common recommendations
        rec_counts = {}
        for rec in all_recommendations:
            rec_counts[rec] = rec_counts.get(rec, 0) + 1
        
        top_recommendations = sorted(rec_counts.items(), key=lambda x: x[1], reverse=True)
        report_data["key_recommendations"] = [rec for rec, _ in top_recommendations[:10]]
        
        # Detailed analysis by resume
        if report_request.report_type == "individual":
            report_data["resume_details"] = []
            for resume in resumes:
                latest_analysis = None
                if resume.analyses:
                    latest_analysis = max(resume.analyses, key=lambda a: a.created_at)
                
                resume_detail = {
                    "resume_id": str(resume.id),
                    "title": resume.title,
                    "overall_score": latest_analysis.overall_score if latest_analysis else None,
                    "ats_score": latest_analysis.ats_score if latest_analysis else None,
                    "strengths": latest_analysis.strengths if latest_analysis else [],
                    "improvements": latest_analysis.recommendations if latest_analysis else []
                }
                report_data["resume_details"].append(resume_detail)
        
        return report_data
    
    def _get_score_assessment(self, score: float) -> str:
        """Get qualitative assessment of score."""
        if score >= 90:
            return "Excellent"
        elif score >= 80:
            return "Very Good"
        elif score >= 70:
            return "Good"
        elif score >= 60:
            return "Fair"
        else:
            return "Needs Improvement"


# Export service
__all__ = ["AnalysisService"]