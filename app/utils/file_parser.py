"""
File parser utilities for extracting text and structured data from resume files.
"""

import logging
import re
from pathlib import Path
from typing import Dict, List, Optional, Any
import asyncio

import aiofiles
from pdfplumber import PDF
from docx import Document
import fitz  # PyMuPDF as fallback

logger = logging.getLogger(__name__)


class ResumeParser:
    """Parser for extracting content from resume files."""
    
    def __init__(self):
        self.phone_pattern = re.compile(r'(\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}')
        self.email_pattern = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b')
        self.url_pattern = re.compile(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+')
        
        # Common section headers
        self.section_headers = {
            'experience': ['experience', 'work experience', 'employment', 'career history', 'professional experience'],
            'education': ['education', 'academic background', 'qualifications', 'degrees'],
            'skills': ['skills', 'technical skills', 'core competencies', 'expertise', 'abilities'],
            'projects': ['projects', 'key projects', 'notable projects', 'project experience'],
            'certifications': ['certifications', 'certificates', 'professional certifications', 'licenses'],
            'achievements': ['achievements', 'accomplishments', 'honors', 'awards', 'recognition'],
            'summary': ['summary', 'profile', 'objective', 'professional summary', 'career objective'],
            'contact': ['contact', 'contact information', 'personal details']
        }
    
    async def parse_pdf(self, file_path: Path) -> Dict[str, Any]:
        """Parse PDF resume file."""
        try:
            text_content = ""
            page_count = 0
            
            # Try pdfplumber first (better for text extraction)
            try:
                with PDF.open(file_path) as pdf:
                    page_count = len(pdf.pages)
                    for page in pdf.pages:
                        page_text = page.extract_text()
                        if page_text:
                            text_content += page_text + "\n"
            except Exception as e:
                logger.warning(f"pdfplumber failed for {file_path}, trying PyMuPDF: {e}")
                
                # Fallback to PyMuPDF
                doc = fitz.open(file_path)
                page_count = len(doc)
                for page_num in range(page_count):
                    page = doc.load_page(page_num)
                    text_content += page.get_text() + "\n"
                doc.close()
            
            if not text_content.strip():
                raise ValueError("No text content extracted from PDF")
            
            # Extract structured data
            structured_data = await self._extract_structured_data(text_content)
            
            return {
                "raw_text": text_content.strip(),
                "structured_data": structured_data,
                "word_count": len(text_content.split()),
                "page_count": page_count,
                "file_type": "pdf"
            }
            
        except Exception as e:
            logger.error(f"PDF parsing failed for {file_path}: {e}")
            return {
                "raw_text": "",
                "structured_data": {},
                "word_count": 0,
                "page_count": 0,
                "parsing_error": str(e),
                "file_type": "pdf"
            }
    
    async def parse_docx(self, file_path: Path) -> Dict[str, Any]:
        """Parse DOCX resume file."""
        try:
            doc = Document(file_path)
            
            # Extract text from paragraphs
            text_content = ""
            for paragraph in doc.paragraphs:
                text_content += paragraph.text + "\n"
            
            # Extract text from tables
            for table in doc.tables:
                for row in table.rows:
                    for cell in row.cells:
                        text_content += cell.text + " "
                    text_content += "\n"
            
            if not text_content.strip():
                raise ValueError("No text content extracted from DOCX")
            
            # Extract structured data
            structured_data = await self._extract_structured_data(text_content)
            
            # Estimate page count (approximate)
            word_count = len(text_content.split())
            estimated_pages = max(1, (word_count // 300))  # ~300 words per page
            
            return {
                "raw_text": text_content.strip(),
                "structured_data": structured_data,
                "word_count": word_count,
                "page_count": estimated_pages,
                "file_type": "docx"
            }
            
        except Exception as e:
            logger.error(f"DOCX parsing failed for {file_path}: {e}")
            return {
                "raw_text": "",
                "structured_data": {},
                "word_count": 0,
                "page_count": 0,
                "parsing_error": str(e),
                "file_type": "docx"
            }
    
    async def parse_doc(self, file_path: Path) -> Dict[str, Any]:
        """Parse legacy DOC resume file (simplified implementation)."""
        try:
            # For legacy DOC files, we would typically use python-docx2txt or antiword
            # This is a simplified implementation
            
            # Placeholder implementation - in production, use proper DOC parser
            text_content = f"Legacy DOC file parsing not fully implemented: {file_path.name}"
            
            return {
                "raw_text": text_content,
                "structured_data": {},
                "word_count": len(text_content.split()),
                "page_count": 1,
                "file_type": "doc",
                "parsing_note": "Legacy DOC format - consider converting to DOCX"
            }
            
        except Exception as e:
            logger.error(f"DOC parsing failed for {file_path}: {e}")
            return {
                "raw_text": "",
                "structured_data": {},
                "word_count": 0,
                "page_count": 0,
                "parsing_error": str(e),
                "file_type": "doc"
            }
    
    async def parse_text(self, file_path: Path) -> Dict[str, Any]:
        """Parse plain text resume file."""
        try:
            async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
                text_content = await f.read()
            
            if not text_content.strip():
                raise ValueError("File is empty")
            
            # Extract structured data
            structured_data = await self._extract_structured_data(text_content)
            
            # Estimate page count
            word_count = len(text_content.split())
            estimated_pages = max(1, (word_count // 300))
            
            return {
                "raw_text": text_content.strip(),
                "structured_data": structured_data,
                "word_count": word_count,
                "page_count": estimated_pages,
                "file_type": "txt"
            }
            
        except Exception as e:
            logger.error(f"Text parsing failed for {file_path}: {e}")
            return {
                "raw_text": "",
                "structured_data": {},
                "word_count": 0,
                "page_count": 0,
                "parsing_error": str(e),
                "file_type": "txt"
            }
    
    async def _extract_structured_data(self, text: str) -> Dict[str, Any]:
        """Extract structured data from resume text."""
        try:
            structured_data = {}
            
            # Extract contact information
            structured_data["contact_info"] = self._extract_contact_info(text)
            
            # Extract sections
            sections = self._identify_sections(text)
            structured_data.update(sections)
            
            # Extract skills
            structured_data["skills"] = self._extract_skills(text)
            
            # Extract keywords
            structured_data["keywords"] = self._extract_keywords(text)
            
            # Extract dates and experience
            structured_data["experience_years"] = self._calculate_experience_years(text)
            
            return structured_data
            
        except Exception as e:
            logger.warning(f"Structured data extraction failed: {e}")
            return {}
    
    def _extract_contact_info(self, text: str) -> Dict[str, Optional[str]]:
        """Extract contact information from text."""
        contact_info = {
            "email": None,
            "phone": None,
            "urls": []
        }
        
        # Extract email
        email_matches = self.email_pattern.findall(text)
        if email_matches:
            contact_info["email"] = email_matches[0].lower()
        
        # Extract phone
        phone_matches = self.phone_pattern.findall(text)
        if phone_matches:
            # Clean up phone number
            phone = re.sub(r'[^\d+]', '', phone_matches[0])
            contact_info["phone"] = phone
        
        # Extract URLs
        url_matches = self.url_pattern.findall(text)
        contact_info["urls"] = list(set(url_matches))  # Remove duplicates
        
        return contact_info
    
    def _identify_sections(self, text: str) -> Dict[str, Any]:
        """Identify and extract resume sections."""
        sections = {}
        lines = text.split('\n')
        current_section = None
        section_content = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Check if line is a section header
            detected_section = self._detect_section_header(line)
            
            if detected_section:
                # Save previous section
                if current_section and section_content:
                    sections[current_section] = self._process_section_content(
                        current_section, section_content
                    )
                
                # Start new section
                current_section = detected_section
                section_content = []
            elif current_section:
                section_content.append(line)
        
        # Save last section
        if current_section and section_content:
            sections[current_section] = self._process_section_content(
                current_section, section_content
            )
        
        return sections
    
    def _detect_section_header(self, line: str) -> Optional[str]:
        """Detect if a line is a section header."""
        line_lower = line.lower().strip()
        
        # Remove common formatting characters
        clean_line = re.sub(r'[:\-_=*#]+', '', line_lower).strip()
        
        for section_type, headers in self.section_headers.items():
            for header in headers:
                if header in clean_line:
                    return section_type
        
        return None
    
    def _process_section_content(self, section_type: str, content: List[str]) -> Any:
        """Process section content based on section type."""
        if section_type == "experience":
            return self._parse_experience_section(content)
        elif section_type == "education":
            return self._parse_education_section(content)
        elif section_type == "skills":
            return self._parse_skills_section(content)
        elif section_type == "projects":
            return self._parse_projects_section(content)
        else:
            # Return as text for other sections
            return "\n".join(content)
    
    def _parse_experience_section(self, content: List[str]) -> List[Dict[str, str]]:
        """Parse work experience section."""
        experiences = []
        current_job = {}
        
        for line in content:
            # Simple parsing - in production, use more sophisticated NLP
            if self._looks_like_job_title(line):
                if current_job:
                    experiences.append(current_job)
                current_job = {"title": line, "description": []}
            elif current_job:
                current_job["description"].append(line)
        
        if current_job:
            experiences.append(current_job)
        
        # Convert descriptions to text
        for exp in experiences:
            if "description" in exp:
                exp["description"] = "\n".join(exp["description"])
        
        return experiences
    
    def _parse_education_section(self, content: List[str]) -> List[Dict[str, str]]:
        """Parse education section."""
        education = []
        
        for line in content:
            if self._looks_like_degree(line):
                education.append({"degree": line})
        
        return education
    
    def _parse_skills_section(self, content: List[str]) -> List[str]:
        """Parse skills section."""
        skills = []
        
        for line in content:
            # Split by common delimiters
            line_skills = re.split(r'[,;|•\-\n]', line)
            for skill in line_skills:
                skill = skill.strip()
                if skill and len(skill) > 1:
                    skills.append(skill)
        
        return list(set(skills))  # Remove duplicates
    
    def _parse_projects_section(self, content: List[str]) -> List[Dict[str, str]]:
        """Parse projects section."""
        projects = []
        current_project = {}
        
        for line in content:
            if self._looks_like_project_title(line):
                if current_project:
                    projects.append(current_project)
                current_project = {"title": line, "description": []}
            elif current_project:
                current_project["description"].append(line)
        
        if current_project:
            projects.append(current_project)
        
        # Convert descriptions to text
        for proj in projects:
            if "description" in proj:
                proj["description"] = "\n".join(proj["description"])
        
        return projects
    
    def _extract_skills(self, text: str) -> List[str]:
        """Extract skills using keyword matching."""
        # Common technical skills patterns
        skill_patterns = [
            # Programming languages
            r'\b(Python|Java|JavaScript|C\+\+|C#|PHP|Ruby|Go|Rust|Swift|Kotlin)\b',
            # Frameworks
            r'\b(React|Angular|Vue|Django|Flask|Spring|Express|Laravel)\b',
            # Databases
            r'\b(MySQL|PostgreSQL|MongoDB|Redis|SQLite|Oracle)\b',
            # Cloud platforms
            r'\b(AWS|Azure|GCP|Google Cloud|Heroku|DigitalOcean)\b',
            # Tools
            r'\b(Git|Docker|Kubernetes|Jenkins|Terraform|Ansible)\b'
        ]
        
        skills = []
        for pattern in skill_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            skills.extend(matches)
        
        return list(set(skills))
    
    def _extract_keywords(self, text: str) -> List[str]:
        """Extract important keywords from resume."""
        # Remove common stop words and extract meaningful terms
        stop_words = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
            'of', 'with', 'by', 'is', 'are', 'was', 'were', 'been', 'be', 'have',
            'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should'
        }
        
        # Extract words that are likely keywords
        words = re.findall(r'\b[A-Za-z]{3,}\b', text)
        keywords = []
        
        for word in words:
            word_lower = word.lower()
            if (word_lower not in stop_words and 
                len(word) >= 3 and 
                not word_lower.isdigit()):
                keywords.append(word)
        
        # Count frequency and return most common
        from collections import Counter
        word_counts = Counter(keywords)
        
        # Return top 20 most frequent keywords
        return [word for word, count in word_counts.most_common(20)]
    
    def _calculate_experience_years(self, text: str) -> Optional[int]:
        """Calculate years of experience from resume text."""
        # Look for experience patterns
        experience_patterns = [
            r'(\d+)[\+\s]*years?\s+of\s+experience',
            r'(\d+)[\+\s]*years?\s+experience',
            r'over\s+(\d+)\s+years?',
            r'more\s+than\s+(\d+)\s+years?'
        ]
        
        for pattern in experience_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                try:
                    return int(matches[0])
                except ValueError:
                    continue
        
        # Try to calculate from dates in experience section
        years = re.findall(r'\b(19|20)\d{2}\b', text)
        if len(years) >= 2:
            try:
                min_year = min(int(year) for year in years)
                max_year = max(int(year) for year in years)
                return max_year - min_year
            except ValueError:
                pass
        
        return None
    
    def _looks_like_job_title(self, line: str) -> bool:
        """Heuristic to detect if a line looks like a job title."""
        line = line.strip()
        
        # Check for common job title patterns
        job_indicators = [
            'manager', 'director', 'engineer', 'developer', 'analyst',
            'specialist', 'coordinator', 'assistant', 'lead', 'senior',
            'junior', 'intern', 'consultant', 'architect', 'designer'
        ]
        
        line_lower = line.lower()
        for indicator in job_indicators:
            if indicator in line_lower:
                return True
        
        # Check if it's all caps (common for job titles)
        if line.isupper() and len(line.split()) <= 4:
            return True
        
        return False
    
    def _looks_like_degree(self, line: str) -> bool:
        """Heuristic to detect if a line looks like a degree."""
        degree_indicators = [
            'bachelor', 'master', 'phd', 'doctorate', 'associate',
            'certificate', 'diploma', 'b.s.', 'b.a.', 'm.s.', 'm.a.',
            'mba', 'university', 'college', 'institute'
        ]
        
        line_lower = line.lower()
        for indicator in degree_indicators:
            if indicator in line_lower:
                return True
        
        return False
    
    def _looks_like_project_title(self, line: str) -> bool:
        """Heuristic to detect if a line looks like a project title."""
        # Simple heuristic - projects often start with capital letters
        # and don't contain common sentence indicators
        line = line.strip()
        
        if not line:
            return False
        
        # Check if it starts with capital and is not too long
        if (line[0].isupper() and 
            len(line.split()) <= 6 and 
            not line.endswith('.') and
            not line.startswith('•')):
            return True
        
        return False


# Export the parser
__all__ = ["ResumeParser"]