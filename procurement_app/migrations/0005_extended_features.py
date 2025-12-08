import uuid
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0002_alter_user_role"),
        ("procurement_app", "0004_alter_purchaserequest_reference"),
    ]

    operations = [
        migrations.AddField(
            model_name="purchaserequest",
            name="risk_level",
            field=models.CharField(
                choices=[("low", "Low"), ("medium", "Medium"), ("high", "High")],
                default="low",
                max_length=8,
            ),
        ),
        migrations.AddField(
            model_name="purchaserequest",
            name="risk_reasons",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.CreateModel(
            name="SavedRequestView",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(max_length=100)),
                ("filters", models.JSONField(blank=True, default=dict)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=models.deletion.CASCADE,
                        related_name="saved_request_views",
                        to="accounts.user",
                    ),
                ),
            ],
            options={
                "ordering": ("name",),
                "unique_together": {("user", "name")},
            },
        ),
        migrations.CreateModel(
            name="RequestComment",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("body", models.TextField()),
                (
                    "author",
                    models.ForeignKey(
                        on_delete=models.deletion.CASCADE,
                        related_name="request_comments",
                        to="accounts.user",
                    ),
                ),
                (
                    "purchase_request",
                    models.ForeignKey(
                        on_delete=models.deletion.CASCADE,
                        related_name="comments",
                        to="procurement_app.purchaserequest",
                    ),
                ),
            ],
            options={
                "ordering": ("created_at",),
            },
        ),
        migrations.CreateModel(
            name="RequestCommentReceipt",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("read_at", models.DateTimeField(auto_now_add=True)),
                (
                    "comment",
                    models.ForeignKey(
                        on_delete=models.deletion.CASCADE, related_name="receipts", to="procurement_app.requestcomment"
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=models.deletion.CASCADE, related_name="comment_receipts", to="accounts.user"
                    ),
                ),
            ],
            options={
                "unique_together": {("comment", "user")},
            },
        ),
        migrations.CreateModel(
            name="FinanceDecision",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "decision",
                    models.CharField(
                        choices=[
                            ("matched", "Matched"),
                            ("accepted_with_note", "Accepted with note"),
                            ("flagged", "Flagged"),
                        ],
                        max_length=32,
                    ),
                ),
                ("note", models.TextField(blank=True)),
                (
                    "decided_by",
                    models.ForeignKey(
                        on_delete=models.deletion.CASCADE,
                        related_name="finance_decisions",
                        to="accounts.user",
                    ),
                ),
                (
                    "purchase_request",
                    models.OneToOneField(
                        on_delete=models.deletion.CASCADE,
                        related_name="finance_decision",
                        to="procurement_app.purchaserequest",
                    ),
                ),
            ],
        ),
    ]
