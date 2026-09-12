from celery import shared_task
from django.utils import timezone


@shared_task
def celery_health_check() -> str:
    return f"Celery is healthy as of {timezone.now().isoformat()}"
