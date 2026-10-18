"""Vues racines de l'API NQA."""
from django.urls import reverse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response


@api_view(['GET'])
@permission_classes([])
def api_root(request, format=None):
    """Accueil de l'API : liste des points d'entrée principaux."""
    return Response({
        'message': 'API backend New Quin Astra',
        'documentation': 'Voir backend/README.md',
        'endpoints': {
            'categories': request.build_absolute_uri(reverse('category-list')),
            'products': request.build_absolute_uri(reverse('product-list')),
            'orders': request.build_absolute_uri(reverse('order-list')),
            'order_tracking': request.build_absolute_uri('/api/v1/orders/track/'),
            'payment_webhook': request.build_absolute_uri('/api/v1/payments/webhook/'),
            'auth': {
                'register': request.build_absolute_uri('/api/v1/auth/register/'),
                'token': request.build_absolute_uri('/api/v1/auth/token/'),
                'me': request.build_absolute_uri('/api/v1/auth/me/'),
            },
            'admin': request.build_absolute_uri('/admin/'),
        },
    })
