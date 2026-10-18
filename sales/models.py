from django.conf import settings
from django.db import models
from django.db.models import Sum
from django.utils import timezone
from django.utils.crypto import get_random_string

CURRENCY_CHOICES = [
    ('USD', 'Dollar américain ($)'),
    ('CDF', 'Franc congolais (FC)'),
]


class DailyRate(models.Model):
    """Taux de change journalier (1 USD = N FC), fixé par l'admin."""
    date = models.DateField(unique=True)
    usd_to_cdf = models.DecimalField(
        '1 USD en FC', max_digits=12, decimal_places=4,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name='daily_rates',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ['-date']
        verbose_name = 'Taux du jour'
        verbose_name_plural = 'Taux journaliers'

    def __str__(self):
        return f"{self.date} : 1 USD = {self.usd_to_cdf} FC"


class RegisterSession(models.Model):
    """Session de caisse : l'admin ouvre la caisse pour un agent avec un
    fond de caisse ; on la referme avec le compte physique du tiroir."""
    STATUS_CHOICES = [
        ('open', 'Ouverte'),
        ('closed', 'Fermée'),
    ]
    cashier = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name='register_sessions',
        verbose_name='Agent en caisse',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        help_text="La personne qui encaisse (possession du tiroir).",
    )
    opened_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name='registers_opened',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    opened_at = models.DateTimeField(auto_now_add=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    closed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name='registers_closed',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    currency = models.CharField('Devise du fond', max_length=3, choices=CURRENCY_CHOICES, default='USD')
    opening_amount = models.DecimalField('Fond de caisse', max_digits=12, decimal_places=2, default=0)
    closing_amount = models.DecimalField(
        'Montant physiquement compté', max_digits=12, decimal_places=2, null=True, blank=True,
    )
    closing_note = models.TextField('Observation clôture', blank=True, default='')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')

    class Meta:
        ordering = ['-opened_at']
        verbose_name = 'Session de caisse'
        verbose_name_plural = 'Sessions de caisse'

    def __str__(self):
        agent = self.cashier.get_username() if self.cashier else 'anonyme'
        return f"Caisse {agent} · {self.status} ({self.get_currency_display()})"

    def summary(self):
        """Totaux de la session par mode de paiement et devise."""
        base = self.sales.all()
        totals = {
            method: [
                {
                    'currency': currency,
                    'amount': str(
                        base.filter(payment_method=method, currency=currency).aggregate(
                            Sum('total')
                        )['total__sum'] or 0
                    ),
                }
                for currency, _ in CURRENCY_CHOICES
            ]
            for method, _ in Sale.PAYMENT_CHOICES
        }
        return {
            'sales_count': base.count(),
            'totals_by_method': totals,
            'cash_expected': str(
                base.filter(payment_method='cash', currency=self.currency).aggregate(
                    Sum('total')
                )['total__sum'] or 0
            ),
        }


class Sale(models.Model):
    """Vente réalisée au comptoir (POS), distincte des commandes à distance."""
    PAYMENT_CHOICES = [
        ('cash', 'Espèces'),
        ('mobile', 'Mobile Money'),
        ('credit', 'Crédit / à terme'),
    ]
    STATUS_CHOICES = [
        ('paid', 'Payée'),
        ('credit', 'À recouvrer'),
    ]
    reference = models.CharField(max_length=50, unique=True, blank=True)
    cashier = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name='sales',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    payment_method = models.CharField(max_length=20, choices=PAYMENT_CHOICES, default='cash')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='paid')
    currency = models.CharField('Devise de la vente', max_length=3, choices=CURRENCY_CHOICES, default='USD')
    rate = models.DecimalField(
        'Taux utilisé (1 USD = N FC)', max_digits=12, decimal_places=4, null=True, blank=True, editable=False,
    )
    register_session = models.ForeignKey(
        'sales.RegisterSession',
        related_name='sales',
        verbose_name='Session de caisse',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        editable=False,
    )
    customer_name = models.CharField(
        'Client (à terme)',
        max_length=255,
        blank=True,
        help_text="Seulement pour une vente à crédit",
    )
    customer_phone = models.CharField('Téléphone (à terme)', max_length=50, blank=True)
    total = models.DecimalField(max_digits=12, decimal_places=2, editable=False)
    amount_paid = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    change_due = models.DecimalField(max_digits=12, decimal_places=2, default=0.00, editable=False)
    notes = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Vente POS'
        verbose_name_plural = 'Ventes POS'

    def __str__(self):
        return f"{self.reference} · {self.payment_method} · {self.status}"

    def save(self, *args, **kwargs):
        if not self.reference:
            self.reference = self.generate_reference()
        super().save(*args, **kwargs)

    @staticmethod
    def generate_reference():
        from datetime import date

        stamp = date.today().strftime('%Y%m%d')
        for _ in range(20):
            candidate = f"VTE-{stamp}-{get_random_string(4, '0123456789')}"
            if not Sale.objects.filter(reference=candidate).exists():
                return candidate
        return f"VTE-{stamp}-{get_random_string(6, '0123456789')}"

    @property
    def balance_due(self):
        if self.status == 'paid':
            return 0
        return self.total - self.amount_paid


class SaleLine(models.Model):
    sale = models.ForeignKey(Sale, related_name='lines', on_delete=models.CASCADE)
    variant = models.ForeignKey(
        'products.ProductVariant',
        related_name='sale_lines',
        on_delete=models.PROTECT,
    )
    sku_snapshot = models.CharField(max_length=100, editable=False)
    name_snapshot = models.CharField(max_length=255, editable=False)
    quantity = models.PositiveIntegerField()
    currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES, default='USD')
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    line_total = models.DecimalField(max_digits=12, decimal_places=2, editable=False)

    def save(self, *args, **kwargs):
        from decimal import Decimal

        if not self.sku_snapshot:
            self.sku_snapshot = self.variant.sku
        if not self.name_snapshot:
            self.name_snapshot = self.variant.name_fr
        self.line_total = Decimal(self.quantity) * self.unit_price
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.quantity} × {self.sku_snapshot}"
