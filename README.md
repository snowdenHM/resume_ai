# AI Resume Builder - FastAPI Backend

A complete, production-ready FastAPI backend for an AI-powered resume builder that analyzes existing resumes and job descriptions to create tailored, optimized resumes.

## 🚀 Features

### Core Features
- **User Authentication & Authorization** - JWT-based auth with role management
- **Resume Upload & Parsing** - Support for PDF, DOCX formats
- **AI-Powered Analysis** - Integration with OpenAI/Anthropic for resume optimization
- **Job Description Analysis** - Extract requirements and match skills
- **Multi-format Export** - PDF, DOCX, JSON export capabilities
- **Template System** - Multiple professional resume templates
- **Version Management** - Track and manage multiple resume versions

### Technical Features
- **Async/Await Support** - Full async implementation with PostgreSQL
- **Background Tasks** - Celery integration for AI processing
- **Rate Limiting** - Built-in API rate limiting
- **Comprehensive Logging** - Structured logging with Sentry integration
- **Health Checks** - Service health monitoring
- **Database Migrations** - Alembic for schema management
- **Email Notifications** - SMTP integration for user communications
- **File Security** - Virus scanning and file validation
- **API Documentation** - Auto-generated OpenAPI/Swagger docs

## 🛠 Tech Stack

- **Framework**: FastAPI 0.104+
- **Database**: PostgreSQL with AsyncPG
- **ORM**: SQLAlchemy 2.0 (async)
- **Cache/Queue**: Redis
- **Background Tasks**: Celery
- **Authentication**: JWT with PyJWT
- **AI Integration**: OpenAI GPT-4 / Anthropic Claude
- **File Processing**: PyPDF2, python-docx, ReportLab
- **Email**: SMTP with Jinja2 templates
- **Monitoring**: Prometheus, Sentry
- **Containerization**: Docker & Docker Compose

## 📋 Prerequisites

- Python 3.11+
- PostgreSQL 14+
- Redis 6+
- Docker (optional)
- OpenAI API Key (for AI features)

## 🚀 Quick Start

### 1. Clone and Setup

```bash
# Clone the repository
git clone <repository-url>
cd ai-resume-builder

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Environment Configuration

```bash
# Copy environment template
cp .env.example .env

# Edit .env with your settings
nano .env
```

### 3. Database Setup

```bash
# Start PostgreSQL and Redis (if using Docker)
docker-compose up -d db redis

# Initialize database
python run.py init-db

# Run migrations
python run.py migrate
```

### 4. Run the Application

```bash
# Start the development server
python run.py server

# In separate terminals, start background services
python run.py worker
python run.py scheduler
```

The API will be available at `http://localhost:8000`
- API Documentation: `http://localhost:8000/docs`
- Health Check: `http://localhost:8000/health`

## 🐳 Docker Development

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f api

# Stop services
docker-compose down
```

## 📊 Project Structure

```
ai_resume_builder/
├── app/                          # Main application code
│   ├── api/                      # API routes
│   │   └── v1/                   # API version 1
│   │       ├── auth.py           # Authentication endpoints
│   │       ├── users.py          # User management endpoints
│   │       ├── resumes.py        # Resume CRUD endpoints
│   │       ├── job_descriptions.py # Job description endpoints
│   │       ├── analysis.py       # AI analysis endpoints
│   │       ├── templates.py      # Template endpoints
│   │       └── export.py         # Export endpoints
│   ├── core/                     # Core utilities
│   │   ├── security.py           # Security utilities
│   │   └── utils.py              # Common utilities
│   ├── models/                   # Database models
│   │   ├── user.py               # User models
│   │   ├── resume.py             # Resume models
│   │   ├── job_description.py    # Job description models
│   │   ├── analysis.py           # Analysis models
│   │   └── template.py           # Template models
│   ├── schemas/                  # Pydantic schemas
│   ├── services/                 # Business logic
│   │   ├── auth_service.py       # Authentication service
│   │   ├── user_service.py       # User management service
│   │   ├── resume_service.py     # Resume processing service
│   │   ├── ai_service.py         # AI integration service
│   │   ├── file_service.py       # File handling service
│   │   ├── export_service.py     # Export service
│   │   └── email_service.py      # Email service
│   ├── utils/                    # Utility modules
│   ├── workers/                  # Celery workers
│   ├── config.py                 # Configuration
│   ├── database.py               # Database setup
│   ├── dependencies.py           # FastAPI dependencies
│   ├── exceptions.py             # Custom exceptions
│   └── main.py                   # FastAPI app
├── migrations/                   # Database migrations
├── scripts/                      # Utility scripts
├── static/                       # Static files
├── tests/                        # Test suite
├── docker-compose.yml            # Docker services
├── Dockerfile                    # Container definition
├── requirements.txt              # Dependencies
└── run.py                        # Development CLI
```

## 🔧 Development Commands

```bash
# Development server
python run.py server

