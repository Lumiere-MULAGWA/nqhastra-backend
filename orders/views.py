from django.db.models import Q
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from .models import Order
from .serializers import OrderCreateSerializer, OrderSerializer


class OrderViewSet(viewsets.ReadOnlyModelViewSet):
    """
    - POST /api/v1/orders/          : créer une commande (invité ou connecté)
    - GET  /api/v1/orders/          : mes commandes (client) / toutes (staff)
    - GET  /api/v1/orders/{ref}/    : détail (staff ou propriétaire)
    - POST /api/v1/orders/{ref}/cancel/ : annulation (staff ou propriétaire, avant expédition)
    """
    permission_classes = [AllowAny]
    lookup_field = 'reference'
    lookup_value_regex = '[0-9A-Za-z\\-]+'

    def get_serializer_class(self):
        if self.request.method in ('POST', 'PUT', 'PATCH'):
            return OrderCreateSerializer
        return OrderSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        order = serializer.save()
        return Response(OrderSerializer(order, context=self.get_serializer_context()).data, status=201)

    def get_queryset(self):
        user = self.request.user
        if user.is_authenticated and user.is_staff_member():
            qs = Order.objects.all()
            requested_status = self.request.query_params.get('status')
            if requested_status:
                qs = qs.filter(status=requested_status)
            return qs
        if user.is_authenticated:
            return Order.objects.filter(user=user)
        return Order.objects.none()

    def retrieve(self, request, *args, **kwargs):
        order = self.lookup_order()
        if order is None:
            return Response({'detail': 'Commande introuvable.'}, status=404)
        self.check_object_permissions(request, order)
        return Response(OrderSerializer(order, context=self.get_serializer_context()).data)

    def lookup_order(self):
        user = self.request.user
        reference = self.kwargs['reference']
        qs = Order.objects.filter(reference=reference)
        if not (user.is_authenticated and user.is_staff_member()):
            if user.is_authenticated:
                return qs.filter(Q(user=user) | Q(customer_email__iexact=user.email)).first()
            return None
        return qs.first()

    @action(
        detail=True,
        methods=['post'],
        permission_classes=[IsAuthenticated],
        url_path='cancel',
    )
    def cancel(self, request, reference=None):
        order = self.lookup_order()
        if order is None:
            return Response({'detail': 'Commande introuvable.'}, status=404)
        user = request.user
        if not (user.is_staff_member() or order.user == user or order.customer_email.lower() == user.email.lower()):
            return Response(
                {'detail': 'Non autorisé : vous ne pouvez annuler que vos commandes.'},
                status=403,
            )
        if not order.can_be_cancelled:
            return Response(
                {'detail': f"Impossible d'annuler une commande « {order.get_status_display()} »."},
                status=400,
            )
        order.status = 'cancelled'
        order.save(update_fields=['status', 'updated_at'])
        return Response({'status': order.status})

    @action(
        detail=False,
        methods=['post'],
        url_path='track',
    )
    def track(self, request, reference=None):
        """Suivi public par référence + e-mail (sans compte)."""
        reference = request.data.get('reference', '')
        email = request.data.get('email', '')
        if not reference or not email:
            return Response(
                {'detail': 'Référence et e-mail requis.'},
                status=400,
            )
        order = Order.objects.filter(
            reference__iexact=reference.strip(),
            customer_email__iexact=email.strip(),
        ).first()
        if order is None:
            return Response({'detail': 'Aucune commande ne correspond.'}, status=404)
        return Response(OrderSerializer(order, context=self.get_serializer_context()).data)
