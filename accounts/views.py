from rest_framework import generics, permissions, views
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView

from .models import BusinessProfile
from .serializers import ProfileSerializer, RegisterSerializer, UserSerializer


class RegisterView(generics.CreateAPIView):
    """Création d'un compte client avec son profil d'entreprise."""
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(UserSerializer(user).data, status=201)


class LoginView(TokenObtainPairView):
    """Connexion JWT (/auth/login/ ou /auth/token/) : access + refresh + profil."""

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        from django.contrib.auth import get_user_model
        User = get_user_model()
        identifier = request.data.get(User.USERNAME_FIELD)
        user = User.objects.filter(email__iexact=identifier).first()
        if user:
            profile = BusinessProfile.objects.filter(user=user).first()
            response.data['user'] = {
                'id': user.id,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'company': profile.company if profile else '',
            }
        return response


class MeView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response(UserSerializer(request.user).data)

    def patch(self, request):
        serializer = ProfileSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)
