"""
AI service for resume analysis, optimization, and job matching.
Integrates with OpenAI and Anthropic APIs.
"""

import asyncio
import json
import logging
import time
from typing import Dict, List, Optional, Any, Tuple
import re

import openai
import anthropic
from anthropic import AsyncAnthropic

from app.config import settings
from app.exceptions import AIServiceException, ValidationException
from app.utils.ai_prompts import PromptTemplates

logger = logging.getLogger(__name__)


class AIService:
    """AI service for resume analysis and optimization."""
    
    def __init__(self):
        self.openai_client = None
        self.anthropic_client = None
        self.prompt_templates = PromptTemplates()
        
        # Initialize clients based on available API keys
        if settings.OPENAI_API_KEY:
            openai.api_key = settings.OPENAI_API_KEY
            self.openai_client = openai
        
        if settings.ANTHROPIC_API_KEY:
            self.anthropic_client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
        
        if not self.openai_client and not self.anthropic_client:
            logger.warning("No AI service configured. Please set OPENAI_API_KEY or ANTHROPIC_API_KEY")
    
    async def analyze_resume(
        self,
        resume_text: str,
        job_description: Optional[str] = None,
        analysis_type: str = "general"
    ) -> Dict[str, Any]:
        """
        Analyze resume content and provide insights.
        
        Args:
            resume_text: Raw resume text
            job_description: Optional job description for targeted analysis
            analysis_type: Type of analysis (general, job_match, ats_check)
            
        Returns:
            Analysis results dictionary
        """
        try:
            start_time = time.time()
            
            # Choose AI provider based on availability and analysis type
            if self.openai_client and analysis_type in ["general", "ats_check"]:
                result = await self._analyze_with_openai(resume_text, job_description, analysis_type)
            elif self.anthropic_client:
                result = await self._analyze_with_anthropic(resume_text, job_description, analysis_type)
            elif self.openai_client:
                result = await self._analyze_with_openai(resume_text, job_description, analysis_type)
            else:
                raise AIServiceException("No AI service available")
            
            processing_time = time.time() - start_time
            result["processing_time"] = processing_time
            result["ai_provider"] = "openai" if self.openai_client and "gpt" in result.get("model", "") else "anthropic"
            
            logger.info(f"Resume analysis completed in {processing_time:.2f}s using {result['ai_provider']}")
            return result
            
        except Exception as e:
            logger.error(f"Resume analysis failed: {e}")
            raise AIServiceException(f"Resume analysis failed: {str(e)}")
    
    async def optimize_resume(
        self,
        resume_text: str,
        job_description: str,
        optimization_type: str = "full"
    ) -> Dict[str, Any]:
        """
        Optimize resume for specific job description.
        
        Args:
            resume_text: Original resume text
            job_description: Target job description
            optimization_type: Type of optimization (full, keywords, format)
            
        Returns:
            Optimization results with improved resume
        """
        try:
            start_time = time.time()
            
            # Use Claude for optimization as it's better at content generation
            if self.anthropic_client:
                result = await self._optimize_with_anthropic(resume_text, job_description, optimization_type)
            elif self.openai_client:
                result = await self._optimize_with_openai(resume_text, job_description, optimization_type)
            else:
                raise AIServiceException("No AI service available for optimization")
            
            processing_time = time.time() - start_time
            result["processing_time"] = processing_time
            
            logger.info(f"Resume optimization completed in {processing_time:.2f}s")
            return result
            
        except Exception as e:
            logger.error(f"Resume optimization failed: {e}")
            raise AIServiceException(f"Resume optimization failed: {str(e)}")
    
    async def extract_job_requirements(self, job_description: str) -> Dict[str, Any]:
        """
        Extract structured requirements from job description.
        
        Args:
            job_description: Raw job description text
            
        Returns:
            Structured job requirements
        """
        try:
            # Use whichever AI service is available
            if self.anthropic_client:
                result = await self._extract_requirements_anthropic(job_description)
            elif self.openai_client:
                result = await self._extract_requirements_openai(job_description)
            else:
                raise AIServiceException("No AI service available")
            
            logger.info("Job requirements extracted successfully")
            return result
            
        except Exception as e:
            logger.error(f"Job requirements extraction failed: {e}")
            raise AIServiceException(f"Job requirements extraction failed: {str(e)}")
    
    async def match_resume_to_job(
        self,
        resume_text: str,
        job_description: str
    ) -> Dict[str, Any]:
        """
        Calculate match score between resume and job description.
        
        Args:
            resume_text: Resume content
            job_description: Job description text
            
        Returns:
            Match analysis with scores and recommendations
        """
        try:
            start_time = time.time()
            
            # Use the best available AI service for matching
            if self.anthropic_client:
                result = await self._match_with_anthropic(resume_text, job_description)
            elif self.openai_client:
                result = await self._match_with_openai(resume_text, job_description)
            else:
                raise AIServiceException("No AI service available")
            
            processing_time = time.time() - start_time
            result["processing_time"] = processing_time
            
            logger.info(f"Resume-job matching completed in {processing_time:.2f}s")
            return result
            
        except Exception as e:
            logger.error(f"Resume-job matching failed: {e}")
            raise AIServiceException(f"Resume-job matching failed: {str(e)}")
    
    async def generate_resume_summary(
        self,
        resume_data: Dict[str, Any],
        job_description: Optional[str] = None
    ) -> str:
        """
        Generate optimized resume summary/objective.
        
        Args:
            resume_data: Structured resume data
            job_description: Optional target job description
            
        Returns:
            Generated summary text
        """
        try:
            if self.anthropic_client:
                summary = await self._generate_summary_anthropic(resume_data, job_description)
            elif self.openai_client:
                summary = await self._generate_summary_openai(resume_data, job_description)
            else:
                raise AIServiceException("No AI service available")
            
            logger.info("Resume summary generated successfully")
            return summary
            
        except Exception as e:
            logger.error(f"Summary generation failed: {e}")
            raise AIServiceException(f"Summary generation failed: {str(e)}")
    
    # OpenAI Implementation Methods
    async def _analyze_with_openai(
        self,
        resume_text: str,
        job_description: Optional[str],
        analysis_type: str
    ) -> Dict[str, Any]:
        """Analyze resume using OpenAI GPT."""
        prompt = self.prompt_templates.get_analysis_prompt(
            resume_text, job_description, analysis_type
        )
        
        try:
            response = await asyncio.to_thread(
                self.openai_client.ChatCompletion.create,
                model=settings.AI_MODEL,
                messages=[
                    {"role": "system", "content": self.prompt_templates.SYSTEM_ANALYST},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=settings.AI_MAX_TOKENS,
                temperature=settings.AI_TEMPERATURE,
                timeout=settings.AI_TIMEOUT
            )
            
            content = response.choices[0].message.content
            result = self._parse_ai_response(content)
            result["model"] = settings.AI_MODEL
            result["tokens_used"] = response.usage.total_tokens
            
            return result
            
        except Exception as e:
            raise AIServiceException(f"OpenAI analysis failed: {str(e)}")
    
    async def _optimize_with_openai(
        self,
        resume_text: str,
        job_description: str,
        optimization_type: str
    ) -> Dict[str, Any]:
        """Optimize resume using OpenAI GPT."""
        prompt = self.prompt_templates.get_optimization_prompt(
            resume_text, job_description, optimization_type
        )
        
        try:
            response = await asyncio.to_thread(
                self.openai_client.ChatCompletion.create,
                model=settings.AI_MODEL,
                messages=[
                    {"role": "system", "content": self.prompt_templates.SYSTEM_OPTIMIZER},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=settings.AI_MAX_TOKENS,
                temperature=0.3,  # Lower temperature for optimization
                timeout=settings.AI_TIMEOUT
            )
            
            content = response.choices[0].message.content
            result = self._parse_optimization_response(content)
            result["model"] = settings.AI_MODEL
            result["tokens_used"] = response.usage.total_tokens
            
            return result
            
        except Exception as e:
            raise AIServiceException(f"OpenAI optimization failed: {str(e)}")
    
    async def _extract_requirements_openai(self, job_description: str) -> Dict[str, Any]:
        """Extract job requirements using OpenAI."""
        prompt = self.prompt_templates.get_extraction_prompt(job_description)
        
        try:
            response = await asyncio.to_thread(
                self.openai_client.ChatCompletion.create,
                model=settings.AI_MODEL,
                messages=[
                    {"role": "system", "content": self.prompt_templates.SYSTEM_EXTRACTOR},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=2000,
                temperature=0.1,  # Very low temperature for extraction
                timeout=settings.AI_TIMEOUT
            )
            
            content = response.choices[0].message.content
            return self._parse_extraction_response(content)
            
        except Exception as e:
            raise AIServiceException(f"OpenAI extraction failed: {str(e)}")
    
    async def _match_with_openai(
        self,
        resume_text: str,
        job_description: str
    ) -> Dict[str, Any]:
        """Match resume to job using OpenAI."""
        prompt = self.prompt_templates.get_matching_prompt(resume_text, job_description)
        
        try:
            response = await asyncio.to_thread(
                self.openai_client.ChatCompletion.create,
                model=settings.AI_MODEL,
                messages=[
                    {"role": "system", "content": self.prompt_templates.SYSTEM_MATCHER},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=settings.AI_MAX_TOKENS,
                temperature=0.2,
                timeout=settings.AI_TIMEOUT
            )
            
            content = response.choices[0].message.content
            return self._parse_matching_response(content)
            
        except Exception as e:
            raise AIServiceException(f"OpenAI matching failed: {str(e)}")
    
    async def _generate_summary_openai(
        self,
        resume_data: Dict[str, Any],
        job_description: Optional[str]
    ) -> str:
        """Generate summary using OpenAI."""
        prompt = self.prompt_templates.get_summary_prompt(resume_data, job_description)
        
        try:
            response = await asyncio.to_thread(
                self.openai_client.ChatCompletion.create,
                model=settings.AI_MODEL,
                messages=[
                    {"role": "system", "content": self.prompt_templates.SYSTEM_WRITER},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=300,
                temperature=0.4,
                timeout=settings.AI_TIMEOUT
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            raise AIServiceException(f"OpenAI summary generation failed: {str(e)}")
    
    # Anthropic Implementation Methods
    async def _analyze_with_anthropic(
        self,
        resume_text: str,
        job_description: Optional[str],
        analysis_type: str
    ) -> Dict[str, Any]:
        """Analyze resume using Anthropic Claude."""
        prompt = self.prompt_templates.get_analysis_prompt(
            resume_text, job_description, analysis_type
        )
        
        try:
            message = await self.anthropic_client.messages.create(
                model="claude-3-sonnet-20240229",
                max_tokens=settings.AI_MAX_TOKENS,
                temperature=settings.AI_TEMPERATURE,
                system=self.prompt_templates.SYSTEM_ANALYST,
                messages=[{"role": "user", "content": prompt}]
            )
            
            content = message.content[0].text
            result = self._parse_ai_response(content)
            result["model"] = "claude-3-sonnet"
            result["tokens_used"] = message.usage.input_tokens + message.usage.output_tokens
            
            return result
            
        except Exception as e:
            raise AIServiceException(f"Anthropic analysis failed: {str(e)}")
    
    async def _optimize_with_anthropic(
        self,
        resume_text: str,
        job_description: str,
        optimization_type: str
    ) -> Dict[str, Any]:
        """Optimize resume using Anthropic Claude."""
        prompt = self.prompt_templates.get_optimization_prompt(
            resume_text, job_description, optimization_type
        )
        
        try:
            message = await self.anthropic_client.messages.create(
                model="claude-3-sonnet-20240229",
                max_tokens=settings.AI_MAX_TOKENS,
                temperature=0.3,
                system=self.prompt_templates.SYSTEM_OPTIMIZER,
                messages=[{"role": "user", "content": prompt}]
            )
            
            content = message.content[0].text
            result = self._parse_optimization_response(content)
            result["model"] = "claude-3-sonnet"
            result["tokens_used"] = message.usage.input_tokens + message.usage.output_tokens
            
            return result
            
        except Exception as e:
            raise AIServiceException(f"Anthropic optimization failed: {str(e)}")
    
    async def _extract_requirements_anthropic(self, job_description: str) -> Dict[str, Any]:
        """Extract job requirements using Anthropic Claude."""
        prompt = self.prompt_templates.get_extraction_prompt(job_description)
        
        try:
            message = await self.anthropic_client.messages.create(
                model="claude-3-sonnet-20240229",
                max_tokens=2000,
                temperature=0.1,
                system=self.prompt_templates.SYSTEM_EXTRACTOR,
                messages=[{"role": "user", "content": prompt}]
            )
            
            content = message.content[0].text
            return self._parse_extraction_response(content)
            
        except Exception as e:
            raise AIServiceException(f"Anthropic extraction failed: {str(e)}")
    
    async def _match_with_anthropic(
        self,
        resume_text: str,
        job_description: str
    ) -> Dict[str, Any]:
        """Match resume to job using Anthropic Claude."""
        prompt = self.prompt_templates.get_matching_prompt(resume_text, job_description)
        
        try:
            message = await self.anthropic_client.messages.create(
                model="claude-3-sonnet-20240229",
                max_tokens=settings.AI_MAX_TOKENS,
                temperature=0.2,
                system=self.prompt_templates.SYSTEM_MATCHER,
                messages=[{"role": "user", "content": prompt}]
            )
            
            content = message.content[0].text
            return self._parse_matching_response(content)
            
        except Exception as e:
            raise AIServiceException(f"Anthropic matching failed: {str(e)}")
    
    async def _generate_summary_anthropic(
        self,
        resume_data: Dict[str, Any],
        job_description: Optional[str]
    ) -> str:
        """Generate summary using Anthropic Claude."""
        prompt = self.prompt_templates.get_summary_prompt(resume_data, job_description)
        
        try:
            message = await self.anthropic_client.messages.create(
                model="claude-3-sonnet-20240229",
                max_tokens=300,
                temperature=0.4,
                system=self.prompt_templates.SYSTEM_WRITER,
                messages=[{"role": "user", "content": prompt}]
            )
            
            return message.content[0].text.strip()
            
        except Exception as e:
            raise AIServiceException(f"Anthropic summary generation failed: {str(e)}")
    
    # Response Parsing Methods
    def _parse_ai_response(self, content: str) -> Dict[str, Any]:
        """Parse AI analysis response into structured data."""
        try:
            # Try to extract JSON from the response
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            
            # Fallback to structured parsing
            result = {
                "overall_score": self._extract_score(content, "overall"),
                "ats_score": self._extract_score(content, "ats"),
                "content_score": self._extract_score(content, "content"),
                "keyword_score": self._extract_score(content, "keyword"),
                "format_score": self._extract_score(content, "format"),
                "strengths": self._extract_list(content, "strengths"),
                "weaknesses": self._extract_list(content, "weaknesses"),
                "recommendations": self._extract_list(content, "recommendations"),
                "missing_keywords": self._extract_list(content, "missing keywords"),
                "extracted_skills": self._extract_list(content, "skills"),
                "raw_response": content
            }
            
            return result
            
        except Exception as e:
            logger.warning(f"Failed to parse AI response: {e}")
            return {
                "overall_score": 0,
                "raw_response": content,
                "parse_error": str(e)
            }
    
    def _parse_optimization_response(self, content: str) -> Dict[str, Any]:
        """Parse optimization response."""
        try:
            # Extract the optimized resume content
            sections = {
                "optimized_content": content,
                "improvements_made": self._extract_list(content, "improvements"),
                "keywords_added": self._extract_list(content, "keywords added"),
                "sections_modified": self._extract_list(content, "sections modified"),
                "suggestions": self._extract_list(content, "suggestions")
            }
            
            return sections
            
        except Exception as e:
            logger.warning(f"Failed to parse optimization response: {e}")
            return {"optimized_content": content, "parse_error": str(e)}
    
    def _parse_extraction_response(self, content: str) -> Dict[str, Any]:
        """Parse job requirements extraction response."""
        try:
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            
            # Fallback extraction
            return {
                "required_skills": self._extract_list(content, "required skills"),
                "preferred_skills": self._extract_list(content, "preferred skills"),
                "education_requirements": self._extract_list(content, "education"),
                "experience_requirements": self._extract_list(content, "experience"),
                "responsibilities": self._extract_list(content, "responsibilities"),
                "keywords": self._extract_list(content, "keywords"),
                "raw_response": content
            }
            
        except Exception as e:
            logger.warning(f"Failed to parse extraction response: {e}")
            return {"raw_response": content, "parse_error": str(e)}
    
    def _parse_matching_response(self, content: str) -> Dict[str, Any]:
        """Parse resume-job matching response."""
        try:
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            
            # Fallback parsing
            return {
                "overall_match_score": self._extract_score(content, "overall"),
                "skills_match_score": self._extract_score(content, "skills"),
                "experience_match_score": self._extract_score(content, "experience"),
                "education_match_score": self._extract_score(content, "education"),
                "keyword_match_score": self._extract_score(content, "keyword"),
                "matched_skills": self._extract_list(content, "matched skills"),
                "missing_skills": self._extract_list(content, "missing skills"),
                "matched_keywords": self._extract_list(content, "matched keywords"),
                "missing_keywords": self._extract_list(content, "missing keywords"),
                "recommendations": self._extract_list(content, "recommendations"),
                "raw_response": content
            }
            
        except Exception as e:
            logger.warning(f"Failed to parse matching response: {e}")
            return {"overall_match_score": 0, "raw_response": content, "parse_error": str(e)}
    
    # Helper Methods
    def _extract_score(self, text: str, score_type: str) -> float:
        """Extract numerical score from text."""
        patterns = [
            rf"{score_type}[:\s]*(\d+(?:\.\d+)?)",
            rf"(\d+(?:\.\d+)?)[%\s]*{score_type}",
            rf"{score_type}[:\s]*(\d+(?:\.\d+)?)[%/]"
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                score = float(match.group(1))
                return min(score, 100.0)  # Cap at 100
        
        return 0.0
    
    def _extract_list(self, text: str, list_type: str) -> List[str]:
        """Extract list items from text."""
        # Look for patterns like "Strengths: - item1 - item2" or "• item1 • item2"
        pattern = rf"{list_type}[:\s]*\n?((?:[-•*]\s*[^\n]+\n?)+)"
        match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        
        if match:
            items_text = match.group(1)
            items = re.findall(r'[-•*]\s*([^\n]+)', items_text)
            return [item.strip() for item in items if item.strip()]
        
        return []
    
    async def get_service_status(self) -> Dict[str, Any]:
        """Get AI service status and capabilities."""
        status = {
            "available_services": [],
            "preferred_service": None,
            "capabilities": {
                "resume_analysis": False,
                "resume_optimization": False,
                "job_matching": False,
                "requirements_extraction": False,
                "summary_generation": False
            }
        }
        
        if self.openai_client:
            status["available_services"].append("openai")
            status["preferred_service"] = "openai"
            for capability in status["capabilities"]:
                status["capabilities"][capability] = True
        
        if self.anthropic_client:
            status["available_services"].append("anthropic")
            if not status["preferred_service"]:
                status["preferred_service"] = "anthropic"
            for capability in status["capabilities"]:
                status["capabilities"][capability] = True
        
        return status


# Export service
__all__ = ["AIService"]