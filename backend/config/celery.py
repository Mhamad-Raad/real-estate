"""Celery app — template→PDF generation (§6.6) and, later, OCR run off the request path.

Settings live in Django under the CELERY_ namespace so there is one config file, not two.
"""

import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("landalloc")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
