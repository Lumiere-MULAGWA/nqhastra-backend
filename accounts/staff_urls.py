"""Routes staff des comptes (sous /api/v1/staff/)."""
from django.contrib.auth import get_user_model
from django.urls import path
from rest_framework import serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from nqa_backend.permissions import IsStoreAdmin


class StaffMemberSerializer(serializers.Serializer):
    """Minimale : pour choisir l'agent à qui ouvrir une caisse."""
    id = serializers.IntegerField(read_only=True)
    email = serializers.EmailField(read_only=True)
    full_name = serializers.CharField(read_only=True)
    role = serializers.CharField(read_only=True)


@api_view(['GET'])
@permission_classes([IsStoreAdmin])
def staff_members(request):
    """GET /api/v1/staff/users/ : agents du personnel (Admin uniquement)."""
    user = get_user_model()
    members = [
        {
            'id': u.id,
            'email': u.email,
            'full_name': u.get_full_name() or u.username,
            'role': 'admin' if u.is_store_admin() else 'commercial',
        }
        for u in user.objects.filter(is_active=True).order_by('first_name', 'last_name')
    ]
    return Response(StaffMemberSerializer(members, many=True).data)


urlpatterns = [
    path('users/', staff_members, name='staff-users'),
]
