import uuid

from django.contrib.auth.models import AbstractUser
from django.db import models

class User(AbstractUser):
    """Custom user that carries a role for the procurement workflow."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    class Roles(models.TextChoices):
        SUPER_ADMIN = "super_admin", "Super Admin"
        STAFF = "staff", "Staff"
        APPROVER_L1 = "approver_lvl1", "Approver Level 1"
        APPROVER_L2 = "approver_lvl2", "Approver Level 2"
        FINANCE = "finance", "Finance"

    role = models.CharField(
        max_length=32,
        choices=Roles.choices,
        default=Roles.STAFF,
        help_text="Determines the default permissions the user has in the system.",
    )
    department = models.CharField(
        max_length=128,
        blank=True,
        help_text="Optional department or business unit for reporting.",
    )
    full_name = models.CharField(
        max_length=255,
        blank=True,
        help_text="Display name shown across the UI.",
    )

    def __str__(self) -> str:
        return self.full_name or self.username

    def save(self, *args, **kwargs):
        if self.is_superuser:
            self.role = self.Roles.SUPER_ADMIN
        super().save(*args, **kwargs)
