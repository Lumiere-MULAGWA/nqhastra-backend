"""URL racine du backend NQA : /api/v1/ pour l'API, /admin/ pour le backoffice."""
from django.conf import settings
from django.contrib import admin
from django.conf.urls.static import static
from django.http import JsonResponse
from django.urls import include, path

from .views import api_root


def home(request):
    """/ → réponse JSON orientant vers /api/v1/ et /admin/."""
    return JsonResponse({
        'detail': 'Backend New Quin Astra — API Django.',
        'api': request.build_absolute_uri('/api/v1/'),
        'admin': request.build_absolute_uri('/admin/'),
    })


api_v1 = [
    # Page d'accueil de l'API (liste des routes)
    path('', api_root, name='api-root'),
    # Catalogue public + routes staff produits
    path('', include('products.urls')),
    # Ventes POS (staff)
    path('sales/', include('sales.urls')),
    # Commandes + paiements
    path('orders/', include('orders.urls')),
    # Routes staff du back-office (sous /api/v1/staff/)
    path('staff/', include('orders.staff_urls')),
    path('staff/', include('sales.staff_urls')),
    path('staff/', include('accounts.staff_urls')),
    path('', include('payments.urls')),
    # Authentification JWT
    path('auth/', include('accounts.urls')),
]

def health(request):
    return JsonResponse({'status': 'ok'})


urlpatterns = [
    path('admin/', admin.site.urls),
    path('health', health, name='health'),
    path('api/v1/', include(api_v1)),
    # / d'abord : aucune trace de catch-all média pour la racine
    path('', home, name='home'),
]

# Fichiers média (uploadés par l'admin) en développement uniquement.
if settings.DEBUG and settings.MEDIA_ROOT:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
