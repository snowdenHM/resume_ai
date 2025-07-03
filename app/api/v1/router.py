"""
Main API router that combines all v1 endpoints.
"""

from fastapi import APIRouter

from app.api.v1 import auth, resumes, users, job_descriptions, templates, export, analysis

# Create main API router
api_router = APIRouter()

# Include all route modules
api_router.include_router(auth.router)
api_router.include_router(resumes.router)
api_router.include_router(users.router)
api_router.include_router(job_descriptions.router)
api_router.include_router(templates.router)
api_router.include_router(export.router)
api_router.include_router(analysis.router)

# Health check endpoint for the entire API
@api_router.get("/health")
async def api_health():
    """API health check endpoint."""
    return {
        "status": "healthy",
        "version": "1.0.0",
        "message": "AI Resume Builder API is running",
        "endpoints": {
            "auth": "✅ Authentication and user management",
            "resumes": "✅ Resume CRUD, analysis, and optimization", 
            "users": "✅ User profile and preference management",
            "jobs": "✅ Job description management and matching",
            "templates": "✅ Resume templates and customization",
            "export": "✅ Resume export in multiple formats",
            "analysis": "✅ AI-powered analysis and insights"
        },
        "features": {
            "ai_analysis": "✅ Resume analysis with OpenAI/Anthropic",
            "job_matching": "✅ Resume-job compatibility scoring",
            "resume_optimization": "✅ AI-powered resume enhancement",
            "template_system": "✅ Professional resume templates",
            "multi_format_export": "✅ PDF, DOCX, JSON, HTML export",
            "background_processing": "✅ Async AI processing with Celery",
            "user_management": "✅ Complete user lifecycle management",
            "premium_features": "✅ Advanced features for premium users",
            "admin_panel": "✅ Administrative controls and statistics"
        }
    }