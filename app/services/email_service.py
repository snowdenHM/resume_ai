"""
Email service for sending notifications, verification emails, and alerts.
"""

import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from typing import List, Optional, Dict, Any
import asyncio
from jinja2 import Environment, FileSystemLoader, Template
import aiofiles
import os

from app.config import settings

logger = logging.getLogger(__name__)


class EmailService:
    """Email service for sending various types of emails."""
    
    def __init__(self):
        self.smtp_server = settings.SMTP_HOST
        self.smtp_port = settings.SMTP_PORT or (587 if settings.SMTP_TLS else 25)
        self.smtp_username = settings.SMTP_USER
        self.smtp_password = settings.SMTP_PASSWORD
        self.use_tls = settings.SMTP_TLS
        self.from_email = settings.EMAILS_FROM_EMAIL
        self.from_name = settings.EMAILS_FROM_NAME
        
        # Initialize Jinja2 environment for email templates
        template_dir = os.path.join(os.path.dirname(__file__), '..', 'templates', 'emails')
        self.jinja_env = Environment(
            loader=FileSystemLoader(template_dir) if os.path.exists(template_dir) else None
        )
    
    async def send_email(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: Optional[str] = None,
        attachments: Optional[List[Dict[str, Any]]] = None,
        cc: Optional[List[str]] = None,
        bcc: Optional[List[str]] = None
    ) -> bool:
        """
        Send email with HTML and optional text content.
        
        Args:
            to_email: Recipient email address
            subject: Email subject
            html_content: HTML email content
            text_content: Plain text content (optional)
            attachments: List of attachments (optional)
            cc: CC recipients (optional)
            bcc: BCC recipients (optional)
            
        Returns:
            True if email sent successfully, False otherwise
        """
        if not self._is_configured():
            logger.warning("Email service not configured, skipping email send")
            return False
        
        try:
            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = f"{self.from_name} <{self.from_email}>" if self.from_name else self.from_email
            msg['To'] = to_email
            
            if cc:
                msg['Cc'] = ', '.join(cc)
            if bcc:
                msg['Bcc'] = ', '.join(bcc)
            
            # Add text content
            if text_content:
                text_part = MIMEText(text_content, 'plain')
                msg.attach(text_part)
            
            # Add HTML content
            html_part = MIMEText(html_content, 'html')
            msg.attach(html_part)
            
            # Add attachments
            if attachments:
                for attachment in attachments:
                    await self._add_attachment(msg, attachment)
            
            # Send email
            await self._send_smtp_email(msg, to_email, cc, bcc)
            
            logger.info(f"Email sent successfully to {to_email}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {e}")
            return False
    
    async def send_verification_email(
        self,
        email: str,
        user_name: str,
        verification_token: str
    ) -> bool:
        """
        Send email verification email.
        
        Args:
            email: User email address
            user_name: User's name
            verification_token: Email verification token
            
        Returns:
            True if sent successfully
        """
        try:
            verification_url = f"{settings.FRONTEND_URL}/verify-email?token={verification_token}" if hasattr(settings, 'FRONTEND_URL') else f"http://localhost:3000/verify-email?token={verification_token}"
            
            context = {
                'user_name': user_name,
                'verification_url': verification_url,
                'app_name': settings.APP_NAME,
                'token': verification_token
            }
            
            # Try to use template if available
            if self.jinja_env:
                try:
                    template = self.jinja_env.get_template('verification.html')
                    html_content = template.render(**context)
                except Exception:
                    html_content = self._get_verification_html_fallback(context)
            else:
                html_content = self._get_verification_html_fallback(context)
            
            text_content = f"""
Hello {user_name},

Welcome to {settings.APP_NAME}!

Please verify your email address by clicking the link below:
{verification_url}

Or copy and paste this verification code: {verification_token}

If you didn't create this account, please ignore this email.

Best regards,
The {settings.APP_NAME} Team
            """.strip()
            
            return await self.send_email(
                to_email=email,
                subject=f"Verify your {settings.APP_NAME} account",
                html_content=html_content,
                text_content=text_content
            )
            
        except Exception as e:
            logger.error(f"Failed to send verification email to {email}: {e}")
            return False
    
    async def send_password_reset_email(
        self,
        email: str,
        user_name: str,
        reset_token: str
    ) -> bool:
        """
        Send password reset email.
        
        Args:
            email: User email address
            user_name: User's name
            reset_token: Password reset token
            
        Returns:
            True if sent successfully
        """
        try:
            reset_url = f"{settings.FRONTEND_URL}/reset-password?token={reset_token}" if hasattr(settings, 'FRONTEND_URL') else f"http://localhost:3000/reset-password?token={reset_token}"
            
            context = {
                'user_name': user_name,
                'reset_url': reset_url,
                'app_name': settings.APP_NAME,
                'token': reset_token
            }
            
            # Try to use template if available
            if self.jinja_env:
                try:
                    template = self.jinja_env.get_template('password_reset.html')
                    html_content = template.render(**context)
                except Exception:
                    html_content = self._get_password_reset_html_fallback(context)
            else:
                html_content = self._get_password_reset_html_fallback(context)
            
            text_content = f"""
Hello {user_name},

You requested a password reset for your {settings.APP_NAME} account.

Click the link below to reset your password:
{reset_url}

Or copy and paste this reset code: {reset_token}

This link will expire in 1 hour for security reasons.

If you didn't request this reset, please ignore this email.

Best regards,
The {settings.APP_NAME} Team
            """.strip()
            
            return await self.send_email(
                to_email=email,
                subject=f"Reset your {settings.APP_NAME} password",
                html_content=html_content,
                text_content=text_content
            )
            
        except Exception as e:
            logger.error(f"Failed to send password reset email to {email}: {e}")
            return False
    
    async def send_welcome_email(
        self,
        email: str,
        user_name: str
    ) -> bool:
        """
        Send welcome email after successful registration.
        
        Args:
            email: User email address
            user_name: User's name
            
        Returns:
            True if sent successfully
        """
        try:
            context = {
                'user_name': user_name,
                'app_name': settings.APP_NAME,
                'login_url': f"{settings.FRONTEND_URL}/login" if hasattr(settings, 'FRONTEND_URL') else "http://localhost:3000/login",
                'dashboard_url': f"{settings.FRONTEND_URL}/dashboard" if hasattr(settings, 'FRONTEND_URL') else "http://localhost:3000/dashboard"
            }
            
            # Try to use template if available
            if self.jinja_env:
                try:
                    template = self.jinja_env.get_template('welcome.html')
                    html_content = template.render(**context)
                except Exception:
                    html_content = self._get_welcome_html_fallback(context)
            else:
                html_content = self._get_welcome_html_fallback(context)
            
            text_content = f"""
Welcome to {settings.APP_NAME}, {user_name}!

Your account has been successfully verified and is ready to use.

Get started by:
1. Uploading your first resume
2. Adding job descriptions you're interested in
3. Using our AI to optimize your resume

Visit your dashboard: {context['dashboard_url']}

Best regards,
The {settings.APP_NAME} Team
            """.strip()
            
            return await self.send_email(
                to_email=email,
                subject=f"Welcome to {settings.APP_NAME}!",
                html_content=html_content,
                text_content=text_content
            )
            
        except Exception as e:
            logger.error(f"Failed to send welcome email to {email}: {e}")
            return False
    
    async def send_resume_analysis_complete_email(
        self,
        email: str,
        user_name: str,
        resume_title: str,
        analysis_score: float,
        recommendations_count: int
    ) -> bool:
        """
        Send notification when resume analysis is complete.
        
        Args:
            email: User email address
            user_name: User's name
            resume_title: Title of analyzed resume
            analysis_score: Analysis score
            recommendations_count: Number of recommendations
            
        Returns:
            True if sent successfully
        """
        try:
            context = {
                'user_name': user_name,
                'resume_title': resume_title,
                'analysis_score': analysis_score,
                'recommendations_count': recommendations_count,
                'app_name': settings.APP_NAME,
                'dashboard_url': f"{settings.FRONTEND_URL}/dashboard" if hasattr(settings, 'FRONTEND_URL') else "http://localhost:3000/dashboard"
            }
            
            html_content = f"""
<div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
    <h2>Resume Analysis Complete!</h2>
    <p>Hello {user_name},</p>
    <p>Great news! Your resume analysis for "<strong>{resume_title}</strong>" is now complete.</p>
    
    <div style="background-color: #f8f9fa; padding: 20px; border-radius: 8px; margin: 20px 0;">
        <h3>Analysis Results:</h3>
        <p><strong>Overall Score:</strong> {analysis_score:.1f}/100</p>
        <p><strong>Recommendations:</strong> {recommendations_count} suggestions to improve your resume</p>
    </div>
    
    <p>Visit your dashboard to review the detailed analysis and implement the recommendations.</p>
    <p><a href="{context['dashboard_url']}" style="background-color: #007bff; color: white; padding: 12px 24px; text-decoration: none; border-radius: 4px; display: inline-block;">View Analysis</a></p>
    
    <p>Best regards,<br>The {settings.APP_NAME} Team</p>
</div>
            """
            
            text_content = f"""
Resume Analysis Complete!

Hello {user_name},

Your resume analysis for "{resume_title}" is now complete.

Analysis Results:
- Overall Score: {analysis_score:.1f}/100
- Recommendations: {recommendations_count} suggestions

Visit your dashboard to review the detailed analysis: {context['dashboard_url']}

Best regards,
The {settings.APP_NAME} Team
            """.strip()
            
            return await self.send_email(
                to_email=email,
                subject=f"Resume Analysis Complete - {resume_title}",
                html_content=html_content,
                text_content=text_content
            )
            
        except Exception as e:
            logger.error(f"Failed to send analysis complete email to {email}: {e}")
            return False
    
    async def send_bulk_email(
        self,
        recipients: List[str],
        subject: str,
        html_content: str,
        text_content: Optional[str] = None,
        batch_size: int = 50
    ) -> Dict[str, int]:
        """
        Send email to multiple recipients in batches.
        
        Args:
            recipients: List of email addresses
            subject: Email subject
            html_content: HTML content
            text_content: Plain text content
            batch_size: Number of emails per batch
            
        Returns:
            Dictionary with success and failure counts
        """
        results = {"success": 0, "failed": 0}
        
        # Split recipients into batches
        for i in range(0, len(recipients), batch_size):
            batch = recipients[i:i + batch_size]
            
            # Send emails in batch
            tasks = [
                self.send_email(email, subject, html_content, text_content)
                for email in batch
            ]
            
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for result in batch_results:
                if isinstance(result, Exception):
                    results["failed"] += 1
                elif result:
                    results["success"] += 1
                else:
                    results["failed"] += 1
            
            # Small delay between batches to avoid overwhelming SMTP server
            if i + batch_size < len(recipients):
                await asyncio.sleep(1)
        
        logger.info(f"Bulk email sent: {results['success']} success, {results['failed']} failed")
        return results
    
    def _is_configured(self) -> bool:
        """Check if email service is properly configured."""
        return bool(
            self.smtp_server and
            self.smtp_username and
            self.smtp_password and
            self.from_email
        )
    
    async def _send_smtp_email(
        self,
        msg: MIMEMultipart,
        to_email: str,
        cc: Optional[List[str]] = None,
        bcc: Optional[List[str]] = None
    ) -> None:
        """Send email via SMTP."""
        recipients = [to_email]
        if cc:
            recipients.extend(cc)
        if bcc:
            recipients.extend(bcc)
        
        # Use asyncio to run SMTP in thread pool
        await asyncio.get_event_loop().run_in_executor(
            None, self._send_smtp_sync, msg, recipients
        )
    
    def _send_smtp_sync(self, msg: MIMEMultipart, recipients: List[str]) -> None:
        """Synchronous SMTP send."""
        with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
            if self.use_tls:
                server.starttls()
            
            if self.smtp_username and self.smtp_password:
                server.login(self.smtp_username, self.smtp_password)
            
            server.send_message(msg, to_addrs=recipients)
    
    async def _add_attachment(
        self,
        msg: MIMEMultipart,
        attachment: Dict[str, Any]
    ) -> None:
        """Add attachment to email message."""
        try:
            if 'file_path' in attachment:
                # File attachment
                async with aiofiles.open(attachment['file_path'], 'rb') as f:
                    content = await f.read()
                
                part = MIMEBase('application', 'octet-stream')
                part.set_payload(content)
                encoders.encode_base64(part)
                
                filename = attachment.get('filename', os.path.basename(attachment['file_path']))
                part.add_header(
                    'Content-Disposition',
                    f'attachment; filename= {filename}'
                )
                
                msg.attach(part)
                
            elif 'content' in attachment:
                # Content attachment
                part = MIMEBase('application', 'octet-stream')
                part.set_payload(attachment['content'])
                encoders.encode_base64(part)
                
                filename = attachment.get('filename', 'attachment')
                part.add_header(
                    'Content-Disposition',
                    f'attachment; filename= {filename}'
                )
                
                msg.attach(part)
                
        except Exception as e:
            logger.error(f"Failed to add attachment: {e}")
    
    def _get_verification_html_fallback(self, context: Dict[str, Any]) -> str:
        """Fallback HTML template for email verification."""
        return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Verify Your Email</title>
