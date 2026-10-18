import json
import uuid
from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings
from django.db import models

from orders.models import Order


class Payment(models.Model):
    STATUS_CHOICES = [
        ('initiated', 'Initié'),
        ('pending', 'En attente'),
        ('succeeded', 'Réussi'),
        ('failed', 'Échoué'),
        ('cancelled', 'Annulé'),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(
        Order,
        related_name='payments',
        on_delete=models.CASCADE,
    )
    provider = models.CharField(max_length=30, default='stub')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, default='USD')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='initiated')
    provider_reference = models.CharField(max_length=255, blank=True)
    checkout_url = models.CharField(max_length=500, blank=True)
    operator = models.CharField(max_length=30, blank=True, help_text="airtel / orange / mpsa / carte…")
    metadata = models.JSONField(blank=True, default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.provider} · {self.amount} {self.currency} · {self.status}"

    @staticmethod
    def normalize_amount(value):
        return Decimal(value).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def default_payment_provider():
    provider_name = getattr(settings, 'PAYMENTS_PROVIDER', 'stub')
    if provider_name not in settings.PAYMENT_PROVIDERS:
        return 'stub'
    return provider_name
