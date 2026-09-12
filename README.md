# chiz-ecommerce
A modern full-stack e-commerce platform built with Django, DRF, React, and PostgreSQL.

## Verifying Celery is working in dev

The dev stack (`docker-compose.dev.yml`) runs two additional services on
top of `backend`: `celery_worker` (executes queued background tasks) and
`celery_beat` (schedules periodic tasks via `django-celery-beat`'s
database-backed scheduler). Both connect to the same Redis instance as
`backend`, on the Celery-dedicated DB index (`REDIS_DB_CELERY`, default
`1` — see `backend/core/settings/base.py`'s Redis DB allocation
comment).

To confirm the whole pipeline (Django → Redis broker → worker process)
is actually working end-to-end, not just that the containers started:

1. Start the stack:
   ```
   docker compose -f docker-compose.dev.yml up --build
   ```
2. Confirm the worker connected and discovered tasks — look for a block
   like this in `celery_worker`'s logs:
   ```
   [tasks]
     . core.celery.debug_task

   [... ] Connected to redis://redis:6379/1
   [... ] celery@<hostname> ready.
   ```
   As of this writing, `core.celery.debug_task` (Celery's own built-in
   task) is the only registered task — no app in this codebase has a
   `tasks.py` module yet. Once one is added, its tasks should appear in
   this same list; if they don't, autodiscovery isn't finding that
   app's `tasks.py`.
3. Confirm `celery_beat` logs show it loaded the database scheduler:
   ```
   . scheduler -> django_celery_beat.schedulers.DatabaseScheduler
   beat: Starting...
   ```
4. Trigger a task on demand and confirm the worker actually executes
   it (this is the real proof — everything above only proves startup):
   ```
   docker compose -f docker-compose.dev.yml exec backend python manage.py shell -c "
   from core.celery import debug_task
   result = debug_task.delay()
   print(result.id)
   "
   ```
   Then check `celery_worker`'s logs for a matching line:
   ```
   Task core.celery.debug_task[<id>] received
   Task core.celery.debug_task[<id>] succeeded in ...
   ```
   Once real project tasks exist, swap `debug_task` for one of those
   (e.g. `from shop.tasks import some_task; some_task.delay()`).
