from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("identity", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="refreshtoken",
            name="ip_address",
            field=models.CharField(blank=True, max_length=45, null=True),
        ),
        migrations.AddField(
            model_name="refreshtoken",
            name="session_started_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="refreshtoken",
            name="user_agent",
            field=models.CharField(blank=True, default="", max_length=200),
        ),
        migrations.AddIndex(
            model_name="refreshtoken",
            index=models.Index(fields=["expires_at"], name="ix_refresh_tokens_expires"),
        ),
    ]
