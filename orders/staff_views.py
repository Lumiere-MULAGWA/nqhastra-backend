"""Routes staff du back-office pour les commandes web."""
from rest_framework import status as http_status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from nqa_backend.permissions import IsStaffMember

from .models import Order
from .serializers import OrderSerializer


@api_view(['PATCH'])
@permission_classes([IsStaffMember])
def order_status(request, reference):
    """PATCH /api/v1/staff/orders/{reference}/ {"status": "confirmed" …}"""
    order = Order.objects.filter(reference=reference).first()
    if order is None:
        return Response({'detail': 'Commande introuvable.'}, status=404)
    new_status = request.data.get('status')
    if new_status not in dict(Order.STATUS_CHOICES):
        choices = ', '.join(key for key, _ in Order.STATUS_CHOICES)
        return Response(
            {'detail': f"Statut invalide. Choix autorisés : {choices}."},
            status=400,
        )
    order.status = new_status
    order.save(update_fields=['status', 'updated_at'])
    return Response(OrderSerializer(order, context={'request': request}).data)
