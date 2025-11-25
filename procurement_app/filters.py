import django_filters

from procurement_app.models import PurchaseRequest


class PurchaseRequestFilter(django_filters.FilterSet):
    created_from = django_filters.DateFilter(field_name="created_at", lookup_expr="gte")
    created_to = django_filters.DateFilter(field_name="created_at", lookup_expr="lte")
    vendor_name = django_filters.CharFilter(field_name="vendor_name", lookup_expr="icontains")
    reference = django_filters.CharFilter(field_name="reference", lookup_expr="icontains")

    class Meta:
        model = PurchaseRequest
        fields = ["status", "vendor_name", "reference", "created_from", "created_to"]
