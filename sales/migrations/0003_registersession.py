import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sales', '0002_currency_and_daily_rate'),
    ]

    operations = [
        migrations.CreateModel(
            name='RegisterSession',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('opened_at', models.DateTimeField(auto_now_add=True)),
                ('closed_at', models.DateTimeField(blank=True, null=True)),
                ('currency', models.CharField(
                    choices=[('USD', 'Dollar américain ($)'), ('CDF', 'Franc congolais (FC)')],
                    default='USD', max_length=3, verbose_name='Devise du fond',
                )),
                ('opening_amount', models.DecimalField(
                    decimal_places=2, default=0, max_digits=12, verbose_name='Fond de caisse',
                )),
                ('closing_amount', models.DecimalField(
                    blank=True, decimal_places=2, max_digits=12, null=True,
                    verbose_name='Montant physiquement compté',
                )),
                ('closing_note', models.TextField(blank=True, default='', verbose_name='Observation clôture')),
                ('status', models.CharField(
                    choices=[('open', 'Ouverte'), ('closed', 'Fermée')], default='open', max_length=20,
                )),
                ('cashier', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='register_sessions',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='Agent en caisse',
                )),
                ('opened_by', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='registers_opened',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('closed_by', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='registers_closed',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'verbose_name': 'Session de caisse',
                'verbose_name_plural': 'Sessions de caisse',
                'ordering': ['-opened_at'],
            },
        ),
        migrations.AddField(
            model_name='sale',
            name='register_session',
            field=models.ForeignKey(
                blank=True, editable=False, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='sales',
                to='sales.registersession',
                verbose_name='Session de caisse',
            ),
        ),
    ]
