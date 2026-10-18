import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sales', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='DailyRate',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date', models.DateField(unique=True, verbose_name='date')),
                ('usd_to_cdf', models.DecimalField(decimal_places=4, max_digits=12, verbose_name='1 USD en FC')),
                ('created_by', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='daily_rates',
                    to='accounts.user',
                )),
            ],
            options={
                'verbose_name': 'Taux du jour',
                'verbose_name_plural': 'Taux journaliers',
                'ordering': ['-date'],
            },
        ),
        migrations.AddField(
            model_name='sale',
            name='currency',
            field=models.CharField(
                choices=[('USD', 'Dollar américain ($)'), ('CDF', 'Franc congolais (FC)')],
                default='USD',
                max_length=3,
                verbose_name='Devise de la vente',
            ),
        ),
        migrations.AddField(
            model_name='sale',
            name='rate',
            field=models.DecimalField(
                blank=True, decimal_places=4, editable=False, max_digits=12, null=True,
                verbose_name='Taux utilisé (1 USD = N FC)',
            ),
        ),
        migrations.AddField(
            model_name='saleline',
            name='currency',
            field=models.CharField(
                choices=[('USD', 'Dollar américain ($)'), ('CDF', 'Franc congolais (FC)')],
                default='USD',
                max_length=3,
            ),
        ),
        migrations.AlterField(
            model_name='saleline',
            name='unit_price',
            field=models.DecimalField(decimal_places=2, max_digits=12),
        ),
    ]
