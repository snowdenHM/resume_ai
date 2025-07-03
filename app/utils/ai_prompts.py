"""
AI prompt templates for resume analysis, optimization, and job matching.
"""

from typing import Dict, List, Optional, Any


class PromptTemplates:
    """Collection of AI prompt templates for various resume operations."""
    
    # System prompts for different AI roles
    SYSTEM_ANALYST = """You are an expert resume analyst with years of experience in HR and recruitment. 
    Your task is to analyze resumes and provide detailed, actionable feedback. Focus on:
    - Content quality and relevance
    - ATS (Applicant Tracking System) compatibility
    - Professional presentation
    - Keyword optimization
    - Industry-specific requirements
    
    Always provide specific, constructive recommendations for improvement."""
    
    SYSTEM_OPTIMIZER = """You are a professional resume writer and career coach specializing in resume optimization.
    Your task is to improve resumes to better match job requirements while maintaining authenticity.
    Focus on:
    - Enhancing content without changing facts
    - Improving keyword density for ATS systems
    - Strengthening action verbs and quantifiable achievements
    - Optimizing format and structure
    - Tailoring content for specific roles
    
    Maintain the candidate's voice and ensure all information remains truthful."""
    
    SYSTEM_EXTRACTOR = """You are a job description analysis expert. Your task is to extract and structure 
    key information from job postings. Focus on:
    - Required and preferred skills
    - Experience requirements
    - Education requirements
    - Key responsibilities
    - Important keywords for ATS matching
    - Company culture indicators
    
    Provide structured, categorized output that can be used for resume matching."""
    
    SYSTEM_MATCHER = """You are an expert at matching candidates to job opportunities. Your task is to 
    analyze the compatibility between resumes and job descriptions. Focus on:
    - Skills alignment
    - Experience relevance
    - Education match
    - Keyword compatibility
    - Cultural fit indicators
    - Gap analysis
    
    Provide detailed scoring and specific recommendations for improvement."""
    
    SYSTEM_WRITER = """You are a professional resume writer specializing in compelling summary statements.
    Your task is to create engaging, targeted resume summaries that:
    - Highlight key strengths and achievements
    - Include relevant keywords
    - Match the target role requirements
    - Maintain professional tone
    - Are concise and impactful (2-4 sentences)
    
    Focus on value proposition and unique selling points."""
    
    def get_analysis_prompt(
        self, 
        resume_text: str, 
        job_description: Optional[str] = None,
        analysis_type: str = "general"
    ) -> str:
        """Generate analysis prompt based on type and context."""
        
        base_prompt = f"""
        Please analyze the following resume and provide detailed feedback.
        
        RESUME TEXT:
        {resume_text}
        
        """
        
        if job_description:
            base_prompt += f"""
        TARGET JOB DESCRIPTION:
        {job_description}
        
        Please provide targeted analysis comparing the resume against this specific job posting.
        """
        
        if analysis_type == "ats_check":
            specific_instructions = """
        Focus specifically on ATS (Applicant Tracking System) compatibility:
        - Keyword density and relevance
        - Format and structure compatibility
        - Section organization
        - File format considerations
        - Common ATS parsing issues
        
        Provide an ATS score (0-100) and specific recommendations for improvement.
        """
        elif analysis_type == "job_match":
            specific_instructions = """
        Focus on job match analysis:
        - Skills alignment with job requirements
        - Experience relevance and level
        - Education match
        - Keyword compatibility
        - Missing qualifications
        - Competitive strengths
        
        Provide match scores for different categories and overall compatibility.
        """
        else:  # general analysis
            specific_instructions = """
        Provide comprehensive resume analysis covering:
        1. Overall Quality Score (0-100)
        2. ATS Compatibility Score (0-100)
        3. Content Quality Score (0-100)
        4. Keyword Optimization Score (0-100)
        5. Format Score (0-100)
        
        For each area, provide:
        - Specific strengths identified
        - Areas for improvement
        - Actionable recommendations
        - Missing keywords or skills
        - Industry-specific suggestions
        """
        
        base_prompt += specific_instructions
        
        base_prompt += """
        
        Please structure your response as JSON with the following format:
        {
            "overall_score": 85,
            "ats_score": 80,
            "content_score": 90,
            "keyword_score": 75,
            "format_score": 85,
            "strengths": ["List of specific strengths"],
            "weaknesses": ["List of areas for improvement"],
            "recommendations": ["List of actionable recommendations"],
            "missing_keywords": ["List of important missing keywords"],
            "extracted_skills": ["List of skills found in resume"],
            "industry_alignment": "Assessment of industry fit",
            "experience_assessment": "Analysis of experience level and relevance"
        }
        """
        
        return base_prompt
    
    def get_optimization_prompt(
        self,
        resume_text: str,
        job_description: str,
        optimization_type: str = "full"
    ) -> str:
        """Generate optimization prompt for resume improvement."""
        
        base_prompt = f"""
        Please optimize the following resume for the target job description.
        
        ORIGINAL RESUME:
        {resume_text}
        
        TARGET JOB DESCRIPTION:
        {job_description}
        
        """
        
        if optimization_type == "keywords":
            specific_instructions = """
        Focus specifically on keyword optimization:
        - Identify important keywords from the job description
        - Naturally integrate missing keywords into existing content
        - Improve keyword density without keyword stuffing
        - Maintain readability and authenticity
        - Prioritize high-impact keywords
        """
        elif optimization_type == "format":
            specific_instructions = """
        Focus on format and structure optimization:
        - Improve section organization and hierarchy
        - Enhance readability and visual appeal
        - Optimize for ATS parsing
        - Improve bullet point structure
        - Strengthen action verbs and quantifiable achievements
        """
        elif optimization_type == "content":
            specific_instructions = """
        Focus on content enhancement:
        - Strengthen achievement statements
        - Add quantifiable results where possible
        - Improve relevance to target role
        - Enhance professional language
        - Remove or minimize less relevant information
        """
        else:  # full optimization
            specific_instructions = """
        Perform comprehensive optimization including:
        1. Content enhancement and relevance improvement
        2. Keyword integration and optimization
        3. Format and structure improvements
        4. ATS compatibility enhancements
        5. Professional language strengthening
        
        Ensure all changes:
        - Maintain factual accuracy
        - Preserve the candidate's authentic voice
        - Improve job match potential
        - Enhance ATS parsing capability
        - Strengthen overall presentation
        """
        
        base_prompt += specific_instructions
        
        base_prompt += """
        
        Please provide:
        1. The complete optimized resume text
        2. A summary of changes made
        3. List of keywords added or enhanced
        4. Sections that were modified
        5. Additional suggestions for further improvement
        
        Structure your response as JSON:
        {
            "optimized_content": "Complete optimized resume text",
            "improvements_made": ["List of improvements"],
            "keywords_added": ["List of keywords integrated"],
            "sections_modified": ["List of sections changed"],
            "suggestions": ["Additional recommendations"]
        }
        """
        
        return base_prompt
    
    def get_extraction_prompt(self, job_description: str) -> str:
        """Generate prompt for extracting structured data from job descriptions."""
        
        prompt = f"""
        Please analyze the following job description and extract structured information.
        
        JOB DESCRIPTION:
        {job_description}
        
        Extract and categorize the following information:
        
        1. Required Skills (technical and soft skills that are mandatory)
        2. Preferred Skills (nice-to-have skills)
        3. Education Requirements (degrees, certifications, etc.)
        4. Experience Requirements (years, specific experience types)
        5. Key Responsibilities (main job duties)
        6. Important Keywords (for ATS matching)
        7. Industry-specific Terms
        8. Role-specific Terminology
        9. Company Culture Indicators
        10. Seniority Level Assessment
        11. Job Category Classification
        
        Also provide quality assessment:
        - Clarity Score (0-100): How clear and well-written is the job description
        - Completeness Score (0-100): How complete is the information provided
        - Specificity Score (0-100): How specific are the requirements
        
        Structure your response as JSON:
        {
            "required_skills": ["List of mandatory skills"],
            "preferred_skills": ["List of preferred skills"],
            "education_requirements": ["List of education requirements"],
            "experience_requirements": ["List of experience requirements"],
            "responsibilities": ["List of key responsibilities"],
            "keywords": ["List of important keywords"],
            "industry_terms": ["Industry-specific terminology"],
            "role_terms": ["Role-specific terminology"],
            "culture_indicators": ["Company culture indicators"],
            "seniority_level": "Entry/Mid/Senior/Executive",
            "category": "Job category/function",
            "clarity_score": 85,
            "completeness_score": 75,
            "specificity_score": 80,
            "suggestions": ["Suggestions for improving job description"],
            "missing_info": ["Important information that's missing"]
        }
        """
        
        return prompt
    
    def get_matching_prompt(self, resume_text: str, job_description: str) -> str:
        """Generate prompt for matching resume to job description."""
        
        prompt = f"""
        Please analyze the compatibility between this resume and job description.
        
        RESUME:
        {resume_text}
        
        JOB DESCRIPTION:
        {job_description}
        
        Perform detailed matching analysis:
        
        1. Overall Match Assessment (0-100 score)
        2. Skills Match Analysis
           - Matched skills between resume and job requirements
           - Missing critical skills
           - Skill level assessment
        3. Experience Match Analysis
           - Relevant experience alignment
           - Experience level compatibility
           - Industry experience relevance
        4. Education Match Analysis
           - Education requirements vs. candidate qualifications
           - Certification alignment
        5. Keyword Match Analysis
           - Matched keywords for ATS optimization
           - Missing important keywords
           - Keyword density assessment
        
        Provide specific recommendations for improving match quality.
        
        Structure your response as JSON:
        {
            "overall_match_score": 78,
            "skills_match_score": 85,
            "experience_match_score": 75,
            "education_match_score": 90,
            "keyword_match_score": 70,
            "matched_skills": ["List of matching skills"],
            "missing_skills": ["List of missing skills"],
            "matched_keywords": ["List of matching keywords"],
            "missing_keywords": ["List of missing keywords"],
            "experience_analysis": "Assessment of experience relevance",
            "education_analysis": "Assessment of education match",
            "recommendations": ["Specific recommendations for improvement"],
            "competitive_strengths": ["Candidate's competitive advantages"],
            "areas_for_development": ["Skills or experience to develop"],
            "match_explanation": "Detailed explanation of match assessment"
        }
        """
        
        return prompt
    
    def get_summary_prompt(
        self, 
        resume_data: Dict[str, Any], 
        job_description: Optional[str] = None
    ) -> str:
        """Generate prompt for creating resume summary/objective."""
        
        # Extract key information from resume data
        experience = resume_data.get("experience", [])
        skills = resume_data.get("skills", [])
        education = resume_data.get("education", [])
        achievements = resume_data.get("achievements", [])
        
        prompt = f"""
        Create a compelling professional summary for a resume based on the following information:
        
        CANDIDATE INFORMATION:
        Experience: {experience}
        Skills: {skills}
        Education: {education}
        Key Achievements: {achievements}
        """
        
        if job_description:
            prompt += f"""
        
        TARGET JOB DESCRIPTION:
        {job_description}
        
        Tailor the summary to align with this specific role and highlight relevant qualifications.
        """
        
        prompt += """
        
        Create a professional summary that:
        1. Is 2-4 sentences long
        2. Highlights the candidate's strongest qualifications
        3. Includes relevant keywords for ATS optimization
        4. Demonstrates value proposition
        5. Matches the target role requirements (if provided)
        6. Uses strong action-oriented language
        7. Quantifies achievements where possible
        
        Focus on the candidate's unique selling points and competitive advantages.
        
        Return only the summary text without additional formatting or explanations.
        """
        
        return prompt
    
    def get_skills_extraction_prompt(self, resume_text: str) -> str:
        """Generate prompt for extracting skills from resume text."""
        
        prompt = f"""
        Extract all skills mentioned in the following resume text and categorize them.
        
        RESUME TEXT:
        {resume_text}
        
        Categorize skills into:
        1. Technical Skills (programming languages, software, tools, technologies)
        2. Soft Skills (communication, leadership, problem-solving, etc.)
        3. Industry Skills (domain-specific knowledge and expertise)
        4. Certifications (professional certifications and licenses)
        5. Languages (spoken/written languages and proficiency levels)
        
        Structure your response as JSON:
        {
            "technical_skills": ["List of technical skills"],
            "soft_skills": ["List of soft skills"],
            "industry_skills": ["List of industry-specific skills"],
            "certifications": ["List of certifications"],
            "languages": ["List of languages with proficiency"],
            "all_skills": ["Complete list of all identified skills"]
        }
        """
        
        return prompt
    
    def get_achievement_enhancement_prompt(self, achievements: List[str]) -> str:
        """Generate prompt for enhancing achievement statements."""
        
        achievements_text = "\n".join([f"- {achievement}" for achievement in achievements])
        
        prompt = f"""
        Enhance the following achievement statements to make them more impactful and quantifiable:
        
        CURRENT ACHIEVEMENTS:
        {achievements_text}
        
        For each achievement, improve by:
        1. Adding quantifiable metrics where possible
        2. Using strong action verbs
        3. Highlighting business impact
        4. Making statements more specific and concrete
        5. Ensuring professional language
        
        Guidelines:
        - Use numbers, percentages, dollar amounts when possible
        - Start with strong action verbs (achieved, increased, reduced, etc.)
        - Focus on business value and impact
        - Keep statements concise but impactful
        - Maintain truthfulness (don't add false metrics)
        
        Return the enhanced achievements as a JSON list:
        {
            "enhanced_achievements": ["List of improved achievement statements"],
            "improvement_notes": ["Explanation of improvements made"]
        }
        """
        
        return prompt


# Export the prompt templates
__all__ = ["PromptTemplates"]