from django.db import connection
from django.http import JsonResponse

def health(request):
    """
    Basic health endpoint that verifies DB connectivity.
    """

    db_ok = True
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1;")
    except Exception:
        db_ok = False

    return JsonResponse(
        {
            "status": "ok" if db_ok else "degraded",
            "db": db_ok,
        },
        status=200 if db_ok else 503,
    )
