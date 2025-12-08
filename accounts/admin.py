from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    """Expose the extended user model inside Django admin."""

    fieldsets = DjangoUserAdmin.fieldsets + (
        (
            "Procurement details",
            {
                "fields": (
                    "role",
                    "department",
                    "full_name",
                )
            },
        ),
    )
    list_display = ("username", "email", "role", "department", "is_active")
    list_filter = ("role", "is_staff", "is_superuser", "is_active")
