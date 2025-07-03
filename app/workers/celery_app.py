"""
Celery application configuration for background tasks.
"""

from celery import Celery
from celery.schedules import crontab
from app.config import settings

# Create Celery instance
celery_app = Celery(
    "ai_resume_builder",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.workers.tasks", "app.workers.ai_tasks"]
)

# Configure Celery
celery_app.conf.update(
    # Serialization and Content
    task_serializer=settings.CELERY_TASK_SERIALIZER,
    result_serializer=settings.CELERY_RESULT_SERIALIZER,
    accept_content=settings.CELERY_ACCEPT_CONTENT,

    # Timezone & UTC
    timezone=settings.CELERY_TIMEZONE,
    enable_utc=True,

    # Task Behavior
    task_track_started=settings.CELERY_TASK_TRACK_STARTED,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,

    # Worker Settings
    worker_max_tasks_per_child=1000,
    worker_disable_rate_limits=False,

    # Result Settings
    result_expires=3600,  # 1 hour
    result_backend_transport_options={
        "master_name": "mymaster",
        "retry_on_timeout": True,
    },

    # Task Routing
    task_routes={
        "app.workers.tasks.*": {"queue": "default"},
        "app.workers.ai_tasks.*": {"queue": "ai_processing"},
    },

    # Scheduled Tasks (Celery Beat)
    beat_schedule={
        "cleanup-expired-exports": {
            "task": "app.workers.tasks.cleanup_expired_exports",
            "schedule": crontab(minute=0, hour=2),  # Daily at 2 AM
        },
        "cleanup-old-analyses": {
            "task": "app.workers.tasks.cleanup_old_analyses",
            "schedule": crontab(minute=30, hour=2),  # Daily at 2:30 AM
        },
        "update-resume-scores": {
            "task": "app.workers.tasks.update_resume_scores",
            "schedule": crontab(minute=0, hour='*/6'),  # Every 6 hours
        },
        "send-weekly-digest": {
            "task": "app.workers.tasks.send_weekly_digest",
            "schedule": crontab(minute=0, hour=9, day_of_week=1),  # Monday at 9 AM
        },
        "monitor-system-health": {
            "task": "app.workers.tasks.monitor_system_health",
            "schedule": crontab(minute="*/15"),  # Every 15 minutes
        },
    },
)

# Task-specific annotations
celery_app.conf.task_annotations = {
    "app.workers.ai_tasks.analyze_resume": {
        "rate_limit": "10/m",
        "time_limit": 300,
        "soft_time_limit": 240,
    },
    "app.workers.ai_tasks.optimize_resume": {
        "rate_limit": "5/m",
        "time_limit": 600,
        "soft_time_limit": 540,
    },
    "app.workers.ai_tasks.match_resume_to_job": {
        "rate_limit": "20/m",
        "time_limit": 180,
        "soft_time_limit": 150,
    },
}
