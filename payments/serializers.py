from rest_framework import serializers

from .models import Payment


class PaymentSerializer(serializers.ModelSerializer):
    order_reference = serializers.CharField(source='order.reference', read_only=True)

    class Meta:
        model = Payment
        fields = [
            'id', 'order_reference', 'provider', 'amount', 'currency', 'status',
            'provider_reference', 'checkout_url', 'operator', 'created_at',
        ]
