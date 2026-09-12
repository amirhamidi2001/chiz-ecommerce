from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from core.health import run_health_checks


class HealthCheckView(APIView):
    """
    GET /api/health/ — reports database and Celery pipeline health.

    The Celery check genuinely exercises the pipeline end-to-end
    (queues a task, blocks briefly for a real worker to complete it)
    rather than just confirming the Celery app object is importable —
    see core/health.py for why that distinction matters.
    """

    permission_classes = [AllowAny]

    def get(self, request):
        result = run_health_checks()
        http_status = (
            status.HTTP_200_OK
            if result["status"] == "healthy"
            else status.HTTP_503_SERVICE_UNAVAILABLE
        )
        return Response(result, status=http_status)
