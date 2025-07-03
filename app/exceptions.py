"""
Custom exception classes for the application.
Provides structured error handling with proper HTTP status codes.
"""

from typing import Any, Dict, List, Optional, Union


class CustomHTTPException(Exception):
    """Base custom HTTP exception."""
    
    def __init__(
        self,
        status_code: int,
        detail: str,
        error_code: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None
    ):
        self.status_code = status_code
        self.detail = detail
        self.error_code = error_code or f"HTTP_{status_code}"
        self.headers = headers
        super().__init__(detail)


class ValidationException(Exception):
    """Exception for validation errors."""
    
    def __init__(self, errors: Union[str, List[Dict[str, Any]]]):
        if isinstance(errors, str):
            self.errors = [{"field": "general", "message": errors}]
        else:
            self.errors = errors
        super().__init__("Validation failed")


class AuthenticationException(CustomHTTPException):
    """Exception for authentication failures."""
    
    def __init__(self, detail: str = "Authentication required"):
        super().__init__(
            status_code=401,
            detail=detail,
            error_code="AUTHENTICATION_REQUIRED"
        )


class AuthorizationException(CustomHTTPException):
    """Exception for authorization failures."""
    
    def __init__(self, detail: str = "Insufficient permissions"):
        super().__init__(
            status_code=403,
            detail=detail,
            error_code="INSUFFICIENT_PERMISSIONS"
        )


class NotFoundException(CustomHTTPException):
    """Exception for resource not found."""
    
    def __init__(self, resource: str = "Resource", resource_id: Optional[str] = None):
        detail = f"{resource} not found"
        if resource_id:
            detail += f" (ID: {resource_id})"
        
        super().__init__(
            status_code=404,
            detail=detail,
            error_code="RESOURCE_NOT_FOUND"
        )


class ConflictException(CustomHTTPException):
    """Exception for resource conflicts."""
    
    def __init__(self, detail: str = "Resource conflict"):
        super().__init__(
            status_code=409,
            detail=detail,
            error_code="RESOURCE_CONFLICT"
        )


class RateLimitException(CustomHTTPException):
    """Exception for rate limit exceeded."""
    
    def __init__(self, retry_after: Optional[int] = None):
        detail = "Rate limit exceeded"
        if retry_after:
            detail += f". Retry after {retry_after} seconds"
        
        headers = {}
        if retry_after:
            headers["Retry-After"] = str(retry_after)
        
        super().__init__(
            status_code=429,
            detail=detail,
            error_code="RATE_LIMIT_EXCEEDED",
            headers=headers
        )


class FileProcessingException(CustomHTTPException):
    """Exception for file processing errors."""
    
    def __init__(self, detail: str = "File processing failed"):
        super().__init__(
            status_code=422,
            detail=detail,
            error_code="FILE_PROCESSING_ERROR"
        )


class AIServiceException(CustomHTTPException):
    """Exception for AI service errors."""
    
    def __init__(self, detail: str = "AI service error", service_error: Optional[str] = None):
        if service_error:
            detail += f": {service_error}"
        
        super().__init__(
            status_code=503,
            detail=detail,
            error_code="AI_SERVICE_ERROR"
        )


class DatabaseException(CustomHTTPException):
    """Exception for database errors."""
    
    def __init__(self, detail: str = "Database operation failed"):
        super().__init__(
            status_code=500,
            detail=detail,
            error_code="DATABASE_ERROR"
        )


class ExternalServiceException(CustomHTTPException):
    """Exception for external service errors."""
    
    def __init__(self, service_name: str, detail: Optional[str] = None):
        detail = detail or f"{service_name} service unavailable"
        
        super().__init__(
            status_code=503,
            detail=detail,
            error_code="EXTERNAL_SERVICE_ERROR"
        )


# User-specific exceptions
class UserNotFoundException(NotFoundException):
    """Exception for user not found."""
    
    def __init__(self, user_id: Optional[str] = None):
        super().__init__("User", user_id)


class UserAlreadyExistsException(ConflictException):
    """Exception for user already exists."""
    
    def __init__(self, email: str):
        super().__init__(f"User with email '{email}' already exists")


class InvalidCredentialsException(AuthenticationException):
    """Exception for invalid login credentials."""
    
    def __init__(self):
        super().__init__("Invalid email or password")


