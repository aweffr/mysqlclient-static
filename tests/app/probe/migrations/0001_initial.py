from django.db import migrations, models

class Migration(migrations.Migration):
    initial = True
    dependencies = []
    operations = [migrations.CreateModel(name="Record", fields=[
        ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
        ("token", models.CharField(max_length=64, unique=True)),
        ("text", models.TextField()),
        ("amount", models.DecimalField(decimal_places=2, max_digits=12)),
        ("payload", models.JSONField()),
        ("binary", models.BinaryField()),
        ("counter", models.IntegerField(default=0)),
        ("created_at", models.DateTimeField()),
    ])]
