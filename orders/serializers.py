from rest_framework import serializers

from products.models import ProductVariant
from .models import Order, OrderItem


class OrderItemSerializer(serializers.ModelSerializer):
    sku = serializers.CharField(source='variant.sku', read_only=True)
    product_name = serializers.CharField(source='variant.name_fr', read_only=True)
    product_id = serializers.CharField(source='variant.model.product.id', read_only=True)

    class Meta:
        model = OrderItem
        fields = ['sku', 'product_id', 'product_name', 'quantity', 'price_at_order']
        read_only_fields = fields


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    customer = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = [
            'reference', 'customer_name', 'customer_email', 'customer_company',
            'customer_phone', 'delivery_city', 'notes', 'status', 'payment_status',
            'total_amount', 'created_at', 'updated_at', 'items', 'customer',
        ]
        read_only_fields = ['reference', 'status', 'payment_status', 'total_amount', 'created_at', 'updated_at', 'items']

    def get_customer(self, obj):
        if obj.user and obj.user == self.context['request'].user:
            return {'id': obj.user.id, 'email': obj.user.email}
        return None


class OrderCreateSerializer(serializers.Serializer):
    """Création de commande : client connecté (champs contact préremplissables) ou invité."""
    customer_name = serializers.CharField(max_length=255)
    customer_email = serializers.EmailField()
    customer_company = serializers.CharField(max_length=255)
    customer_phone = serializers.CharField(max_length=50)
    delivery_city = serializers.ChoiceField(choices=Order.CITY_CHOICES)
    notes = serializers.CharField(required=False, allow_blank=True, allow_null=True, default='')
    items = serializers.ListField(
        child=serializers.DictField(),
        allow_empty=False,
    )

    def validate_items(self, value):
        for position, item in enumerate(value, start=1):
            if 'sku' not in item:
                raise serializers.ValidationError(f"Ligne {position} : 'sku' manquant.")
            try:
                qty = int(item.get('quantity'))
            except (TypeError, ValueError):
                raise serializers.ValidationError(
                    f"Ligne {position} ({item['sku']}) : quantité invalide."
                )
            if qty < 1:
                raise serializers.ValidationError(
                    f"Ligne {position} ({item['sku']}) : quantité minimale 1."
                )
        skus = [item['sku'] for item in value]
        if len(set(skus)) != len(skus):
            raise serializers.ValidationError("SKUs dupliqués : fusionnez les quantités par ligne.")
        return value

    def create(self, validated_data):
        items_data = validated_data.pop('items')
        skus = {item['sku'] for item in items_data}
        variants = {variant.sku: variant for variant in ProductVariant.objects.filter(sku__in=skus)}

        missing = [item['sku'] for item in items_data if item['sku'] not in variants]
        if missing:
            raise serializers.ValidationError({
                'items': [f"SKU inconnu : {sku}" for sku in missing],
            })
        inactive = [sku for sku, variant in variants.items() if not variant.is_active]
        if inactive:
            raise serializers.ValidationError({'items': [f"SKU désactivé : {sku}" for sku in inactive]})

        user = self.context['request'].user if self.context['request'].user.is_authenticated else None
        order = Order.objects.create(user=user, **validated_data)
        for item_data in items_data:
            variant = variants[item_data['sku']]
            OrderItem.objects.create(
                order=order,
                variant=variant,
                quantity=int(item_data['quantity']),
                price_at_order=variant.price,
            )
        order.recalculate_total()
        return order
