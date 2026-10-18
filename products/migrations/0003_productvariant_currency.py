import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0002_productvariant_is_active_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='productvariant',
            name='currency',
            field=models.CharField(
                choices=[('USD', 'Dollar américain ($)'), ('CDF', 'Franc congolais (FC)')],
                default='USD',
                max_length=3,
                verbose_name='Devise du prix',
            ),
        ),
    ]