</head>
<body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
    <div style="text-align: center; margin-bottom: 30px;">
        <h1 style="color: #333;">{context['app_name']}</h1>
    </div>
    
    <h2>Verify Your Email Address</h2>
    <p>Hello {context['user_name']},</p>
    <p>Welcome to {context['app_name']}! Please verify your email address to complete your registration.</p>
    
    <div style="text-align: center; margin: 30px 0;">
        <a href="{context['verification_url']}" 
           style="background-color: #007bff; color: white; padding: 12px 24px; text-decoration: none; border-radius: 4px; display: inline-block;">
            Verify Email Address
        </a>
    </div>
    
    <p>Or copy and paste this link in your browser:</p>
    <p style="word-break: break-all; background-color: #f8f9fa; padding: 10px; border-radius: 4px;">
        {context['verification_url']}
    </p>
    
    <p>Verification code: <code>{context['token']}</code></p>
    
    <hr style="margin: 30px 0;">
    <p style="color: #666; font-size: 14px;">
        If you didn't create this account, please ignore this email.
    </p>
</body>
</html>
        """
    
    def _get_password_reset_html_fallback(self, context: Dict[str, Any]) -> str:
        """Fallback HTML template for password reset."""
        return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Reset Your Password</title>
</head>
<body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
    <div style="text-align: center; margin-bottom: 30px;">
        <h1 style="color: #333;">{context['app_name']}</h1>
    </div>
    
    <h2>Password Reset Request</h2>
    <p>Hello {context['user_name']},</p>
    <p>You requested a password reset for your {context['app_name']} account.</p>
    
    <div style="text-align: center; margin: 30px 0;">
        <a href="{context['reset_url']}" 
           style="background-color: #dc3545; color: white; padding: 12px 24px; text-decoration: none; border-radius: 4px; display: inline-block;">
            Reset Password
        </a>
    </div>
    
    <p>Or copy and paste this link in your browser:</p>
    <p style="word-break: break-all; background-color: #f8f9fa; padding: 10px; border-radius: 4px;">
        {context['reset_url']}
    </p>
    
    <p>Reset code: <code>{context['token']}</code></p>
    
    <div style="background-color: #fff3cd; padding: 15px; border-radius: 4px; margin: 20px 0;">
        <strong>⚠️ Security Notice:</strong> This link will expire in 1 hour for security reasons.
    </div>
    
    <hr style="margin: 30px 0;">
    <p style="color: #666; font-size: 14px;">
        If you didn't request this password reset, please ignore this email or contact support if you're concerned about your account security.
    </p>
</body>
</html>
        """
    
    def _get_welcome_html_fallback(self, context: Dict[str, Any]) -> str:
        """Fallback HTML template for welcome email."""
        return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Welcome to {context['app_name']}</title>
</head>
<body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
    <div style="text-align: center; margin-bottom: 30px;">
        <h1 style="color: #333;">{context['app_name']}</h1>
    </div>
    
    <h2>Welcome aboard! 🎉</h2>
    <p>Hello {context['user_name']},</p>
    <p>Your account has been successfully verified and you're ready to start building amazing resumes!</p>
    
    <div style="background-color: #f8f9fa; padding: 20px; border-radius: 8px; margin: 20px 0;">
        <h3>Get Started:</h3>
        <ul>
            <li>Upload your first resume</li>
            <li>Add job descriptions you're interested in</li>
            <li>Use our AI to optimize your resume for each position</li>
            <li>Export your optimized resume in multiple formats</li>
        </ul>
    </div>
    
    <div style="text-align: center; margin: 30px 0;">
        <a href="{context['dashboard_url']}" 
           style="background-color: #28a745; color: white; padding: 12px 24px; text-decoration: none; border-radius: 4px; display: inline-block;">
            Go to Dashboard
        </a>
    </div>
    
    <p>Need help? Check out our documentation or contact support.</p>
    
    <p>Best regards,<br>The {context['app_name']} Team</p>
</body>
</html>
        """


# Export service
__all__ = ["EmailService"]