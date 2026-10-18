from decimal import Decimal
from datetime import date

from django.db import transaction
from django.db.models import F, Value
from django.db.models.functions import Greatest
from rest_framework import serializers

from products.models import ProductVariant
from .models import CURRENCY_CHOICES, DailyRate, RegisterSession, Sale, SaleLine

CENT = Decimal('0.01')


def convert(amount: Decimal, from_currency: str, to_currency: str, rate: Decimal) -> Decimal:
    """Convertit un montant USD ↔ FC selon le taux du jour (1 USD = rate FC)."""
    if from_currency == to_currency:
        return amount
    if to_currency == 'CDF':
        return amount * rate
    return amount / rate


class SaleLineSerializer(serializers.ModelSerializer):
    sku = serializers.CharField(source='sku_snapshot', read_only=True)
    name = serializers.CharField(source='name_snapshot', read_only=True)
    total = serializers.DecimalField(source='line_total', max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = SaleLine
        fields = ['sku', 'name', 'quantity', 'unit_price', 'total', 'currency']
        read_only_fields = fields


class SaleSerializer(serializers.ModelSerializer):
    lines = SaleLineSerializer(many=True, read_only=True)
    cashier_name = serializers.CharField(read_only=True)

    class Meta:
        model = Sale
        fields = [
            'reference', 'cashier_name', 'payment_method', 'status', 'currency', 'rate',
            'customer_name', 'customer_phone', 'total', 'amount_paid',
            'change_due', 'balance_due', 'notes', 'created_at', 'lines',
        ]
        read_only_fields = fields


class RegisterSessionSerializer(serializers.ModelSerializer):
    """Caisse : session + résumé des ventes de la session."""
    cashier_name = serializers.SerializerMethodField()
    opened_by_name = serializers.SerializerMethodField()
    summary = serializers.SerializerMethodField()

    class Meta:
        model = RegisterSession
        fields = [
            'id', 'cashier', 'cashier_name', 'opened_by_name',
            'opened_at', 'closed_at', 'status', 'currency',
            'opening_amount', 'closing_amount', 'closing_note', 'summary',
        ]
        read_only_fields = fields

    def get_cashier_name(self, obj):
        if obj.cashier is None:
            return None
        return obj.cashier.get_full_name() or obj.cashier.username

    def get_opened_by_name(self, obj):
        if obj.opened_by is None:
            return None
        return obj.opened_by.get_full_name() or obj.opened_by.username

    def get_summary(self, obj):
        return obj.summary()


class SaleCreateSerializer(serializers.Serializer):
    """Encaissement POS : stock décrémenté atomiquement à la création."""
    payment_method = serializers.ChoiceField(choices=Sale.PAYMENT_CHOICES)
    items = serializers.ListField(child=serializers.DictField(), allow_empty=False)
    currency = serializers.ChoiceField(choices=CURRENCY_CHOICES, default='USD')
    amount_paid = serializers.DecimalField(
        max_digits=12, decimal_places=2, required=False, default=None,
    )
    customer_name = serializers.CharField(required=False, allow_blank=True, default='')
    customer_phone = serializers.CharField(required=False, allow_blank=True, default='')
    notes = serializers.CharField(required=False, allow_blank=True, default='')

    def validate_items(self, items):
        for position, item in enumerate(items, start=1):
            if 'sku' not in item:
                raise serializers.ValidationError(f"Ligne {position} : 'sku' manquant.")
            try:
                quantity = int(item.get('quantity'))
            except (TypeError, ValueError):
                raise serializers.ValidationError(
                    f"Ligne {position} ({item['sku']}) : quantité invalide."
                )
            if quantity < 1:
                raise serializers.ValidationError(f"Ligne {position} : quantité minimale 1.")
            item['quantity'] = quantity
        skus = [item['sku'] for item in items]
        if len(set(skus)) != len(skus):
            raise serializers.ValidationError("SKUs dupliqués dans la vente.")
        return items

    def validate_customer_name(self, value):
        # Vente anonyme par défaut : champ renseigné seulement pour un crédit.
        return value

    def create(self, validated_data):
        payment_method = validated_data['payment_method']
        sale_currency = validated_data['currency']
        if payment_method != 'credit' and (validated_data.get('customer_name') or validated_data.get('customer_phone')):
            raise serializers.ValidationError(
                "Coordonnées client autorisées uniquement pour une vente à crédit."
            )
        if payment_method == 'credit' and not validated_data.get('customer_name'):
            raise serializers.ValidationError(
                "Une vente à crédit exige le nom du client."
            )

        variants = ProductVariant.objects.in_bulk(
            [item['sku'] for item in validated_data['items']], field_name='sku'
        )
        for position, item in enumerate(validated_data['items'], start=1):
            if item['sku'] not in variants:
                raise serializers.ValidationError(
                    f"Ligne {position} : SKU inconnu {item['sku']}."
                )

        needs_conversion = any(
            variants[item['sku']].currency != sale_currency
            for item in validated_data['items']
        )
        rate = None
        if needs_conversion:
            rate = self.get_today_rate()
            if rate is None:
                raise serializers.ValidationError(
                    "Taux du jour non défini : l'admin doit fixer le taux (1 USD = N FC) "
                    "pour encaisser en devise mélangée."
                )

        with transaction.atomic():
            request_user = self.context['request'].user
            cashier = request_user if request_user.is_authenticated else None
            # Lie la vente à la session de caisse ouverte de l'agent (s'il y en a une).
            open_session = (
                RegisterSession.objects.filter(status='open', cashier=cashier).first()
                if cashier else None
            )
            sale = Sale.objects.create(
                cashier=cashier,
                payment_method=payment_method,
                status='credit' if payment_method == 'credit' else 'paid',
                currency=sale_currency,
                rate=rate if sale_currency != 'USD' or needs_conversion else None,
                customer_name=validated_data.get('customer_name', ''),
                customer_phone=validated_data.get('customer_phone', ''),
                notes=validated_data.get('notes', ''),
                total=Decimal('0.00'),
                register_session=open_session,
            )
            total = Decimal('0.00')
            for item in validated_data['items']:
                variant = variants[item['sku']]
                quantity = item['quantity']
                unit_price = item.get('unit_price')
                if unit_price not in (None, ''):
                    # Prix imposé : considéré dans la devise de la variante.
                    unit_price = convert(
                        Decimal(str(unit_price)), variant.currency, sale_currency, rate
                    ).quantize(CENT)
                else:
                    unit_price = convert(variant.price, variant.currency, sale_currency, rate).quantize(CENT)
                line = SaleLine(
                    sale=sale, variant=variant, quantity=quantity, unit_price=unit_price,
                    currency=sale_currency,
                )
                line.save()  # calcule snapshot + line_total
                total += line.line_total
                ProductVariant.objects.filter(pk=variant.pk).update(
                    quantity=Greatest(F('quantity') - quantity, Value(0)),
                )
            sale.total = total.quantize(CENT)
            if payment_method == 'cash' and validated_data.get('amount_paid') is not None:
                received = Decimal(str(validated_data['amount_paid']))
                sale.amount_paid = received
                sale.change_due = max(Decimal('0.00'), received - sale.total)
            elif payment_method == 'credit':
                sale.amount_paid = Decimal(str(validated_data.get('amount_paid') or '0.00'))
            else:
                sale.amount_paid = sale.total
            sale.save(update_fields=['total', 'amount_paid', 'change_due'])
        return sale

    def get_today_rate(self):
        today = date.today()
        rate = DailyRate.objects.filter(date=today).first()
        return rate.usd_to_cdf if rate else None
