from django.db import models
from django.db.models import F
from rest_framework import serializers, status
from rest_framework.viewsets import ModelViewSet
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes

from nqa_backend.permissions import IsStaffMember

from .models import (
    Category, Product, ProductModel, ProductVariant, ProductAttribute,
    ProductApplication, ProductSpec,
)
from .serializers import CategorySerializer


class LocalizedIn(serializers.Serializer):
    fr = serializers.CharField(allow_blank=True)
    en = serializers.CharField(allow_blank=True)


class AttributeIn(serializers.Serializer):
    label = LocalizedIn()
    value = LocalizedIn()


class VariantIn(serializers.Serializer):
    sku = serializers.CharField(max_length=100)
    name = LocalizedIn()
    stock_status = serializers.ChoiceField(
        choices=[choice for choice, _label in ProductVariant.STOCK_CHOICES],
    )
    price = serializers.DecimalField(max_digits=10, decimal_places=2)
    quantity = serializers.IntegerField(min_value=0, default=0)
    low_stock_threshold = serializers.IntegerField(min_value=0, default=10)
    is_active = serializers.BooleanField(default=True)
    attributes = AttributeIn(many=True, default=[])


class ModelIn(serializers.Serializer):
    id = serializers.CharField(max_length=100)
    name = LocalizedIn()
    description = LocalizedIn()
    variants = VariantIn(many=True, default=[])


class ProductIn(serializers.Serializer):
    id = serializers.SlugField()
    category = serializers.SlugField()
    name = LocalizedIn()
    description = LocalizedIn()
    details = LocalizedIn()
    applications = LocalizedIn(many=True, default=[])
    specs = LocalizedIn(many=True, default=[])
    models = ModelIn(many=True, default=[])


class StaffProductSerializer(serializers.Serializer):
    """Sortie =	payload identique à l'API publique, avec ids éditables."""
    id = serializers.CharField(read_only=True)
    category = serializers.CharField(read_only=True)
    name = serializers.SerializerMethodField()
    description = serializers.SerializerMethodField()
    details = serializers.SerializerMethodField()
    applications = serializers.SerializerMethodField()
    specs = serializers.SerializerMethodField()
    models = serializers.SerializerMethodField()

    def get_name(self, obj):
        return {'fr': obj.name_fr, 'en': obj.name_en}

    def get_description(self, obj):
        return {'fr': obj.description_fr, 'en': obj.description_en}

    def get_details(self, obj):
        return {'fr': obj.details_fr, 'en': obj.details_en}

    def get_applications(self, obj):
        return [{'fr': a.text_fr, 'en': a.text_en} for a in obj.applications.all()]

    def get_specs(self, obj):
        return [{'fr': s.text_fr, 'en': s.text_en} for s in obj.specs.all()]

    def get_models(self, obj):
        return [
            {
                'id': model.id,
                'name': {'fr': model.name_fr, 'en': model.name_en},
                'description': {'fr': model.description_fr, 'en': model.description_en},
                'variants': [
                    {
                        'sku': variant.sku,
                        'name': {'fr': variant.name_fr, 'en': variant.name_en},
                        'stock': variant.stock_status,
                        'price': str(variant.price),
                        'quantity': variant.quantity,
                        'low_stock_threshold': variant.low_stock_threshold,
                        'is_active': variant.is_active,
                        'attributes': [
                            {
                                'label': {'fr': a.label_fr, 'en': a.label_en},
                                'value': {'fr': a.value_fr, 'en': a.value_en},
                            }
                            for a in variant.attributes.all()
                        ],
                    }
                    for variant in model.variants.all()
                ],
            }
            for model in obj.models.all()
        ]