# Background worker
python run.py worker

# Task scheduler
python run.py scheduler

# Database operations
python run.py init-db
python run.py migrate
python run.py create-migration "description"

# Code quality
python run.py format        # Format with black & isort
python run.py lint          # Lint with flake8
python run.py test          # Run tests

# Setup
python run.py setup         # Setup dev environment
```

## 🔐 Authentication

The API uses JWT-based authentication with access and refresh tokens:

```bash
# Register user
curl -X POST "http://localhost:8000/api/v1/auth/register" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "SecurePass123!",
    "first_name": "John",
    "last_name": "Doe"
  }'

# Login
curl -X POST "http://localhost:8000/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "SecurePass123!"
  }'

# Use token in requests
curl -X GET "http://localhost:8000/api/v1/auth/me" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

## 🧪 Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov-report=html

# Run specific test file
pytest tests/test_auth.py

# Run with verbose output
pytest -v
```

## 📡 API Endpoints

### Authentication
- `POST /api/v1/auth/register` - Register new user
- `POST /api/v1/auth/login` - Login user
- `POST /api/v1/auth/refresh` - Refresh access token
- `POST /api/v1/auth/logout` - Logout user
- `POST /api/v1/auth/verify-email` - Verify email address
- `POST /api/v1/auth/change-password` - Change password
- `POST /api/v1/auth/forgot-password` - Request password reset
- `POST /api/v1/auth/reset-password` - Reset password
- `GET /api/v1/auth/me` - Get current user
- `GET /api/v1/auth/sessions` - Get user sessions

### Users (Future)
- `GET /api/v1/users/profile` - Get user profile
- `PUT /api/v1/users/profile` - Update user profile
- `GET /api/v1/users/preferences` - Get user preferences
- `PUT /api/v1/users/preferences` - Update user preferences

### Resumes (Future)
- `GET /api/v1/resumes` - List user resumes
- `POST /api/v1/resumes` - Upload new resume
- `GET /api/v1/resumes/{id}` - Get resume details
- `PUT /api/v1/resumes/{id}` - Update resume
- `DELETE /api/v1/resumes/{id}` - Delete resume

### Analysis (Future)
- `POST /api/v1/analysis/analyze-resume` - Analyze resume
- `POST /api/v1/analysis/optimize-resume` - Optimize resume
- `POST /api/v1/analysis/match-job` - Match resume to job
- `GET /api/v1/analysis/{id}` - Get analysis results

## 🔧 Configuration

Key environment variables:

```env
# Database
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/db
REDIS_URL=redis://localhost:6379

# Security
SECRET_KEY=your-secret-key
ACCESS_TOKEN_EXPIRE_MINUTES=30

# AI Services
OPENAI_API_KEY=your-openai-key
ANTHROPIC_API_KEY=your-anthropic-key

# Email
SMTP_HOST=smtp.gmail.com
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
```

## 🚀 Deployment

### Production with Docker

```bash
# Build and deploy
docker-compose -f docker-compose.prod.yml up -d

# Scale services
docker-compose up -d --scale worker=3
```

### Manual Deployment

```bash
# Install production dependencies
pip install -r requirements/production.txt

# Set environment
export ENVIRONMENT=production

# Run with Gunicorn
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker
```

## 📊 Monitoring

- **Health Checks**: `/health` and `/health/detailed`
- **Metrics**: `/metrics` (Prometheus format)
- **Logs**: Structured logging with correlation IDs
- **Error Tracking**: Sentry integration

## 🔒 Security Features

- JWT authentication with secure tokens
- Password strength validation
- Rate limiting (100 requests/minute by default)
- Input validation and sanitization
- SQL injection prevention
- File upload security scanning
- CORS configuration
- Security headers
- Environment-based configuration

## 🎯 Performance Optimizations

- Async database operations
- Connection pooling
- Redis caching
- Background task processing
- Lazy loading of relationships
- Database query optimization
- CDN-ready static file serving

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Development Guidelines

-