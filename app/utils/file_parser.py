"""
Resume file parser for extracting text and structured data from various file formats.
"""

import logging
import re
from pathlib import Path
from typing import Dict, List, Optional, Any
import asyncio

import aiofiles
import PyPDF2
import fitz  # PyMuPDF
from docx import Document
import pandas as pd

logger = logging.getLogger(__name__)


class ResumeParser:
    """Parser for extracting content from resume files."""
    
    def __init__(self):
        self.email_pattern = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b')
        self.phone_pattern = re.compile(r'(\+?1?[-.\s]?)?\(?([0-9]{3})\)?[-.\s]?([0-9]{3})[-.\s]?([0-9]{4})')
        self.url_pattern = re.compile(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+')
        
        # Common section headers
        self.section_patterns = {
            'experience': re.compile(r'\b(experience|work\s+experience|employment|professional\s+experience|career)\b', re.IGNORECASE),
            'education': re.compile(r'\b(education|academic|qualifications|degrees?)\b', re.IGNORECASE),
            'skills': re.compile(r'\b(skills|technical\s+skills|competencies|expertise|proficiencies)\b', re.IGNORECASE),
            'summary': re.compile(r'\b(summary|profile|overview|objective|about)\b', re.IGNORECASE),
            'certifications': re.compile(r'\b(certifications?|certificates?|credentials)\b', re.IGNORECASE),
            'projects': re.compile(r'\b(projects?|portfolio)\b', re.IGNORECASE),
            'achievements': re.compile(r'\b(achievements?|accomplishments?|awards?|honors?)\b', re.IGNORECASE),
            'languages': re.compile(r'\b(languages?|linguistic)\b', re.IGNORECASE),
            'references': re.compile(r'\b(references?)\b', re.IGNORECASE)
        }
    
    async def parse_pdf(self, file_path: Path) -> Dict[str, Any]:
        """Parse PDF resume file."""
        try:
            # Try PyMuPDF first (better text extraction)
            text = await self._extract_pdf_text_pymupdf(file_path)
            if not text.strip():
                # Fallback to PyPDF2
                text = await self._extract_pdf_text_pypdf2(file_path)
            
            # Get page count
            page_count = await self._get_pdf_page_count(file_path)
            
            # Parse content
            structured_data = self._parse_text_content(text)
            
            return {
                "raw_text": text,
                "structured_data": structured_data,
                "word_count": len(text.split()),
                "page_count": page_count,
                "parsing_method": "pdf"
            }
            
        except Exception as e:
            logger.error(f"PDF parsing failed: {file_path}, error: {e}")
            raise Exception(f"Failed to parse PDF: {str(e)}")
    
    async def parse_docx(self, file_path: Path) -> Dict[str, Any]:
        """Parse DOCX resume file."""
        try:
            text = await self._extract_docx_text(file_path)
            structured_data = self._parse_text_content(text)
            
            return {
                "raw_text": text,
                "structured_data": structured_data,
                "word_count": len(text.split()),
                "page_count": 1,  # Approximate for DOCX
                "parsing_method": "docx"
            }
            
        except Exception as e:
            logger.error(f"DOCX parsing failed: {file_path}, error: {e}")
            raise Exception(f"Failed to parse DOCX: {str(e)}")
    
    async def parse_doc(self, file_path: Path) -> Dict[str, Any]:
        """Parse DOC resume file (legacy Word format)."""
        try:
            # For .doc files, we'll try to use python-docx which may work
            # Or use a different library like python-docx2txt
            text = await self._extract_doc_text(file_path)
            structured_data = self._parse_text_content(text)
            
            return {
                "raw_text": text,
                "structured_data": structured_data,
                "word_count": len(text.split()),
                "page_count": 1,
                "parsing_method": "doc"
            }
            
        except Exception as e:
            logger.error(f"DOC parsing failed: {file_path}, error: {e}")
            raise Exception(f"Failed to parse DOC: {str(e)}")
    
    async def parse_text(self, file_path: Path) -> Dict[str, Any]:
        """Parse plain text resume file."""
        try:
            async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
                text = await f.read()
            
            structured_data = self._parse_text_content(text)
            
            return {
                "raw_text": text,
                "structured_data": structured_data,
                "word_count": len(text.split()),
                "page_count": 1,
                "parsing_method": "text"
            }
            
        except Exception as e:
            logger.error(f"Text parsing failed: {file_path}, error: {e}")
            raise Exception(f"Failed to parse text file: {str(e)}")
    
    # Private extraction methods
    async def _extract_pdf_text_pymupdf(self, file_path: Path) -> str:
        """Extract text from PDF using PyMuPDF."""
        def extract():
            doc = fitz.open(str(file_path))
            text = ""
            for page in doc:
                text += page.get_text()
            doc.close()
            return text
        
        return await asyncio.to_thread(extract)
    
    async def _extract_pdf_text_pypdf2(self, file_path: Path) -> str:
        """Extract text from PDF using PyPDF2."""
        def extract():
            text = ""
            with open(file_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                for page in pdf_reader.pages:
                    text += page.extract_text()
            return text
        
        return await asyncio.to_thread(extract)
    
    async def _get_pdf_page_count(self, file_path: Path) -> int:
        """Get PDF page count."""
        def count_pages():
            with open(file_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                return len(pdf_reader.pages)
        
        return await asyncio.to_thread(count_pages)
    
    async def _extract_docx_text(self, file_path: Path) -> str:
        """Extract text from DOCX file."""
        def extract():
            doc = Document(str(file_path))
            text = ""
            for paragraph in doc.paragraphs:
                text += paragraph.text + "\n"
            return text
        
        return await asyncio.to_thread(extract)
    
    async def _extract_doc_text(self, file_path: Path) -> str:
        """Extract text from DOC file."""
        # For legacy .doc files, we might need to use different approaches
        # This is a simplified version - in production, you might want to use
        # tools like antiword or convert to .docx first
        try:
            # Try to read as if it were a docx (might work for some .doc files)
            return await self._extract_docx_text(file_path)
        except:
            # Fallback: basic text extraction (limited)
            async with aiofiles.open(file_path, 'rb') as f:
                content = await f.read()
                # Basic text extraction from binary - very limited
                text = content.decode('utf-8', errors='ignore')
                return self._clean_text(text)
    
    # Content parsing methods
    def _parse_text_content(self, text: str) -> Dict[str, Any]:
        """Parse text content into structured data."""
        cleaned_text = self._clean_text(text)
        
        structured_data = {
            "personal_info": self._extract_personal_info(cleaned_text),
            "sections": self._extract_sections(cleaned_text),
            "skills": self._extract_skills(cleaned_text),
            "education": self._extract_education(cleaned_text),
            "experience": self._extract_experience(cleaned_text),
            "contact_info": self._extract_contact_info(cleaned_text),
            "keywords": self._extract_keywords(cleaned_text)
        }
        
        return structured_data
    
    def _clean_text(self, text: str) -> str:
        """Clean and normalize text."""
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text)
        # Remove special characters that might interfere
        text = re.sub(r'[^\w\s@.,()\-+/]', ' ', text)
        return text.strip()
    
    def _extract_personal_info(self, text: str) -> Dict[str, Any]:
        """Extract personal information."""
        lines = text.split('\n')[:10]  # Check first 10 lines
        
        # Look for name (typically first non-empty line)
        name = None
        for line in lines:
            line = line.strip()
            if line and not self.email_pattern.search(line) and not self.phone_pattern.search(line):
                # Simple heuristic: if line has 2-4 words and looks like a name
                words = line.split()
                if 2 <= len(words) <= 4 and all(word.isalpha() or word.replace('.', '').isalpha() for word in words):
                    name = line
                    break
        
        return {
            "name": name,
            "email": self._extract_email(text),
            "phone": self._extract_phone(text),
            "location": self._extract_location(text),
            "linkedin": self._extract_linkedin(text),
            "website": self._extract_website(text)
        }
    
    def _extract_contact_info(self, text: str) -> Dict[str, Any]:
        """Extract contact information."""
        return {
            "emails": self.email_pattern.findall(text),
            "phones": [match.group() for match in self.phone_pattern.finditer(text)],
            "urls": self.url_pattern.findall(text)
        }
    
    def _extract_email(self, text: str) -> Optional[str]:
        """Extract primary email address."""
        emails = self.email_pattern.findall(text)
        return emails[0] if emails else None
    
    def _extract_phone(self, text: str) -> Optional[str]:
        """Extract primary phone number."""
        phones = self.phone_pattern.findall(text)
        if phones:
            # Format phone number
            phone = phones[0]
            return f"({phone[1]}) {phone[2]}-{phone[3]}"
        return None
    
    def _extract_location(self, text: str) -> Optional[str]:
        """Extract location information."""
        # Look for common location patterns
        location_patterns = [
            r'([A-Z][a-z]+,\s*[A-Z]{2})',  # City, ST
            r'([A-Z][a-z]+,\s*[A-Z][a-z]+)',  # City, State
            r'([A-Z][a-z]+\s*\d{5})',  # City ZIP
        ]
        
        for pattern in location_patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1)
        
        return None
    
    def _extract_linkedin(self, text: str) -> Optional[str]:
        """Extract LinkedIn URL."""
        linkedin_pattern = re.compile(r'linkedin\.com/in/[\w\-]+', re.IGNORECASE)
        match = linkedin_pattern.search(text)
        return f"https://{match.group()}" if match else None
    
    def _extract_website(self, text: str) -> Optional[str]:
        """Extract personal website URL."""
        urls = self.url_pattern.findall(text)
        # Filter out common social media and email URLs
        websites = [url for url in urls if not any(domain in url.lower() 
                   for domain in ['linkedin', 'facebook', 'twitter', 'github', 'mailto'])]
        return websites[0] if websites else None
    
    def _extract_sections(self, text: str) -> Dict[str, str]:
        """Extract resume sections."""
        sections = {}
        lines = text.split('\n')
        current_section = None
        section_content = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Check if line is a section header
            found_section = None
            for section_name, pattern in self.section_patterns.items():
                if pattern.search(line):
                    found_section = section_name
                    break
            
            if found_section:
                # Save previous section
                if current_section and section_content:
                    sections[current_section] = '\n'.join(section_content).strip()
                
                # Start new section
                current_section = found_section
                section_content = []
            elif current_section:
                section_content.append(line)
        
        # Save last section
        if current_section and section_content:
            sections[current_section] = '\n'.join(section_content).strip()
        
        return sections
    
    def _extract_skills(self, text: str) -> List[str]:
        """Extract skills from resume text."""
        # Common technical skills
        tech_skills = [
            'python', 'java', 'javascript', 'c++', 'c#', 'php', 'ruby', 'go', 'rust',
            'react', 'angular', 'vue', 'node.js', 'express', 'django', 'flask',
            'sql', 'mysql', 'postgresql', 'mongodb', 'redis', 'elasticsearch',
            'aws', 'azure', 'gcp', 'docker', 'kubernetes', 'jenkins', 'git',
            'linux', 'windows', 'macos', 'html', 'css', 'sass', 'less',
            'tensorflow', 'pytorch', 'scikit-learn', 'pandas', 'numpy',
            'project management', 'agile', 'scrum', 'leadership', 'communication'
        ]
        
        found_skills = []
        text_lower = text.lower()
        
        for skill in tech_skills:
            if skill.lower() in text_lower:
                found_skills.append(skill)
        
        # Look for skills in dedicated skills section
        sections = self._extract_sections(text)
        if 'skills' in sections:
            skills_text = sections['skills']
            # Extract comma-separated or bullet-pointed skills
            skill_patterns = [
                r'[•\-\*]\s*([^•\-\*\n]+)',  # Bullet points
                r'([^,\n]+)(?:,|$)',  # Comma separated
            ]
            
            for pattern in skill_patterns:
                matches = re.findall(pattern, skills_text)
                for match in matches:
                    skill = match.strip()
                    if skill and len(skill) < 50:  # Reasonable skill length
                        found_skills.append(skill)
        
        return list(set(found_skills))  # Remove duplicates
    
    def _extract_education(self, text: str) -> List[Dict[str, Any]]:
        """Extract education information."""
        education = []
        sections = self._extract_sections(text)
        
        if 'education' not in sections:
            return education
        
        edu_text = sections['education']
        
        # Common degree patterns
        degree_patterns = [
            r'(Bachelor[\'s]*\s+of\s+\w+|B\.?\w*\.?\s+\w+)',
            r'(Master[\'s]*\s+of\s+\w+|M\.?\w*\.?\s+\w+)',
            r'(Doctor\s+of\s+\w+|Ph\.?D\.?\s+\w+)',
            r'(Associate[\'s]*\s+\w+|A\.?\w*\.?\s+\w+)'
        ]
        
        # Extract degree information
        for pattern in degree_patterns:
            matches = re.finditer(pattern, edu_text, re.IGNORECASE)
            for match in matches:
                degree = match.group(1)
                # Try to find associated school and year
                context = edu_text[max(0, match.start()-100):match.end()+100]
                
                # Look for year
                year_match = re.search(r'(19|20)\d{2}', context)
                year = year_match.group() if year_match else None
                
                # Look for school name (capitalize words)
                school_match = re.search(r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\s+(?:University|College|Institute|School))', context)
                school = school_match.group(1) if school_match else None
                
                education.append({
                    'degree': degree,
                    'school': school,
                    'year': year,
                    'field': None  # Could be extracted with more sophisticated parsing
                })
        
        return education
    
    def _extract_experience(self, text: str) -> List[Dict[str, Any]]:
        """Extract work experience information."""
        experience = []
        sections = self._extract_sections(text)
        
        if 'experience' not in sections:
            return experience
        
        exp_text = sections['experience']
        
        # Split by common job entry patterns
        job_entries = re.split(r'\n(?=[A-Z][^a-z]*(?:at|@|\|)\s*[A-Z])', exp_text)
        
        for entry in job_entries:
            if len(entry.strip()) < 20:  # Skip very short entries
                continue
            
            lines = [line.strip() for line in entry.split('\n') if line.strip()]
            if not lines:
                continue
            
            # First line often contains job title and company
            first_line = lines[0]
            
            # Extract job title and company
            title_company_patterns = [
                r'([^@|]+)(?:at|@|\|)\s*(.+)',
                r'(.+?)\s*[-–]\s*(.+)',
            ]
            
            job_title = None
            company = None
            
            for pattern in title_company_patterns:
                match = re.search(pattern, first_line)
                if match:
                    job_title = match.group(1).strip()
                    company = match.group(2).strip()
                    break
            
            # Extract dates
            date_pattern = r'((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{4})\s*[-–]\s*((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{4}|Present|Current)'
            date_match = re.search(date_pattern, entry, re.IGNORECASE)
            
            start_date = None
            end_date = None
            if date_match:
                start_date = date_match.group(1)
                end_date = date_match.group(2)
            
            # Extract job description (remaining lines)
            description = '\n'.join(lines[1:]) if len(lines) > 1 else ''
            
            experience.append({
                'job_title': job_title,
                'company': company,
                'start_date': start_date,
                'end_date': end_date,
                'description': description,
                'location': None  # Could be extracted with more parsing
            })
        
        return experience
    
    def _extract_keywords(self, text: str) -> List[str]:
        """Extract important keywords from resume."""
        # Remove common stop words
        stop_words = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
            'of', 'with', 'by', 'from', 'up', 'about', 'into', 'through', 'during',
            'before', 'after', 'above', 'below', 'between', 'among', 'this', 'that',
            'these', 'those', 'i', 'me', 'my', 'myself', 'we', 'our', 'ours', 'ourselves',
            'you', 'your', 'yours', 'yourself', 'he', 'him', 'his', 'himself', 'she',
            'her', 'hers', 'herself', 'it', 'its', 'itself', 'they', 'them', 'their',
            'theirs', 'themselves', 'what', 'which', 'who', 'whom', 'whose', 'this',
            'that', 'these', 'those', 'am', 'is', 'are', 'was', 'were', 'be', 'been',
            'being', 'have', 'has', 'had', 'having', 'do', 'does', 'did', 'doing',
            'will', 'would', 'could', 'should', 'may', 'might', 'must', 'can', 'shall'
        }
        
        # Extract words and phrases
        words = re.findall(r'\b[a-zA-Z][a-zA-Z0-9+#.]*\b', text.lower())
        
        # Filter and score keywords
        keyword_counts = {}
        for word in words:
            if (len(word) > 2 and 
                word not in stop_words and 
                not word.isdigit()):
                keyword_counts[word] = keyword_counts.get(word, 0) + 1
        
        # Extract multi-word phrases (bigrams and trigrams)
        sentences = re.split(r'[.!?]+', text)
        for sentence in sentences:
            words_in_sentence = re.findall(r'\b[a-zA-Z][a-zA-Z0-9+#.]*\b', sentence.lower())
            
            # Bigrams
            for i in range(len(words_in_sentence) - 1):
                bigram = f"{words_in_sentence[i]} {words_in_sentence[i+1]}"
                if all(word not in stop_words for word in words_in_sentence[i:i+2]):
                    keyword_counts[bigram] = keyword_counts.get(bigram, 0) + 1
            
            # Trigrams
            for i in range(len(words_in_sentence) - 2):
                trigram = f"{words_in_sentence[i]} {words_in_sentence[i+1]} {words_in_sentence[i+2]}"
                if all(word not in stop_words for word in words_in_sentence[i:i+3]):
                    keyword_counts[trigram] = keyword_counts.get(trigram, 0) + 1
        
        # Return top keywords sorted by frequency
        sorted_keywords = sorted(keyword_counts.items(), key=lambda x: x[1], reverse=True)
        return [keyword for keyword, count in sorted_keywords[:50]]  # Top 50 keywords
    
    def extract_structured_resume_data(self, text: str) -> Dict[str, Any]:
        """
        Extract comprehensive structured data from resume text.
        This is the main method for getting all structured information.
        """
        structured_data = self._parse_text_content(text)
        
        # Additional processing for better structure
        structured_data.update({
            "summary": self._extract_summary(text),
            "certifications": self._extract_certifications(text),
            "projects": self._extract_projects(text),
            "languages": self._extract_languages(text),
            "achievements": self._extract_achievements(text)
        })
        
        return structured_data
    
    def _extract_summary(self, text: str) -> Optional[str]:
        """Extract professional summary or objective."""
        sections = self._extract_sections(text)
        return sections.get('summary', None)
    
    def _extract_certifications(self, text: str) -> List[str]:
        """Extract certifications."""
        sections = self._extract_sections(text)
        if 'certifications' not in sections:
            return []
        
        cert_text = sections['certifications']
        # Extract certifications from bullet points or lines
        certs = []
        lines = cert_text.split('\n')
        for line in lines:
            line = line.strip()
            if line and len(line) > 5:  # Reasonable certification name length
                # Clean up bullet points
                clean_line = re.sub(r'^[•\-\*]\s*', '', line)
                if clean_line:
                    certs.append(clean_line)
        
        return certs
    
    def _extract_projects(self, text: str) -> List[Dict[str, str]]:
        """Extract project information."""
        sections = self._extract_sections(text)
        if 'projects' not in sections:
            return []
        
        projects = []
        project_text = sections['projects']
        
        # Split by project entries (similar to experience parsing)
        project_entries = re.split(r'\n(?=[A-Z][^a-z]*(?:[-–]|\s*\n))', project_text)
        
        for entry in project_entries:
            lines = [line.strip() for line in entry.split('\n') if line.strip()]
            if not lines:
                continue
            
            project_name = lines[0]
            description = '\n'.join(lines[1:]) if len(lines) > 1 else ''
            
            projects.append({
                'name': project_name,
                'description': description
            })
        
        return projects
    
    def _extract_languages(self, text: str) -> List[str]:
        """Extract language skills."""
        sections = self._extract_sections(text)
        if 'languages' not in sections:
            return []
        
        lang_text = sections['languages']
        
        # Common languages
        common_languages = [
            'english', 'spanish', 'french', 'german', 'italian', 'portuguese',
            'chinese', 'mandarin', 'japanese', 'korean', 'arabic', 'hindi',
            'russian', 'dutch', 'swedish', 'norwegian', 'danish', 'finnish'
        ]
        
        found_languages = []
        text_lower = lang_text.lower()
        
        for lang in common_languages:
            if lang in text_lower:
                found_languages.append(lang.title())
        
        # Also extract from structured format
        lines = lang_text.split('\n')
        for line in lines:
            line = line.strip()
            if line and len(line) < 30:  # Reasonable language entry length
                # Clean up bullet points and proficiency levels
                clean_line = re.sub(r'^[•\-\*]\s*', '', line)
                clean_line = re.sub(r'\s*[-–]\s*(native|fluent|conversational|basic|intermediate|advanced|beginner)', '', clean_line, flags=re.IGNORECASE)
                if clean_line and clean_line.lower() not in [lang.lower() for lang in found_languages]:
                    found_languages.append(clean_line.title())
        
        return found_languages
    
    def _extract_achievements(self, text: str) -> List[str]:
        """Extract achievements and awards."""
        sections = self._extract_sections(text)
        if 'achievements' not in sections:
            return []
        
        achievements = []
        achievement_text = sections['achievements']
        
        lines = achievement_text.split('\n')
        for line in lines:
            line = line.strip()
            if line and len(line) > 10:  # Reasonable achievement length
                # Clean up bullet points
                clean_line = re.sub(r'^[•\-\*]\s*', '', line)
                if clean_line:
                    achievements.append(clean_line)
        
        return achievements


# Export the parser class
__all__ = ["ResumeParser"]