from django.contrib import admin

from .models import Approval, PurchaseOrder, PurchaseRequest, RequestItem


class RequestItemInline(admin.TabularInline):
    model = RequestItem
    extra = 0


@admin.register(PurchaseRequest)
class PurchaseRequestAdmin(admin.ModelAdmin):
    list_display = ("reference", "title", "created_by", "status", "amount_estimated", "vendor_name", "created_at")
    list_filter = ("status", "currency", "created_at")
    search_fields = ("title", "created_by__username")
    inlines = [RequestItemInline]


@admin.register(Approval)
class ApprovalAdmin(admin.ModelAdmin):
    list_display = ("purchase_request", "approver", "level", "decision", "created_at")
    list_filter = ("decision", "level")
    search_fields = ("purchase_request__title", "approver__username")


@admin.register(PurchaseOrder)
class PurchaseOrderAdmin(admin.ModelAdmin):
    list_display = ("po_number", "purchase_request", "vendor_name", "currency", "total_amount")
    search_fields = ("po_number", "vendor_name")
