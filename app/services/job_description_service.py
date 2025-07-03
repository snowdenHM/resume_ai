"""
Job description service for managing job postings, analysis, and matching.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
import uuid
import re
from urllib.parse import urlparse

from sqlalchemy import select, update, and_, desc, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, joinedload

from app.config import settings
from app.exceptions import (
    JobDescriptionNotFoundException, ValidationException, AIServiceException,
    DatabaseException
)
from app.models.job_description import (
    JobDescription, JobMatch, JobStatus, JobType, 
    ExperienceLevel, RemoteType
)
from app.models.resume import Resume
from app.models.user import User
from app.schemas.job_description import (
    JobDescriptionCreateRequest, JobDescriptionUpdateRequest,
    JobDescriptionResponse, JobDescriptionListResponse,
    JobAnalysisResponse, JobMatchResponse, JobSearchRequest,
    JobStatsResponse, JobImportRequest, JobUrlExtractionResponse
)
from app.services.ai_service import AIService
from app.workers.celery_app import analyze_job_description_task, extract_job_from_url_task

logger = logging.getLogger(__name__)


class JobDescriptionService:
    """Service for job description management and analysis."""
    
    def __init__(self):
        self.ai_service = AIService()
    
    async def create_job_description(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        job_data: JobDescriptionCreateRequest
    ) -> JobDescription:
        """
        Create a new job description.
        
        Args:
            session: Database session
            user_id: User ID
            job_data: Job description data
            
        Returns:
            Created job description
        """
        try:
            # Check user's job description quota
            user_job_count = await session.execute(
                select(func.count(JobDescription.id))
                .where(JobDescription.user_id == user_id)
            )
            job_count = user_job_count.scalar()
            
            # Get user to check premium status
            user_result = await session.execute(
                select(User).where(User.id == user_id)
            )
            user = user_result.scalar_one_or_none()
            
            max_jobs = 50 if (user and user.is_premium) else 10
            if job_count >= max_jobs:
                raise ValidationException(f"Job description limit reached ({max_jobs})")
            
            # Create job description
            job = JobDescription(
                user_id=user_id,
                title=job_data.title,
                company=job_data.company,
                location=job_data.location,
                job_type=job_data.job_type,
                experience_level=job_data.experience_level,
                remote_type=job_data.remote_type,
                industry=job_data.industry,
                department=job_data.department,
                description=job_data.description,
                salary_min=job_data.salary_min,
                salary_max=job_data.salary_max,
                salary_currency=job_data.salary_currency,
                salary_period=job_data.salary_period,
                responsibilities=job_data.responsibilities,
                requirements=job_data.requirements,
                nice_to_have=job_data.nice_to_have,
                benefits=job_data.benefits,
                required_skills=job_data.required_skills,
                preferred_skills=job_data.preferred_skills,
                education_requirements=job_data.education_requirements,
                years_experience_min=job_data.years_experience_min,
                years_experience_max=job_data.years_experience_max,
                application_url=job_data.application_url,
                application_email=job_data.application_email,
                application_deadline=job_data.application_deadline,
                status=job_data.status,
                posted_date=job_data.posted_date or datetime.utcnow(),
                source_url=job_data.source_url,
                source_platform=job_data.source_platform
            )
            
            session.add(job)
            await session.flush()
            
            await session.commit()
            
            # Trigger background analysis
            analyze_job_description_task.delay(str(job.id))
            
            logger.info(f"Job description created: {job.id} for user {user_id}")
            return job
            
        except Exception as e:
            await session.rollback()
            if isinstance(e, ValidationException):
                raise
            logger.error(f"Job creation failed for user {user_id}: {e}")
            raise DatabaseException(f"Job creation failed: {str(e)}")
    
    async def get_job_description(
        self,
        session: AsyncSession,
        job_id: uuid.UUID,
        user_id: Optional[uuid.UUID] = None
    ) -> JobDescription:
        """
        Get job description by ID.
        
        Args:
            session: Database session
            job_id: Job description ID
            user_id: Optional user ID for ownership check
            
        Returns:
            Job description
        """
        query = select(JobDescription).where(JobDescription.id == job_id)
        
        if user_id:
            query = query.where(JobDescription.user_id == user_id)
        
        result = await session.execute(query)
        job = result.scalar_one_or_none()
        
        if not job:
            raise JobDescriptionNotFoundException(str(job_id))
        
        # Increment view count
        job.view_count += 1
        await session.commit()
        
        return job
    
    async def get_user_job_descriptions(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        search_request: JobSearchRequest
    ) -> Tuple[List[JobDescription], int]:
        """
        Get user's job descriptions with search and filtering.
        
        Args:
            session: Database session
            user_id: User ID
            search_request: Search and filter parameters
            
        Returns:
            Tuple of (job descriptions, total count)
        """
        try:
            # Build base query
            query = (
                select(JobDescription)
                .where(JobDescription.user_id == user_id)
            )
            
            # Apply text search
            if search_request.query:
                search_terms = f"%{search_request.query}%"
                query = query.where(
                    or_(
                        JobDescription.title.ilike(search_terms),
                        JobDescription.company.ilike(search_terms),
                        JobDescription.description.ilike(search_terms),
                        JobDescription.location.ilike(search_terms)
                    )
                )
            
            # Apply filters
            if search_request.company:
                query = query.where(JobDescription.company.ilike(f"%{search_request.company}%"))
            
            if search_request.location:
                query = query.where(JobDescription.location.ilike(f"%{search_request.location}%"))
            
            if search_request.job_type:
                query = query.where(JobDescription.job_type == search_request.job_type)
            
            if search_request.experience_level:
                query = query.where(JobDescription.experience_level == search_request.experience_level)
            
            if search_request.remote_type:
                query = query.where(JobDescription.remote_type == search_request.remote_type)
            
            if search_request.industry:
                query = query.where(JobDescription.industry.ilike(f"%{search_request.industry}%"))
            
            # Salary filters
            if search_request.salary_min:
                query = query.where(
                    or_(
                        JobDescription.salary_min >= search_request.salary_min,
                        JobDescription.salary_max >= search_request.salary_min
                    )
                )
            
            if search_request.salary_max:
                query = query.where(
                    or_(
                        JobDescription.salary_min <= search_request.salary_max,
                        JobDescription.salary_max <= search_request.salary_max
                    )
                )
            
            # Date filters
            if search_request.posted_after:
                query = query.where(JobDescription.posted_date >= search_request.posted_after)
            
            if search_request.posted_before:
                query = query.where(JobDescription.posted_date <= search_request.posted_before)
            
            # Boolean filters
            if search_request.has_salary_info is not None:
                if search_request.has_salary_info:
                    query = query.where(
                        or_(
                            JobDescription.salary_min.isnot(None),
                            JobDescription.salary_max.isnot(None)
                        )
                    )
                else:
                    query = query.where(
                        and_(
                            JobDescription.salary_min.is_(None),
                            JobDescription.salary_max.is_(None)
                        )
                    )
            
            if search_request.is_remote_friendly is not None:
                if search_request.is_remote_friendly:
                    query = query.where(
                        JobDescription.remote_type.in_([RemoteType.REMOTE, RemoteType.HYBRID])
                    )
                else:
                    query = query.where(JobDescription.remote_type == RemoteType.ON_SITE)
            
            # Get total count
            count_query = select(func.count()).select_from(query.subquery())
            total_result = await session.execute(count_query)
            total_count = total_result.scalar()
            
            # Apply sorting
            if search_request.sort_by == "created_at":
                sort_field = JobDescription.created_at
            elif search_request.sort_by == "title":
                sort_field = JobDescription.title
            elif search_request.sort_by == "company":
                sort_field = JobDescription.company
            elif search_request.sort_by == "posted_date":
                sort_field = JobDescription.posted_date
            else:
                sort_field = JobDescription.created_at
            
            if search_request.sort_order == "asc":
                query = query.order_by(sort_field.asc())
            else:
                query = query.order_by(sort_field.desc())
            
            # Apply pagination
            paginated_query = query.limit(search_request.page_size).offset(
                (search_request.page - 1) * search_request.page_size
            )
            
            result = await session.execute(paginated_query)
            jobs = result.scalars().all()
            
            return list(jobs), total_count
            
        except Exception as e:
            logger.error(f"Job search failed for user {user_id}: {e}")
            raise DatabaseException(f"Job search failed: {str(e)}")
    
    async def update_job_description(
        self,
        session: AsyncSession,
        job_id: uuid.UUID,
        user_id: uuid.UUID,
        job_data: JobDescriptionUpdateRequest
    ) -> JobDescription:
        """
        Update job description.
        
        Args:
            session: Database session
            job_id: Job description ID
            user_id: User ID
            job_data: Updated job data
            
        Returns:
            Updated job description
        """
        try:
            job = await self.get_job_description(session, job_id, user_id)
            
            # Update fields that are provided
            for field, value in job_data.dict(exclude_unset=True).items():
                if hasattr(job, field):
                    setattr(job, field, value)
            
            await session.commit()
            
            logger.info(f"Job description updated: {job_id}")
            return job
            
        except Exception as e:
            await session.rollback()
            if isinstance(e, JobDescriptionNotFoundException):
                raise
            logger.error(f"Job update failed: {job_id}, error: {e}")
            raise DatabaseException(f"Job update failed: {str(e)}")
    
    async def delete_job_description(
        self,
        session: AsyncSession,
        job_id: uuid.UUID,
        user_id: uuid.UUID
    ) -> bool:
        """
        Delete job description.
        
        Args:
            session: Database session
            job_id: Job description ID
            user_id: User ID
            
        Returns:
            True if successful
        """
        try:
            job = await self.get_job_description(session, job_id, user_id)
            
            await session.delete(job)
            await session.commit()
            
            logger.info(f"Job description deleted: {job_id}")
            return True
            
        except Exception as e:
            await session.rollback()
            if isinstance(e, JobDescriptionNotFoundException):
                raise
            logger.error(f"Job deletion failed: {job_id}, error: {e}")
            return False
    
    async def analyze_job_description(
        self,
        session: AsyncSession,
        job_id: uuid.UUID,
        user_id: uuid.UUID
    ) -> JobAnalysisResponse:
        """
        Analyze job description using AI.
        
        Args:
            session: Database session
            job_id: Job description ID
            user_id: User ID
            
        Returns:
            Analysis results
        """
        try:
            job = await self.get_job_description(session, job_id, user_id)
            
            # Perform AI analysis
            analysis_result = await self.ai_service.extract_job_requirements(job.description)
            
            # Update job with extracted data
            if analysis_result.get("required_skills"):
                job.required_skills = analysis_result["required_skills"]
            
            if analysis_result.get("preferred_skills"):
                job.preferred_skills = analysis_result["preferred_skills"]
            
            if analysis_result.get("keywords"):
                job.keywords = analysis_result["keywords"]
            
            if analysis_result.get("requirements"):
                job.requirements = analysis_result["requirements"]
            
            # Calculate analysis scores
            complexity_score = self._calculate_complexity_score(job)
            analysis_score = self._calculate_analysis_score(analysis_result)
            
            job.structured_data = analysis_result
            job.analysis_score = analysis_score
            job.complexity_score = complexity_score
            job.last_analyzed_at = datetime.utcnow()
            
            await session.commit()
            
            # Create response
            response = JobAnalysisResponse(
                job_id=job.id,
                analysis_score=analysis_score,
                complexity_score=complexity_score,
                extracted_requirements=analysis_result.get("structured_requirements", {}),
                required_skills=analysis_result.get("required_skills", []),
                soft_skills=analysis_result.get("soft_skills", []),
                important_keywords=analysis_result.get("keywords", []),
                industry_terms=analysis_result.get("industry_terms", []),
                role_specific_terms=analysis_result.get("role_terms", []),
                job_category=analysis_result.get("category"),
                seniority_level=analysis_result.get("seniority"),
                description_quality={
                    "clarity": analysis_result.get("clarity_score", 0),
                    "completeness": analysis_result.get("completeness_score", 0),
                    "specificity": analysis_result.get("specificity_score", 0)
                },
                clarity_score=analysis_result.get("clarity_score", 0),
                completeness_score=analysis_result.get("completeness_score", 0),
                improvement_suggestions=analysis_result.get("suggestions", []),
                missing_information=analysis_result.get("missing_info", []),
                analyzed_at=datetime.utcnow()
            )
            
            logger.info(f"Job description analyzed: {job_id}")
            return response
            
        except Exception as e:
            if isinstance(e, JobDescriptionNotFoundException):
                raise
            logger.error(f"Job analysis failed: {job_id}, error: {e}")
            raise AIServiceException(f"Job analysis failed: {str(e)}")
    
    async def match_job_with_resumes(
        self,
        session: AsyncSession,
        job_id: uuid.UUID,
        user_id: uuid.UUID,
        resume_ids: Optional[List[uuid.UUID]] = None
    ) -> List[JobMatchResponse]:
        """
        Match job description with user's resumes.
        
        Args:
            session: Database session
            job_id: Job description ID
            user_id: User ID
            resume_ids: Optional specific resume IDs to match
            
        Returns:
            List of job matches
        """
        try:
            job = await self.get_job_description(session, job_id, user_id)
            
            # Get resumes to match
            resume_query = (
                select(Resume)
                .where(
                    and_(
                        Resume.user_id == user_id,
                        Resume.is_deleted == False,
                        Resume.raw_text.isnot(None)
                    )
                )
            )
            
            if resume_ids:
                resume_query = resume_query.where(Resume.id.in_(resume_ids))
            
            resumes_result = await session.execute(resume_query)
            resumes = resumes_result.scalars().all()
            
            matches = []
            
            for resume in resumes:
                try:
                    # Perform AI matching
                    match_result = await self.ai_service.match_resume_to_job(
                        resume.raw_text, job.description
                    )
                    
                    # Create or update job match record
                    existing_match = await session.execute(
                        select(JobMatch).where(
                            and_(
                                JobMatch.resume_id == resume.id,
                                JobMatch.job_description_id == job.id,
                                JobMatch.user_id == user_id
                            )
                        )
                    )
                    job_match = existing_match.scalar_one_or_none()
                    
                    if job_match:
                        # Update existing match
                        job_match.overall_match_score = match_result.get("overall_match_score", 0)
                        job_match.match_data = match_result
                        job_match.processing_time = match_result.get("processing_time")
                    else:
                        # Create new match
                        job_match = JobMatch(
                            resume_id=resume.id,
                            job_description_id=job.id,
                            user_id=user_id,
                            overall_match_score=match_result.get("overall_match_score", 0),
                            match_data=match_result,
                            processing_time=match_result.get("processing_time")
                        )
                        session.add(job_match)
                    
                    # Create response
                    match_response = JobMatchResponse(
                        id=job_match.id if job_match.id else uuid.uuid4(),
                        resume_id=resume.id,
                        job_description_id=job.id,
                        user_id=user_id,
                        overall_match_score=match_result.get("overall_match_score", 0),
                        skills_match_score=match_result.get("skills_match_score"),
                        experience_match_score=match_result.get("experience_match_score"),
                        education_match_score=match_result.get("education_match_score"),
                        keyword_match_score=match_result.get("keyword_match_score"),
                        matched_skills=match_result.get("matched_skills", []),
                        missing_skills=match_result.get("missing_skills", []),
                        matched_keywords=match_result.get("matched_keywords", []),
                        missing_keywords=match_result.get("missing_keywords", []),
                        recommendations=match_result.get("recommendations", []),
                        match_data=match_result,
                        processing_time=match_result.get("processing_time"),
                        created_at=datetime.utcnow()
                    )
                    
                    matches.append(match_response)
                    
                except Exception as e:
                    logger.warning(f"Failed to match resume {resume.id} with job {job_id}: {e}")
                    continue
            
            await session.commit()
            
            # Update job match count
            job.match_count = len(matches)
            await session.commit()
            
            logger.info(f"Job matched with {len(matches)} resumes: {job_id}")
            return matches
            
        except Exception as e:
            await session.rollback()
            if isinstance(e, JobDescriptionNotFoundException):
                raise
            logger.error(f"Job matching failed: {job_id}, error: {e}")
            raise AIServiceException(f"Job matching failed: {str(e)}")
    
    async def import_job_from_url(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        import_request: JobImportRequest
    ) -> JobDescription:
        """
        Import job description from URL.
        
        Args:
            session: Database session
            user_id: User ID
            import_request: Import request data
            
        Returns:
            Imported job description
        """
        try:
            # Validate URL
            parsed_url = urlparse(import_request.url)
            if not parsed_url.scheme or not parsed_url.netloc:
                raise ValidationException("Invalid URL provided")
            
            # Extract job data from URL (simplified implementation)
            extraction_result = await self._extract_job_from_url(import_request.url)
            
            if not extraction_result.get("title") or not extraction_result.get("description"):
                raise ValidationException("Could not extract job information from URL")
            
            # Create job description from extracted data
            job_data = JobDescriptionCreateRequest(
                title=extraction_result.get("title", "Imported Job"),
                company=extraction_result.get("company", "Unknown Company"),
                location=extraction_result.get("location"),
                description=extraction_result.get("description", ""),
                requirements=extraction_result.get("requirements", []),
                source_url=import_request.url,
                source_platform=extraction_result.get("source_platform"),
                status=JobStatus.DRAFT if import_request.save_as_draft else JobStatus.ACTIVE
            )
            
            job = await self.create_job_description(session, user_id, job_data)
            
            logger.info(f"Job imported from URL: {job.id}")
            return job
            
        except Exception as e:
            if isinstance(e, ValidationException):
                raise
            logger.error(f"Job import failed for user {user_id}: {e}")
            raise ValidationException(f"Job import failed: {str(e)}")
    
    async def get_job_statistics(
        self,
        session: AsyncSession,
        user_id: uuid.UUID
    ) -> JobStatsResponse:
        """
        Get job description statistics for user.
        
        Args:
            session: Database session
            user_id: User ID
            
        Returns:
            Job statistics
        """
        try:
            # Total jobs
            total_jobs = await session.execute(
                select(func.count(JobDescription.id))
                .where(JobDescription.user_id == user_id)
            )
            total_jobs = total_jobs.scalar()
            
            # Active jobs
            active_jobs = await session.execute(
                select(func.count(JobDescription.id))
                .where(
                    and_(
                        JobDescription.user_id == user_id,
                        JobDescription.status == JobStatus.ACTIVE
                    )
                )
            )
            active_jobs = active_jobs.scalar()
            
            # Jobs by type
            jobs_by_type = await session.execute(
                select(JobDescription.job_type, func.count(JobDescription.id))
                .where(JobDescription.user_id == user_id)
                .group_by(JobDescription.job_type)
            )
            type_counts = dict(jobs_by_type.fetchall())
            
            # Jobs by industry
            jobs_by_industry = await session.execute(
                select(JobDescription.industry, func.count(JobDescription.id))
                .where(
                    and_(
                        JobDescription.user_id == user_id,
                        JobDescription.industry.isnot(None)
                    )
                )
                .group_by(JobDescription.industry)
                .limit(10)
            )
            industry_counts = dict(jobs_by_industry.fetchall())
            
            # Recent activity
            week_ago = datetime.utcnow() - timedelta(days=7)
            month_ago = datetime.utcnow() - timedelta(days=30)
            
            jobs_this_week = await session.execute(
                select(func.count(JobDescription.id))
                .where(
                    and_(
                        JobDescription.user_id == user_id,
                        JobDescription.created_at >= week_ago
                    )
                )
            )
            jobs_this_week = jobs_this_week.scalar()
            
            jobs_this_month = await session.execute(
                select(func.count(JobDescription.id))
                .where(
                    and_(
                        JobDescription.user_id == user_id,
                        JobDescription.created_at >= month_ago
                    )
                )
            )
            jobs_this_month = jobs_this_month.scalar()
            
            # Get popular skills from all jobs
            all_skills = []
            jobs_with_skills = await session.execute(
                select(JobDescription.required_skills, JobDescription.preferred_skills)
                .where(JobDescription.user_id == user_id)
            )
            
            for required, preferred in jobs_with_skills.fetchall():
                if required:
                    all_skills.extend(required)
                if preferred:
                    all_skills.extend(preferred)
            
            # Count skill frequency
            skill_counts = {}
            for skill in all_skills:
                skill_counts[skill] = skill_counts.get(skill, 0) + 1
            
            popular_skills = sorted(skill_counts.items(), key=lambda x: x[1], reverse=True)[:10]
            popular_skills = [skill for skill, _ in popular_skills]
            
            return JobStatsResponse(
                total_jobs=total_jobs,
                active_jobs=active_jobs,
                jobs_by_type=type_counts,
                jobs_by_industry=industry_counts,
                jobs_by_experience_level={},  # Can be implemented similarly
                jobs_added_this_week=jobs_this_week,
                jobs_added_this_month=jobs_this_month,
                total_matches=0,  # Can be calculated from JobMatch table
                average_match_score=None,
                best_match_job=None,
                applications_count=0,  # Can be tracked separately
                bookmarked_jobs=0,  # Can be tracked separately
                popular_skills=popular_skills,
                popular_industries=list(industry_counts.keys())[:5],
                salary_trends=None,  # Can be calculated from salary data
                last_updated=datetime.utcnow()
            )
            
        except Exception as e:
            logger.error(f"Failed to get job stats for user {user_id}: {e}")
            raise DatabaseException(f"Failed to retrieve statistics: {str(e)}")
    
    # Private helper methods
    async def _extract_job_from_url(self, url: str) -> Dict[str, Any]:
        """Extract job information from URL (simplified implementation)."""
        # This would typically use web scraping or API integration
        # For now, return a basic structure
        return {
            "title": "Extracted Job Title",
            "company": "Extracted Company",
            "description": "Extracted job description...",
            "location": "Remote",
            "source_platform": self._detect_platform(url)
        }
    
    def _detect_platform(self, url: str) -> str:
        """Detect job board platform from URL."""
        domain = urlparse(url).netloc.lower()
        
        if "linkedin.com" in domain:
            return "LinkedIn"
        elif "indeed.com" in domain:
            return "Indeed"
        elif "glassdoor.com" in domain:
            return "Glassdoor"
        elif "monster.com" in domain:
            return "Monster"
        elif "ziprecruiter.com" in domain:
            return "ZipRecruiter"
        else:
            return "Other"
    
    def _calculate_complexity_score(self, job: JobDescription) -> float:
        """Calculate job complexity score based on requirements."""
        score = 0
        
        # Base score
        score += 20
        
        # Add points for detailed requirements
        if job.requirements and len(job.requirements) > 3:
            score += 20
        
        if job.required_skills and len(job.required_skills) > 5:
            score += 20
        
        if job.education_requirements:
            score += 15
        
        if job.years_experience_min and job.years_experience_min > 3:
            score += 15
        
        # Add points for seniority
        if job.experience_level in [ExperienceLevel.SENIOR_LEVEL, ExperienceLevel.EXECUTIVE_LEVEL]:
            score += 10
        
        return min(score, 100)
    
    def _calculate_analysis_score(self, analysis_result: Dict[str, Any]) -> float:
        """Calculate analysis quality score."""
        score = 0
        
        # Check completeness
        if analysis_result.get("required_skills"):
            score += 20
        
        if analysis_result.get("keywords"):
            score += 20
        
        if analysis_result.get("requirements"):
            score += 20
        
        if analysis_result.get("category"):
            score += 20
        
        if analysis_result.get("seniority"):
            score += 20
        
        return min(score, 100)


# Export service
__all__ = ["JobDescriptionService"]