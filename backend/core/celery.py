import os

from celery import Celery

# manage.py uses this same default (core.settings.development) — matched
# here for consistency. wsgi.py/asgi.py default to the bare "core.settings"
# package instead, which is empty and non-functional on its own; production
# already depends entirely on the container's DJANGO_SETTINGS_MODULE env var
# being set correctly for the app to run at all, independent of Celery, so
# this setdefault is a safe local-dev fallback, not something that can
# override a correctly-configured production environment.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings.development")

app = Celery("chiz")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f"Request: {self.request!r}")
