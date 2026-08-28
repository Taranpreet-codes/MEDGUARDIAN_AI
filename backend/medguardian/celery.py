"""
MedGuardian AI — Celery Application Bootstrap
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
This module initialises the Celery application so it shares Django's full
settings and ORM.  It must be imported by medguardian/__init__.py so Celery
is available before any Django app is ready.
"""
import os
from celery import Celery

# Tell Celery which Django settings module to use
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'medguardian.settings')

app = Celery('medguardian')

# Pull all CELERY_* settings from Django's settings.py
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-discover tasks.py in every INSTALLED_APP
app.autodiscover_tasks()


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    """Simple introspection task — useful during development."""
    print(f'Request: {self.request!r}')