class StaffProductViewSet(ModelViewSet):
    """
    CRUD produits pour le back-office (staff) :
    POST/PATCH acceptent le même format imbriqué que l'import
    (products → models → variants → attributes), upsert par id/sku.
    """
    permission_classes = [IsStaffMember]
    pagination_class = None
    lookup_field = 'id'
    lookup_value_regex = '[\\w\\-]+'
    serializer_class = StaffProductSerializer

    def get_queryset(self):
        return Product.objects.all().prefetch_related(
            'models__variants__attributes', 'applications', 'specs',
        )

    def _upsert(self, payload, instance=None):
        try:
            category = Category.objects.get(slug=payload['category'])
        except Category.DoesNotExist:
            raise serializers.ValidationError({'category': [f"Catégorie inconnue : {payload['category']}"]})

        defaults = {
            'category': category,
            'name_fr': payload['name']['fr'],
            'name_en': payload['name']['en'],
            'description_fr': payload['description']['fr'],
            'description_en': payload['description']['en'],
            'details_fr': payload['details']['fr'],
            'details_en': payload['details']['en'],
        }
        if instance is None:
            instance = Product.objects.create(id=payload['id'], **defaults)
        else:
            for field, value in defaults.items():
                setattr(instance, field, value)
            instance.save()

        instance.applications.all().delete()
        for item in payload.get('applications', ()):
            ProductApplication.objects.create(
                product=instance, text_fr=item['fr'], text_en=item['en'])
        instance.specs.all().delete()
        for item in payload.get('specs', ()):
            ProductSpec.objects.create(
                product=instance, text_fr=item['fr'], text_en=item['en'])

        for model_data in payload.get('models', ()):
            model, _ = ProductModel.objects.update_or_create(
                id=model_data['id'],
                defaults={
                    'product': instance,
                    'name_fr': model_data['name']['fr'],
                    'name_en': model_data['name']['en'],
                    'description_fr': model_data['description']['fr'],
                    'description_en': model_data['description']['en'],
                },
            )
            for variant_data in model_data.get('variants', ()):
                variant, _ = ProductVariant.objects.update_or_create(
                    sku=variant_data['sku'],
                    defaults={
                        'model': model,
                        'name_fr': variant_data['name']['fr'],
                        'name_en': variant_data['name']['en'],
                        'stock_status': variant_data['stock_status'],
                        'price': variant_data['price'],
                        'currency': variant_data.get('currency', 'USD'),
                        'quantity': variant_data['quantity'],
                        'low_stock_threshold': variant_data.get('low_stock_threshold', 10),
                        'is_active': variant_data.get('is_active', True),
                    },
                )
                variant.attributes.all().delete()
                for attribute in variant_data.get('attributes', ()):
                    ProductAttribute.objects.create(
                        variant=variant,
                        label_fr=attribute['label']['fr'],
                        label_en=attribute['label']['en'],
                        value_fr=attribute['value']['fr'],
                        value_en=attribute['value']['en'],
                    )
        return instance

    def create(self, request):
        serializer = ProductIn(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance = self._upsert(serializer.validated_data)
        return Response(
            StaffProductSerializer(instance).data, status=status.HTTP_201_CREATED,
        )

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = ProductIn(data=request.data)
        serializer.is_valid(raise_exception=True)
        self._upsert(serializer.validated_data, instance=instance)
        return Response(StaffProductSerializer(instance).data)

    def destroy(self, request, *args, **kwargs):
        try:
            return super().destroy(request, *args, **kwargs)
        except models.ProtectedError:
            return Response(
                {'detail': 'Produit non supprimé : des commandes ou ventes passées y font référence.'},
                status=400,
            )


class StaffVariantViewSet(ModelViewSet):
    """
    Édition rapide d'une variante depuis le back-office :
    GET/PATCH/DELETE /api/v1/staff/variants/{sku}/
    """    
    permission_classes = [IsStaffMember]
    pagination_class = None
    lookup_field = 'sku'
    lookup_value_regex = '[-A-Za-z0-9\\./]+'

    class VariantAdminSerializer(serializers.ModelSerializer):
        model_id = serializers.CharField(source='model.id', read_only=True)

        class Meta:
            model = ProductVariant
            fields = [
                'sku', 'model_id', 'name_fr', 'name_en', 'stock_status',
                'price', 'currency', 'quantity', 'low_stock_threshold', 'is_active',
            ]
            read_only_fields = ['sku', 'model_id']

    class VariantAdminInputSerializer(serializers.ModelSerializer):
        class Meta:
            model = ProductVariant
            fields = ['stock_status', 'price', 'currency', 'quantity', 'low_stock_threshold', 'is_active']

    queryset = ProductVariant.objects.select_related('model__product')
    http_method_names = ['post', 'get', 'patch', 'delete', 'head', 'options']

    def get_serializer_class(self):
        if self.request.method in ('PATCH',):
            return self.VariantAdminInputSerializer
        return self.VariantAdminSerializer

    def destroy(self, request, *args, **kwargs):
        try:
            return super().destroy(request, *args, **kwargs)
        except models.ProtectedError:
            return Response(
                {'detail': 'Variante non supprimable : des commandes ou ventes y font référence.'},
                status=400,
            )


@api_view(['GET'])
@permission_classes([IsStaffMember])
def low_stock_list(request):
    """GET /api/v1/staff/low-stock/ — variantes dont la quantité ≤ seuil."""
    low = (
        ProductVariant.objects
        .select_related('model__product')
        .filter(quantity__lte=F('low_stock_threshold'), is_active=True)
        .exclude(stock_status='on_request')
        .order_by('quantity')
    )
    return Response([
        {
            'sku': variant.sku,
            'product': variant.model.product.name_fr,
            'model': variant.model.name_fr,
            'name_fr': variant.name_fr,
            'quantity': variant.quantity,
            'low_stock_threshold': variant.low_stock_threshold,
            'stock_status': variant.stock_status,
        }
        for variant in low
    ])
