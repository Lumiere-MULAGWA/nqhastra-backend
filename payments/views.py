import json

from django.conf import settings
from django.db import transaction
from django.db.models import F, Value
from django.db.models.functions import Greatest
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status as http_status

from orders.models import Order
from .models import Payment, default_payment_provider
from .serializers import PaymentSerializer

VALID_OPERATORS = ('airtel', 'orange', 'mtn', 'mpsa', 'card')


@api_view(['POST'])
@permission_classes([AllowAny])
def order_pay(request, reference):
    """Démarre le paiement d'une commande (Mobile Money)."""
    order = Order.objects.filter(reference=reference).first()
    if order is None:
        return Response({'detail': "Commande introuvable."}, status=404)
    if order.payment_status == 'paid':
        return Response({'detail': "Cette commande est déjà payée."}, status=400)
    if order.status == 'cancelled':
        return Response({'detail': "Commande annulée : paiement impossible."}, status=400)

    operator = request.data.get('operator', 'card')
    if operator not in VALID_OPERATORS:
        return Response(
            {'detail': f"Opérateur invalide. Choix : {', '.join(VALID_OPERATORS)}."},
            status=400,
        )

    amount = Payment.normalize_amount(order.total_amount)
    if amount <= 0:
        return Response(
            {'detail': "Aucun montant à régler : le commercial doit d'abord établir les prix."},
            status=400,
        )

    provider_name = default_payment_provider()
    provider = settings.PAYMENT_PROVIDERS[provider_name]
    payment = Payment.objects.create(
        order=order,
        provider=provider_name,
        amount=amount,
        currency=getattr(settings, 'PAYMENTS_CURRENCY', 'USD'),
        status='initiated',
        operator=operator,
    )
    provider.initiate(payment, operator=operator)

    order.payment_status = 'paid' if payment.status == 'succeeded' else 'initiated'
    order.save(update_fields=['payment_status'])

    return Response(PaymentSerializer(payment).data, status=201)


@api_view(['POST'])
@permission_classes([AllowAny])
def webhook(request):
    """Webhook du fournisseur : met à jour le paiement puis la commande."""
    provider_name = default_payment_provider()
    provider = settings.PAYMENT_PROVIDERS[provider_name]
    event = provider.handle_event(request.data)
    if isinstance(event, dict) and event.get('signature_valid') is False:
        return Response({'detail': 'Signature webhook invalide.'}, status=400)

    payment = Payment.objects.filter(provider_reference=event.get('reference', '')).first()
    if payment is None:
        return Response({'detail': 'Paiement introuvable.'}, status=404)

    new_status = event.get('status', 'pending')
    if new_status not in ('initiated', 'pending', 'succeeded', 'failed', 'cancelled'):
        new_status = 'pending'
    apply_payment_status(payment, new_status, event.get('metadata'))
    return Response({'status': payment.status, 'order': payment.order.reference})


@api_view(['POST'])
@permission_classes([AllowAny])
def simulate(request, provider_reference):
    """Complète un paiement du fournisseur 'stub' (sandbox de développement)."""
    from .models import default_payment_provider

    if not settings.DEBUG and default_payment_provider() != 'stub':
        return Response({'detail': 'Simulation désactivée hors développement.'}, status=404)
    payment = Payment.objects.filter(provider_reference=provider_reference).first()
    if payment is None:
        return Response({'detail': 'Paiement introuvable.'}, status=404)
    new_status = request.data.get('status', 'succeeded')
    if new_status not in ('succeeded', 'failed'):
        return Response({'detail': "Statut de simulation invalide ('succeeded' ou 'failed')."}, status=400)
    apply_payment_status(payment, new_status, {'simulated': True})
    return Response({'status': payment.status, 'order': payment.order.reference})


def apply_payment_status(payment, new_status, metadata=None):
    payment.metadata = {**(metadata or {}), 'last_event': new_status}
    payment.status = new_status
    payment.save(update_fields=['status', 'metadata'])

    order = payment.order
    if new_status == 'succeeded':
        order.payment_status = 'paid'
        mark_confirmed = order.status in ('pending', 'confirmed')
        if order.status == 'pending':
            order.status = 'confirmed'
        if mark_confirmed:
            order.save(update_fields=['payment_status', 'status'])
        else:
            order.save(update_fields=['payment_status'])
        consume_stock(order)
    elif new_status == 'failed':
        order.payment_status = 'failed'
        order.save(update_fields=['payment_status'])
    elif new_status in ('initiated', 'pending'):
        if not order.payment_status == 'paid':
            order.payment_status = 'initiated'
            order.save(update_fields=['payment_status'])
    elif new_status == 'cancelled':
        if order.payment_status != 'paid':
            order.payment_status = 'none'
            order.save(update_fields=['payment_status'])


def consume_stock(order):
    """Décrémente la quantité en stock à la confirmation effective de la commande."""
    with transaction.atomic():
        for item in order.items.select_related('variant'):
            item.variant.__class__.objects.filter(pk=item.variant_id).update(
                quantity=Greatest(
                    F('quantity') - item.quantity,
                    Value(0),
                ),
            )
