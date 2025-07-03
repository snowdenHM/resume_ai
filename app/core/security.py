"""
Security utilities for authentication, password hashing, and JWT tokens.
"""

import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Union
import uuid

from jose import JWTError, jwt
from passlib.context import CryptContext
from passlib.hash import bcrypt

from app.config import settings


# Password hashing context
pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__rounds=12  # Higher rounds for better security
)


class SecurityManager:
    """Centralized security management class."""
    
    def __init__(self):
        self.pwd_context = pwd_context
        self.algorithm = settings.ALGORITHM
        self.secret_key = settings.SECRET_KEY
        self.access_token_expire_minutes = settings.ACCESS_TOKEN_EXPIRE_MINUTES
        self.refresh_token_expire_days = settings.REFRESH_TOKEN_EXPIRE_DAYS
    
    # Password Management
    def hash_password(self, password: str) -> str:
        """
        Hash a password using bcrypt.
        
        Args:
            password: Plain text password
            
        Returns:
            Hashed password string
        """
        return self.pwd_context.hash(password)
    
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """
        Verify a password against its hash.
        
        Args:
            plain_password: Plain text password
            hashed_password: Hashed password from database
            
        Returns:
            True if password matches, False otherwise
        """
        return self.pwd_context.verify(plain_password, hashed_password)
    
    def validate_password_strength(self, password: str) -> Dict[str, Any]:
        """
        Validate password strength.
        
        Args:
            password: Password to validate
            
        Returns:
            Dictionary with validation results
        """
        issues = []
        score = 0
        
        # Length check
        if len(password) < settings.PASSWORD_MIN_LENGTH:
            issues.append(f"Password must be at least {settings.PASSWORD_MIN_LENGTH} characters long")
        else:
            score += 1
        
        # Character type checks
        has_upper = any(c.isupper() for c in password)
        has_lower = any(c.islower() for c in password)
        has_digit = any(c.isdigit() for c in password)
        has_special = any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password)
        
        if not has_upper:
            issues.append("Password must contain at least one uppercase letter")
        else:
            score += 1
            
        if not has_lower:
            issues.append("Password must contain at least one lowercase letter")
        else:
            score += 1
            
        if not has_digit:
            issues.append("Password must contain at least one digit")
        else:
            score += 1
            
        if not has_special:
            issues.append("Password must contain at least one special character")
        else:
            score += 1
        
        # Common password check
        common_passwords = {
            "password", "123456", "password123", "admin", "qwerty",
            "letmein", "welcome", "monkey", "dragon", "master"
        }
        if password.lower() in common_passwords:
            issues.append("Password is too common")
            score -= 1
        
        # Strength assessment
        if score >= 5:
            strength = "strong"
        elif score >= 3:
            strength = "medium"
        else:
            strength = "weak"
        
        return {
            "is_valid": len(issues) == 0,
            "issues": issues,
            "strength": strength,
            "score": max(0, score)
        }
    
    # Token Management
    def create_access_token(
        self,
        subject: Union[str, uuid.UUID],
        expires_delta: Optional[timedelta] = None,
        additional_claims: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Create a JWT access token.
        
        Args:
            subject: User ID or email
            expires_delta: Custom expiration time
            additional_claims: Additional JWT claims
            
        Returns:
            JWT token string
        """
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(
                minutes=self.access_token_expire_minutes
            )
        
        to_encode = {
            "exp": expire,
            "sub": str(subject),
            "type": "access",
            "iat": datetime.utcnow(),
            "jti": str(uuid.uuid4())  # JWT ID for revocation
        }
        
        if additional_claims:
            to_encode.update(additional_claims)
        
        return jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
    
    def create_refresh_token(
        self,
        subject: Union[str, uuid.UUID],
        expires_delta: Optional[timedelta] = None
    ) -> str:
        """
        Create a JWT refresh token.
        
        Args:
            subject: User ID or email
            expires_delta: Custom expiration time
            
        Returns:
            JWT refresh token string
        """
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(
                days=self.refresh_token_expire_days
            )
        
        to_encode = {
            "exp": expire,
            "sub": str(subject),
            "type": "refresh",
            "iat": datetime.utcnow(),
            "jti": str(uuid.uuid4())
        }
        
        return jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
    
    def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Verify and decode a JWT token.
        
        Args:
            token: JWT token string
            
        Returns:
            Token payload if valid, None otherwise
        """
        try:
            payload = jwt.decode(
                token,
                self.secret_key,
                algorithms=[self.algorithm]
            )
            
            # Check if token is expired
            exp = payload.get("exp")
            if exp and datetime.utcnow() > datetime.fromtimestamp(exp):
                return None
            
            return payload
        except JWTError:
            return None
    
    def get_token_subject(self, token: str) -> Optional[str]:
        """
        Extract subject from JWT token.
        
        Args:
            token: JWT token string
            
        Returns:
            Token subject if valid, None otherwise
        """
        payload = self.verify_token(token)
        if payload:
            return payload.get("sub")
        return None
    
    def is_token_type(self, token: str, token_type: str) -> bool:
        """
        Check if token is of specific type.
        
        Args:
            token: JWT token string
            token_type: Expected token type ('access' or 'refresh')
            
        Returns:
            True if token type matches, False otherwise
        """
        payload = self.verify_token(token)
        if payload:
            return payload.get("type") == token_type
        return False
    
    # Hash utilities
    def generate_secure_token(self, length: int = 32) -> str:
        """
        Generate a cryptographically secure random token.
        
        Args:
            length: Token length in bytes
            
        Returns:
            Hex-encoded secure token
        """
        return secrets.token_hex(length)
    
    def generate_verification_code(self, length: int = 6) -> str:
        """
        Generate a numeric verification code.
        
        Args:
            length: Code length
            
        Returns:
            Numeric verification code
        """
        return ''.join(secrets.choice('0123456789') for _ in range(length))
    
    def hash_token(self, token: str) -> str:
        """
        Create a hash of a token for storage.
        
        Args:
            token: Token to hash
            
        Returns:
            SHA-256 hash of the token
        """
        return hashlib.sha256(token.encode()).hexdigest()
    
    def generate_api_key(self, prefix: str = "ak") -> str:
        """
        Generate an API key.
        
        Args:
            prefix: Key prefix
            
        Returns:
            API key string
        """
        random_part = self.generate_secure_token(16)
        return f"{prefix}_{random_part}"
    
    # Security validation
    def validate_email_format(self, email: str) -> bool:
        """
        Validate email format.
        
        Args:
            email: Email address to validate
            
        Returns:
            True if email format is valid, False otherwise
        """
        import re
        
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email))
    
    def sanitize_filename(self, filename: str) -> str:
        """
        Sanitize filename for safe storage.
        
        Args:
            filename: Original filename
            
        Returns:
            Sanitized filename
        """
        import re
        
        # Remove path separators and dangerous characters
        filename = re.sub(r'[<>:"/\\|?*]', '', filename)
        filename = re.sub(r'\.{2,}', '.', filename)  # Remove multiple dots
        
        # Ensure filename is not empty and not reserved
        if not filename or filename.lower() in ['con', 'prn', 'aux', 'nul']:
            filename = f"file_{self.generate_secure_token(4)}"
        
        return filename[:255]  # Limit length
    
    def check_file_safety(self, file_content: bytes, allowed_types: list) -> Dict[str, Any]:
        """
        Check if uploaded file is safe.
        
        Args:
            file_content: File content bytes
            allowed_types: List of allowed MIME types
            
        Returns:
            Dictionary with safety check results
        """
        import magic
        
        try:
            # Detect file type
            detected_type = magic.from_buffer(file_content, mime=True)
            
            # Check file size
            file_size = len(file_content)
            is_size_ok = file_size <= settings.MAX_FILE_SIZE
            
            # Check if type is allowed
            is_type_allowed = detected_type in allowed_types
            
            # Basic malware detection (check for suspicious patterns)
            suspicious_patterns = [
                b'<script',
                b'javascript:',
                b'vbscript:',
                b'<?php',
                b'<%',
                b'exec(',
                b'system(',
                b'shell_exec('
            ]
            
            has_suspicious_content = any(
                pattern in file_content.lower() for pattern in suspicious_patterns
            )
            
            return {
                "is_safe": is_size_ok and is_type_allowed and not has_suspicious_content,
                "detected_type": detected_type,
                "file_size": file_size,
                "is_size_ok": is_size_ok,
                "is_type_allowed": is_type_allowed,
                "has_suspicious_content": has_suspicious_content
            }
            
        except Exception as e:
            return {
                "is_safe": False,
                "error": str(e),
                "detected_type": None,
                "file_size": len(file_content),
                "is_size_ok": False,
                "is_type_allowed": False,
                "has_suspicious_content": True
            }


