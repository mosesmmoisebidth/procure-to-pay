from django.db import migrations, models


def populate_reference(apps, schema_editor):
    from procurement_app.models import generate_reference

    PurchaseRequest = apps.get_model("procurement_app", "PurchaseRequest")
    for request in PurchaseRequest.objects.filter(reference__isnull=True):
        request.reference = generate_reference()
        request.save(update_fields=["reference"])


class Migration(migrations.Migration):

    dependencies = [
        ("procurement_app", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="purchaserequest",
            name="reference",
            field=models.CharField(blank=True, editable=False, max_length=32, null=True),
        ),
        migrations.RunPython(populate_reference, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="purchaserequest",
            name="reference",
            field=models.CharField(editable=False, max_length=32, unique=True),
        ),
    ]
