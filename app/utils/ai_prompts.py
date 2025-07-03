"""
AI prompt templates for various resume analysis and optimization tasks.
"""

from typing import Dict, Any, Optional


class PromptTemplates:
    """Collection of AI prompt templates for resume processing."""
    
    # System prompts for different AI roles
    SYSTEM_ANALYST = """You are an expert resume analyst and career coach with 15+ years of experience in recruitment and talent acquisition. You specialize in:
- ATS (Applicant Tracking System) optimization
- Resume content analysis and scoring
- Keyword optimization for job matching
- Professional formatting assessment
- Industry-specific resume requirements

Provide detailed, actionable feedback with specific scores and recommendations. Always respond with structured JSON when possible."""

    SYSTEM_OPTIMIZER = """You are a professional resume writer and optimization expert. Your role is to:
- Rewrite and improve resume content for maximum impact
- Optimize resumes for specific job descriptions
- Enhance keyword density while maintaining readability
- Improve formatting and structure for ATS compatibility
- Tailor content to match job requirements

Focus on creating compelling, professional content that highlights achievements and matches job requirements."""

    SYSTEM_EXTRACTOR = """You are a job description analysis expert specializing in:
- Extracting key requirements from job postings
- Identifying required vs. preferred qualifications
- Parsing skills, experience, and education requirements
- Analyzing job responsibilities and expectations
- Extracting important keywords and phrases

Always provide structured, organized output in JSON format when possible."""

    SYSTEM_MATCHER = """You are a resume-job matching specialist with expertise in:
- Calculating compatibility scores between resumes and job descriptions
- Identifying skill gaps and matches
- Analyzing experience relevance
- Keyword matching and optimization
- Providing specific improvement recommendations

Provide detailed matching analysis with numerical scores and actionable insights."""

    SYSTEM_WRITER = """You are a professional content writer specializing in resume summaries and professional statements. You excel at:
- Creating compelling professional summaries
- Writing achievement-focused content
- Adapting tone for different industries and roles
- Highlighting unique value propositions
- Optimizing content for both humans and ATS systems

Write engaging, professional content that stands out to recruiters."""

    def get_analysis_prompt(
        self,
        resume_text: str,
        job_description: Optional[str] = None,
        analysis_type: str = "general"
    ) -> str:
        """Generate resume analysis prompt."""
        
        base_prompt = f"""
Analyze the following resume and provide a comprehensive assessment:

RESUME CONTENT:
{resume_text}

"""
        
        if job_description:
            base_prompt += f"""
TARGET JOB DESCRIPTION:
{job_description}

"""
        
        if analysis_type == "general":
            analysis_instructions = """
Please provide a detailed analysis including:

1. OVERALL ASSESSMENT (0-100 score)
   - Overall resume quality and effectiveness
   - Professional presentation and formatting
   - Content relevance and impact

2. ATS COMPATIBILITY (0-100 score)
   - Keyword optimization
   - Format compatibility with ATS systems
   - Section organization and headers

3. CONTENT QUALITY (0-100 score)
   - Achievement focus vs. responsibility listing
   - Quantifiable results and metrics
   - Professional language and tone

4. FORMATTING & STRUCTURE (0-100 score)
   - Visual appeal and readability
   - Proper use of white space
   - Consistent formatting

5. STRENGTHS
   - List 3-5 key strengths of the resume

6. AREAS FOR IMPROVEMENT
   - List 3-5 specific areas that need improvement

7. RECOMMENDATIONS
   - Provide 5-8 actionable recommendations for improvement

8. SKILLS EXTRACTION
   - List all technical and soft skills found in the resume

Please format your response as JSON with the following structure:
{
    "overall_score": 85,
    "ats_score": 78,
    "content_score": 90,
    "format_score": 82,
    "strengths": ["strength1", "strength2", ...],
    "weaknesses": ["weakness1", "weakness2", ...],
    "recommendations": ["recommendation1", "recommendation2", ...],
    "extracted_skills": ["skill1", "skill2", ...],
    "summary": "Brief overall assessment"
}
"""
        
        elif analysis_type == "job_match":
            analysis_instructions = """
Analyze how well this resume matches the target job description:

1. OVERALL MATCH (0-100 score)
   - How well the resume aligns with job requirements

2. SKILLS MATCH (0-100 score)
   - Technical and soft skills alignment
   - Required vs. preferred skills coverage

3. EXPERIENCE MATCH (0-100 score)
   - Relevant work experience
   - Industry and role alignment
   - Years of experience match

4. KEYWORD OPTIMIZATION (0-100 score)
   - Presence of important job keywords
   - Industry-specific terminology

5. MISSING ELEMENTS
   - Skills not mentioned in resume but required for job
   - Keywords that should be added
   - Experience gaps

6. IMPROVEMENT RECOMMENDATIONS
   - Specific suggestions to improve job match

Format as JSON with match scores and detailed analysis.
"""
        
        elif analysis_type == "ats_check":
            analysis_instructions = """
Focus specifically on ATS (Applicant Tracking System) compatibility:

1. FORMAT COMPATIBILITY
   - File format suitability
   - Header and section recognition
   - Font and formatting issues

2. KEYWORD OPTIMIZATION
   - Relevant keyword density
   - Proper use of industry terminology
   - Job-specific keyword inclusion

3. STRUCTURE ANALYSIS
   - Standard section headers
   - Chronological organization
   - Contact information placement

4. COMMON ATS ISSUES
   - Graphics or images that may cause problems
   - Complex formatting that ATS can't parse
   - Missing essential sections

Provide specific ATS optimization recommendations.
"""
        
        return base_prompt + analysis_instructions

    def get_optimization_prompt(
        self,
        resume_text: str,
        job_description: str,
        optimization_type: str = "full"
    ) -> str:
        """Generate resume optimization prompt."""
        
        prompt = f"""
Optimize the following resume for the target job description:

ORIGINAL RESUME:
{resume_text}

TARGET JOB DESCRIPTION:
{job_description}

"""
        
        if optimization_type == "full":
            optimization_instructions = """
Please provide a comprehensive optimization including:

1. REWRITTEN RESUME CONTENT
   - Optimize for the target job description
   - Improve keyword density naturally
   - Enhance achievement statements with metrics
   - Improve professional language and impact

2. KEY IMPROVEMENTS MADE
   - List specific changes and enhancements
   - Explain why each change improves the resume

3. KEYWORD INTEGRATION
   - Show which keywords were added
   - Explain keyword placement strategy

4. SECTION ENHANCEMENTS
   - Detail improvements to each section
   - Highlight new achievements or better formatting

5. ATS OPTIMIZATION
   - Ensure format is ATS-friendly
   - Use standard section headers
   - Optimize for keyword scanning

Provide the optimized resume in a clean, professional format suitable for immediate use.
"""
        
        elif optimization_type == "keywords":
            optimization_instructions = """
Focus specifically on keyword optimization:

1. Identify all relevant keywords from the job description
2. Integrate keywords naturally into the resume content
3. Improve keyword density without keyword stuffing
4. Use variations and synonyms of important terms
5. Ensure keywords appear in appropriate sections

Provide the keyword-optimized version with explanations of changes made.
"""
        
        elif optimization_type == "format":
            optimization_instructions = """
Focus on formatting and structure optimization:

1. Improve overall visual appeal and readability
2. Ensure ATS-friendly formatting
3. Optimize section organization
4. Improve bullet point structure
5. Enhance professional presentation

Provide the reformatted resume with clean, professional styling.
"""
        
        return prompt + optimization_instructions

    def get_extraction_prompt(self, job_description: str) -> str:
        """Generate job requirements extraction prompt."""
        
        return f"""
Analyze the following job description and extract structured requirements:

JOB DESCRIPTION:
{job_description}

Please extract and organize the following information in JSON format:

{{
    "job_title": "extracted job title",
    "company": "company name if mentioned",
    "required_skills": ["skill1", "skill2", ...],
    "preferred_skills": ["skill1", "skill2", ...],
    "education_requirements": ["requirement1", "requirement2", ...],
    "experience_requirements": {{
        "minimum_years": 3,
        "preferred_years": 5,
        "relevant_experience": ["type1", "type2", ...]
    }},
    "responsibilities": ["responsibility1", "responsibility2", ...],
    "qualifications": ["qualification1", "qualification2", ...],
    "keywords": ["keyword1", "keyword2", ...],
    "industry": "industry sector",
    "job_level": "entry/mid/senior/executive",
    "employment_type": "full-time/part-time/contract",
    "location": "location if specified",
    "salary_range": "salary range if mentioned",
    "benefits": ["benefit1", "benefit2", ...],
    "company_culture": ["culture1", "culture2", ...],
    "nice_to_have": ["nice1", "nice2", ...]
}}

Focus on extracting:
- Technical skills vs. soft skills
- Must-have vs. nice-to-have requirements
- Years of experience needed
- Education level required
- Industry-specific terminology
- Important keywords for ATS optimization
"""

    def get_matching_prompt(self, resume_text: str, job_description: str) -> str:
        """Generate resume-job matching prompt."""
        
        return f"""
Calculate the compatibility between this resume and job description:

RESUME:
{resume_text}

JOB DESCRIPTION:
{job_description}

Provide a detailed matching analysis in JSON format:

{{
    "overall_match_score": 85,
    "breakdown": {{
        "skills_match_score": 80,
        "experience_match_score": 90,
        "education_match_score": 85,
        "keyword_match_score": 75
    }},
    "matched_elements": {{
        "skills": ["matched skill1", "matched skill2", ...],
        "keywords": ["matched keyword1", "matched keyword2", ...],
        "experience": ["relevant experience1", "relevant experience2", ...]
    }},
    "missing_elements": {{
        "skills": ["missing skill1", "missing skill2", ...],
        "keywords": ["missing keyword1", "missing keyword2", ...],
        "experience": ["experience gap1", "experience gap2", ...]
    }},
    "recommendations": [
        "Add experience with X technology",
        "Include more keywords about Y",
        "Highlight achievements in Z area"
    ],
    "match_explanation": "Detailed explanation of the match assessment",
    "improvement_priority": [
        "highest priority improvement",
        "medium priority improvement",
        "lower priority improvement"
    ]
}}

Consider:
- Technical skills alignment
- Industry experience relevance
- Education/certification requirements
- Leadership and soft skills match
- Career progression alignment
- Company culture fit indicators
"""

    def get_summary_prompt(
        self,
        resume_data: Dict[str, Any],
        job_description: Optional[str] = None
    ) -> str:
        """Generate professional summary prompt."""
        
        prompt = f"""
Create a compelling professional summary based on the following resume information:

RESUME DATA:
- Name: {resume_data.get('name', 'Professional')}
- Experience: {resume_data.get('years_experience', 'Multiple years')} years
- Current/Recent Role: {resume_data.get('current_role', 'Professional')}
- Industry: {resume_data.get('industry', 'Various industries')}
- Key Skills: {', '.join(resume_data.get('skills', []))}
- Notable Achievements: {', '.join(resume_data.get('achievements', []))}
- Education: {resume_data.get('education', 'Relevant education')}

"""
        
        if job_description:
            prompt += f"""
TARGET JOB DESCRIPTION:
{job_description}

Create a summary that specifically targets this role and highlights relevant qualifications.
"""
        
        prompt += """
Write a professional summary that:
1. Is 3-4 sentences long (50-80 words)
2. Starts with years of experience and current role
3. Highlights 2-3 key skills or areas of expertise
4. Includes 1-2 notable achievements or value propositions
5. Uses strong action words and professional language
6. Is tailored to the target role (if job description provided)
7. Avoids clichés and generic statements

The summary should immediately capture a recruiter's attention and make them want to read more.

Example format:
"Experienced [Role] with [X] years of expertise in [skill/industry]. Proven track record of [achievement] and [achievement]. Specialized in [skill] and [skill] with demonstrated ability to [value proposition]. Seeking to leverage [relevant experience] to drive [relevant outcome] at [target role/company type]."

Return only the professional summary text, no additional formatting or explanation.
"""
        
        return prompt

    def get_bullet_point_optimization_prompt(self, bullet_points: list, job_keywords: list) -> str:
        """Generate prompt for optimizing resume bullet points."""
        
        return f"""
Optimize these resume bullet points for maximum impact:

ORIGINAL BULLET POINTS:
{chr(10).join(['• ' + point for point in bullet_points])}

TARGET KEYWORDS TO INCORPORATE:
{', '.join(job_keywords)}

Rewrite each bullet point to:
1. Start with strong action verbs
2. Include quantifiable results/metrics where possible
3. Naturally incorporate relevant keywords
4. Focus on achievements rather than just responsibilities
5. Use professional, impactful language
6. Keep each point concise but comprehensive

Guidelines:
- Use past tense for previous roles, present tense for current role
- Include numbers, percentages, dollar amounts when possible
- Show progression and growth
- Highlight leadership and initiative
- Demonstrate problem-solving abilities

Return the optimized bullet points in the same format, one per line with bullet symbols.
"""

    def get_skills_optimization_prompt(self, current_skills: list, job_skills: list) -> str:
        """Generate prompt for optimizing skills section."""
        
        return f"""
Optimize this skills section for the target job:

CURRENT SKILLS:
{', '.join(current_skills)}

REQUIRED JOB SKILLS:
{', '.join(job_skills)}

Create an optimized skills section that:
1. Prioritizes skills mentioned in the job description
2. Groups related skills logically
3. Uses consistent terminology with the job posting
4. Removes outdated or irrelevant skills
5. Adds missing critical skills (if the candidate likely has them)
6. Orders skills by relevance to the target role

Organize skills into categories like:
- Technical Skills
- Programming Languages
- Software/Tools
- Soft Skills
- Certifications

Return the organized skills list with category headers.
"""


# Export the class
__all__ = ["PromptTemplates"]