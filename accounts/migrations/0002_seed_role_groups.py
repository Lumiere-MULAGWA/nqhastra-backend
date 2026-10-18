"""Seed des groupes de rôles : Admin (accès total) et Commercial (API staff)."""
from django.contrib.auth.models import Group
from django.db import migrations


ROLE_GROUPS = ('Admin', 'Commercial')


def seed_groups(apps, schema_editor):
    for name in ROLE_GROUPS:
        Group.objects.get_or_create(name=name)


def remove_groups(apps, schema_editor):
    Group.objects.filter(name__in=ROLE_GROUPS).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(seed_groups, remove_groups),
    ]
