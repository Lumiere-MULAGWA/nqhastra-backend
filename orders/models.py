from django.conf import settings
from django.db import models
from django.utils.crypto import get_random_string

from products.models import ProductVariant


class Order(models.Model):
    CITY_CHOICES = [
        ('lubumbashi', 'Siège Lubumbashi'),
        ('dar', 'Dar es Salaam'),
        ('other', 'Autre site'),
    ]
    STATUS_CHOICES = [
        ('pending', 'En attente'),
        ('confirmed', 'Confirmée'),
        ('preparing', 'En préparation'),
        ('shipped', 'Expédiée'),
        ('delivered', 'Livrée'),
        ('cancelled', 'Annulée'),
    ]
    PAYMENT_STATUS_CHOICES = [
        ('none', 'Non réglée'),
        ('initiated', 'Paiement initié'),
        ('pending', 'Paiement en attente'),
        ('paid', 'Payée'),
        ('failed', 'Paiement échoué'),
    ]
    reference = models.CharField(max_length=50, unique=True, blank=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name='orders',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Compte client (optionnel : commande invité autorisée)",
    )
    customer_name = models.CharField(max_length=255)
    customer_email = models.EmailField()
    customer_company = models.CharField(max_length=255)
    customer_phone = models.CharField(max_length=50)
    delivery_city = models.CharField(max_length=20, choices=CITY_CHOICES)
    notes = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='none')
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.reference

    def save(self, *args, **kwargs):
        if not self.reference:
            self.reference = generate_reference()
        super().save(*args, **kwargs)

    def recalculate_total(self):
        total = sum(
            (item.quantity * item.price_at_order for item in self.items.all()),
            start=0,
        )
        self.total_amount = total
        self.save(update_fields=['total_amount'])

    @property
    def can_be_cancelled(self):
        return self.status in ('pending', 'confirmed')


def generate_reference():
    """Référence unique NQA-AAAAMMJJ-XXXX (tirage aléatoire avec vérification de collision)."""
    import random
    from datetime import date

    stamp = date.today().strftime('%Y%m%d')
    for _ in range(20):
        candidate = f"NQA-{stamp}-{random.randint(1000, 9999)}"
        if not Order.objects.filter(reference=candidate).exists():
            return candidate
    # Secours très improbable : suffixe aléatoire plus long.
    return f"NQA-{stamp}-{get_random_string(6, '0123456789')}"


class OrderItem(models.Model):
    order = models.ForeignKey(Order, related_name='items', on_delete=models.CASCADE)
    variant = models.ForeignKey(ProductVariant, on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField()
    price_at_order = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.quantity} x {self.variant.sku}"
