from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import FinanceRequestViewSet, PurchaseRequestViewSet, home

router = DefaultRouter()
router.register(r"requests", PurchaseRequestViewSet, basename="requests")
router.register(r"finance/requests", FinanceRequestViewSet, basename="finance-requests")

urlpatterns = [
    path("", home, name="home"),
    path("api/", include(router.urls)),
]