# Global security manager instance
security = SecurityManager()


# Convenience functions for backward compatibility
def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    return security.hash_password(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return security.verify_password(plain_password, hashed_password)


def create_access_token(
    subject: Union[str, uuid.UUID],
    expires_delta: Optional[timedelta] = None,
    additional_claims: Optional[Dict[str, Any]] = None
) -> str:
    """Create a JWT access token."""
    return security.create_access_token(subject, expires_delta, additional_claims)


def create_refresh_token(
    subject: Union[str, uuid.UUID],
    expires_delta: Optional[timedelta] = None
) -> str:
    """Create a JWT refresh token."""
    return security.create_refresh_token(subject, expires_delta)


def verify_token(token: str) -> Optional[Dict[str, Any]]:
    """Verify and decode a JWT token."""
    return security.verify_token(token)


def get_token_subject(token: str) -> Optional[str]:
    """Extract subject from JWT token."""
    return security.get_token_subject(token)


def generate_secure_token(length: int = 32) -> str:
    """Generate a cryptographically secure random token."""
    return security.generate_secure_token(length)


def generate_verification_code(length: int = 6) -> str:
    """Generate a numeric verification code."""
    return security.generate_verification_code(length)


def hash_token(token: str) -> str:
    """Create a hash of a token for storage."""
    return security.hash_token(token)


# Rate limiting utilities
class RateLimiter:
    """Simple in-memory rate limiter."""
    
    def __init__(self):
        self._requests = {}
        self._last_cleanup = datetime.utcnow()
    
    def is_allowed(
        self,
        identifier: str,
        max_requests: int = settings.RATE_LIMIT_REQUESTS,
        window_seconds: int = settings.RATE_LIMIT_PERIOD
    ) -> bool:
        """
        Check if request is allowed based on rate limit.
        
        Args:
            identifier: Unique identifier (IP, user ID, etc.)
            max_requests: Maximum requests allowed
            window_seconds: Time window in seconds
            
        Returns:
            True if request is allowed, False otherwise
        """
        now = datetime.utcnow()
        
        # Cleanup old entries every 5 minutes
        if (now - self._last_cleanup).seconds > 300:
            self._cleanup()
            self._last_cleanup = now
        
        # Get current window start
        window_start = now - timedelta(seconds=window_seconds)
        
        # Get or create request list for identifier
        if identifier not in self._requests:
            self._requests[identifier] = []
        
        # Remove old requests outside window
        self._requests[identifier] = [
            req_time for req_time in self._requests[identifier]
            if req_time > window_start
        ]
        
        # Check if under limit
        if len(self._requests[identifier]) < max_requests:
            self._requests[identifier].append(now)
            return True
        
        return False
    
    def _cleanup(self):
        """Remove old entries to prevent memory leaks."""
        cutoff = datetime.utcnow() - timedelta(hours=1)
        
        for identifier in list(self._requests.keys()):
            self._requests[identifier] = [
                req_time for req_time in self._requests[identifier]
                if req_time > cutoff
            ]
            
            # Remove empty entries
            if not self._requests[identifier]:
                del self._requests[identifier]


# Global rate limiter instance
rate_limiter = RateLimiter()


# CSRF protection utilities
def generate_csrf_token() -> str:
    """Generate CSRF token."""
    return security.generate_secure_token(16)


def verify_csrf_token(token: str, session_token: str) -> bool:
    """
    Verify CSRF token.
    
    Args:
        token: CSRF token from request
        session_token: CSRF token from session
        
    Returns:
        True if tokens match, False otherwise
    """
    return secrets.compare_digest(token, session_token)


# Input sanitization
def sanitize_html(text: str) -> str:
    """
    Sanitize HTML content to prevent XSS.
    
    Args:
        text: HTML text to sanitize
        
    Returns:
        Sanitized text
    """
    import html
    return html.escape(text)


def sanitize_sql_identifier(identifier: str) -> str:
    """
    Sanitize SQL identifier (table/column names).
    
    Args:
        identifier: SQL identifier
        
    Returns:
        Sanitized identifier
    """
    import re
    
    # Only allow alphanumeric characters and underscores
    sanitized = re.sub(r'[^a-zA-Z0-9_]', '', identifier)
    
    # Ensure it doesn't start with a number
    if sanitized and sanitized[0].isdigit():
        sanitized = f"_{sanitized}"
    
    return sanitized[:63]  # PostgreSQL identifier limit


# Encryption utilities (for sensitive data at rest)
class DataEncryption:
    """Simple data encryption for sensitive fields."""
    
    def __init__(self, key: Optional[bytes] = None):
        from cryptography.fernet import Fernet
        
        if key:
            self.cipher = Fernet(key)
        else:
            # Generate key from settings
            import base64
            key_material = hashlib.sha256(settings.SECRET_KEY.encode()).digest()
            key = base64.urlsafe_b64encode(key_material)
            self.cipher = Fernet(key)
    
    def encrypt(self, data: str) -> str:
        """Encrypt string data."""
        return self.cipher.encrypt(data.encode()).decode()
    
    def decrypt(self, encrypted_data: str) -> str:
        """Decrypt string data."""
        return self.cipher.decrypt(encrypted_data.encode()).decode()


# Global encryption instance
data_encryption = DataEncryption()


# Export all security utilities
__all__ = [
    "SecurityManager",
    "security",
    "hash_password",
    "verify_password", 
    "create_access_token",
    "create_refresh_token",
    "verify_token",
    "get_token_subject",
    "generate_secure_token",
    "generate_verification_code",
    "hash_token",
    "RateLimiter",
    "rate_limiter",
    "generate_csrf_token",
    "verify_csrf_token",
    "sanitize_html",
    "sanitize_sql_identifier",
    "DataEncryption",
    "data_encryption"
]