class AccountNotVerifiedException(AuthenticationException):
    """Exception for unverified account."""
    
    def __init__(self):
        super().__init__("Account not verified. Please check your email")


class AccountSuspendedException(AuthenticationException):
    """Exception for suspended account."""
    
    def __init__(self):
        super().__init__("Account has been suspended")


class TokenExpiredException(AuthenticationException):
    """Exception for expired token."""
    
    def __init__(self, token_type: str = "Token"):
        super().__init__(f"{token_type} has expired")


class InvalidTokenException(AuthenticationException):
    """Exception for invalid token."""
    
    def __init__(self, token_type: str = "Token"):
        super().__init__(f"Invalid {token_type.lower()}")


# Resume-specific exceptions
class ResumeNotFoundException(NotFoundException):
    """Exception for resume not found."""
    
    def __init__(self, resume_id: Optional[str] = None):
        super().__init__("Resume", resume_id)


class ResumeQuotaExceededException(CustomHTTPException):
    """Exception for resume quota exceeded."""
    
    def __init__(self, max_resumes: int):
        super().__init__(
            status_code=403,
            detail=f"Resume limit reached. Maximum {max_resumes} resumes allowed",
            error_code="RESUME_QUOTA_EXCEEDED"
        )


class InvalidResumeFormatException(FileProcessingException):
    """Exception for invalid resume format."""
    
    def __init__(self, supported_formats: List[str]):
        formats_str = ", ".join(supported_formats)
        super().__init__(f"Invalid resume format. Supported formats: {formats_str}")


class ResumeParsingException(FileProcessingException):
    """Exception for resume parsing errors."""
    
    def __init__(self, parsing_error: str):
        super().__init__(f"Failed to parse resume: {parsing_error}")


# Job description-specific exceptions
class JobDescriptionNotFoundException(NotFoundException):
    """Exception for job description not found."""
    
    def __init__(self, job_id: Optional[str] = None):
        super().__init__("Job description", job_id)


class InvalidJobDescriptionException(ValidationException):
    """Exception for invalid job description."""
    
    def __init__(self, details: str):
        super().__init__(f"Invalid job description: {details}")


# Analysis-specific exceptions
class AnalysisNotFoundException(NotFoundException):
    """Exception for analysis not found."""
    
    def __init__(self, analysis_id: Optional[str] = None):
        super().__init__("Analysis", analysis_id)


class AnalysisFailedException(AIServiceException):
    """Exception for analysis failures."""
    
    def __init__(self, reason: str):
        super().__init__(f"Analysis failed: {reason}")


class OptimizationFailedException(AIServiceException):
    """Exception for optimization failures."""
    
    def __init__(self, reason: str):
        super().__init__(f"Resume optimization failed: {reason}")


# Template-specific exceptions
class TemplateNotFoundException(NotFoundException):
    """Exception for template not found."""
    
    def __init__(self, template_id: Optional[str] = None):
        super().__init__("Template", template_id)


class TemplateRenderingException(CustomHTTPException):
    """Exception for template rendering errors."""
    
    def __init__(self, template_name: str, error: str):
        super().__init__(
            status_code=500,
            detail=f"Failed to render template '{template_name}': {error}",
            error_code="TEMPLATE_RENDERING_ERROR"
        )


# Export-specific exceptions
class ExportFailedException(CustomHTTPException):
    """Exception for export failures."""
    
    def __init__(self, format_type: str, reason: str):
        super().__init__(
            status_code=500,
            detail=f"Failed to export as {format_type}: {reason}",
            error_code="EXPORT_FAILED"
        )


class UnsupportedExportFormatException(CustomHTTPException):
    """Exception for unsupported export format."""
    
    def __init__(self, format_type: str, supported_formats: List[str]):
        formats_str = ", ".join(supported_formats)
        super().__init__(
            status_code=400,
            detail=f"Unsupported export format '{format_type}'. Supported: {formats_str}",
            error_code="UNSUPPORTED_EXPORT_FORMAT"
        )


# File handling exceptions
class FileTooLargeException(CustomHTTPException):
    """Exception for file size exceeded."""
    
    def __init__(self, max_size_mb: int):
        super().__init__(
            status_code=413,
            detail=f"File too large. Maximum size: {max_size_mb}MB",
            error_code="FILE_TOO_LARGE"
        )


