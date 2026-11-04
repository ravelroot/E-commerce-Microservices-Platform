from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0002_totais_bigint_e_indice"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="idempotency_key",
            field=models.CharField(blank=True, max_length=64, null=True),
        ),
        migrations.AddConstraint(
            model_name="order",
            constraint=models.UniqueConstraint(
                fields=("customer_id", "idempotency_key"),
                name="uq_orders_customer_idempotency",
            ),
        ),
    ]
