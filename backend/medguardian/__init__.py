# MedGuardian AI
# Expose the Celery application so `celery -A medguardian` works correctly
# and the app is initialised before any Django app accesses it.
from .celery import app as celery_app  # noqa: F401

__all__ = ('celery_app',)