class UnsupportedFileTypeException(CustomHTTPException):
    """Exception for unsupported file type."""
    
    def __init__(self, file_type: str, supported_types: List[str]):
        types_str = ", ".join(supported_types)
        super().__init__(
            status_code=415,
            detail=f"Unsupported file type '{file_type}'. Supported: {types_str}",
            error_code="UNSUPPORTED_FILE_TYPE"
        )


class MaliciousFileException(CustomHTTPException):
    """Exception for malicious file detected."""
    
    def __init__(self):
        super().__init__(
            status_code=400,
            detail="File appears to contain malicious content and was rejected",
            error_code="MALICIOUS_FILE_DETECTED"
        )


# Subscription-specific exceptions
class SubscriptionRequiredException(CustomHTTPException):
    """Exception for subscription required."""
    
    def __init__(self, feature: str):
        super().__init__(
            status_code=402,
            detail=f"Premium subscription required for {feature}",
            error_code="SUBSCRIPTION_REQUIRED"
        )


class SubscriptionExpiredException(CustomHTTPException):
    """Exception for expired subscription."""
    
    def __init__(self):
        super().__init__(
            status_code=402,
            detail="Subscription has expired. Please renew to continue",
            error_code="SUBSCRIPTION_EXPIRED"
        )


# Utility functions for exception handling
def create_validation_error(field: str, message: str) -> Dict[str, Any]:
    """Create a validation error dictionary."""
    return {
        "field": field,
        "message": message,
        "type": "validation_error"
    }


def create_multiple_validation_errors(errors: List[tuple]) -> List[Dict[str, Any]]:
    """Create multiple validation errors from tuples."""
    return [
        create_validation_error(field, message)
        for field, message in errors
    ]


def handle_database_error(error: Exception) -> DatabaseException:
    """Convert database errors to custom exceptions."""
    error_str = str(error).lower()
    
    if "unique constraint" in error_str:
        return ConflictException("Resource already exists")
    elif "foreign key constraint" in error_str:
        return ValidationException("Referenced resource does not exist")
    elif "not null constraint" in error_str:
        return ValidationException("Required field is missing")
    else:
        return DatabaseException("Database operation failed")


def handle_ai_service_error(error: Exception, service_name: str = "AI") -> AIServiceException:
    """Convert AI service errors to custom exceptions."""
    error_str = str(error).lower()
    
    if "rate limit" in error_str or "quota" in error_str:
        return RateLimitException()
    elif "authentication" in error_str or "api key" in error_str:
        return AIServiceException(f"{service_name} service authentication failed")
    elif "timeout" in error_str:
        return AIServiceException(f"{service_name} service timeout")
    else:
        return AIServiceException(f"{service_name} service error", str(error))


# Export all exceptions
__all__ = [
    # Base exceptions
    "CustomHTTPException",
    "ValidationException",
    "AuthenticationException",
    "AuthorizationException",
    "NotFoundException",
    "ConflictException",
    "RateLimitException",
    "FileProcessingException",
    "AIServiceException",
    "DatabaseException",
    "ExternalServiceException",
    
    # User exceptions
    "UserNotFoundException",
    "UserAlreadyExistsException",
    "InvalidCredentialsException",
    "AccountNotVerifiedException",
    "AccountSuspendedException",
    "TokenExpiredException",
    "InvalidTokenException",
    
    # Resume exceptions
    "ResumeNotFoundException",
    "ResumeQuotaExceededException",
    "InvalidResumeFormatException",
    "ResumeParsingException",
    
    # Job description exceptions
    "JobDescriptionNotFoundException",
    "InvalidJobDescriptionException",
    
    # Analysis exceptions
    "AnalysisNotFoundException",
    "AnalysisFailedException",
    "OptimizationFailedException",
    
    # Template exceptions
    "TemplateNotFoundException",
    "TemplateRenderingException",
    
    # Export exceptions
    "ExportFailedException",
    "UnsupportedExportFormatException",
    
    # File exceptions
    "FileTooLargeException",
    "UnsupportedFileTypeException",
    "MaliciousFileException",
    
    # Subscription exceptions
    "SubscriptionRequiredException",
    "SubscriptionExpiredException",
    
    # Utility functions
    "create_validation_error",
    "create_multiple_validation_errors",
    "handle_database_error",
    "handle_ai_service_error"
]