from rest_framework import viewsets
from rest_framework.permissions import AllowAny

from .models import Category, Product
from .serializers import CategorySerializer, ProductSerializer


class CategoryViewSet(viewsets.ReadOnlyModelViewSet):
    """GET /api/v1/categories/ — liste publique des catégories."""
    permission_classes = [AllowAny]
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    pagination_class = None
    lookup_field = 'slug'


class ProductViewSet(viewsets.ReadOnlyModelViewSet):
    """
    GET /api/v1/products/        ?q=<texte> & category=<slug> & stock=<status>
    GET /api/v1/products/{id}/   (idem structure du frontend + price/quantity)
    """
    permission_classes = [AllowAny]
    pagination_class = None
    lookup_field = 'id'
    lookup_value_regex = '[\\w\\-]+'

    def get_queryset(self):
        qs = Product.objects.all().prefetch_related(
            'models__variants__attributes', 'applications', 'specs',
        )
        params = self.request.query_params
        query = params.get('q')
        if query:
            for token in query.split():
                qs = _search(qs, token)
        category = params.get('category')
        if category and category != 'all':
            qs = qs.filter(category__slug=category)
        stock = params.get('stock')
        if stock:
            qs = qs.filter(models__variants__stock_status=stock).distinct()
        return qs

    # Format identique au frontend (models → variants) pour la
    # liste ET le détail : le catalogue du site et le POS s'appuient dessus.
    serializer_class = ProductSerializer


def _search(queryset, token):
    """Recherche texte bilingue sur nom / SKU / attributs."""
    from django.db.models import Q

    return queryset.filter(
        Q(name_fr__icontains=token)
        | Q(name_en__icontains=token)
        | Q(description_fr__icontains=token)
        | Q(description_en__icontains=token)
        | Q(models__variants__sku__icontains=token)
        | Q(models__variants__name_fr__icontains=token)
        | Q(models__variants__name_en__icontains=token)
    ).distinct()
