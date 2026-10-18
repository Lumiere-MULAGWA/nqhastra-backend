from rest_framework import serializers

from .models import (
    Category,
    Product,
    ProductModel,
    ProductVariant,
    ProductAttribute,
    ProductApplication,
    ProductSpec,
)


class LocalizedSerializer(serializers.Serializer):
    """Représente un champ bilingue en {fr: ..., en: ...} comme le frontend."""
    fr = serializers.CharField(allow_blank=True, required=False)
    en = serializers.CharField(allow_blank=True, required=False)


class CategorySerializer(serializers.ModelSerializer):
    label = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ['slug', 'label']

    def get_label(self, instance):
        return {'fr': instance.name_fr, 'en': instance.name_en}


class ProductAttributeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductAttribute
        fields: list = []

    def to_representation(self, instance):
        return {
            'label': {'fr': instance.label_fr, 'en': instance.label_en},
            'value': {'fr': instance.value_fr, 'en': instance.value_en},
        }


class ProductVariantSerializer(serializers.ModelSerializer):
    """Format aligné sur le type `ProductVariant` du frontend :
    sku, name, attributes, stock — plus les champs backend (price, quantity)."""
    name = serializers.SerializerMethodField()
    stock = serializers.CharField(source='stock_status')
    attributes = ProductAttributeSerializer(many=True, read_only=True)

    class Meta:
        model = ProductVariant
        fields = ['sku', 'name', 'stock', 'price', 'currency', 'quantity', 'attributes']

    def get_name(self, instance):
        return {'fr': instance.name_fr, 'en': instance.name_en}


class ProductModelSerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()
    description = serializers.SerializerMethodField()
    variants = ProductVariantSerializer(many=True, read_only=True)

    class Meta:
        model = ProductModel
        fields = ['id', 'name', 'description', 'variants']

    def get_name(self, instance):
        return {'fr': instance.name_fr, 'en': instance.name_en}

    def get_description(self, instance):
        return {'fr': instance.description_fr, 'en': instance.description_en}


class ProductApplicationSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductApplication
        fields = []

    def to_representation(self, instance):
        return {'fr': instance.text_fr, 'en': instance.text_en}


class ProductSpecSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductSpec
        fields = []

    def to_representation(self, instance):
        return {'fr': instance.text_fr, 'en': instance.text_en}


class ProductListSerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()
    description = serializers.SerializerMethodField()
    category = serializers.CharField(source='category.slug')

    class Meta:
        model = Product
        fields = ['id', 'category', 'name', 'description', 'image']

    def get_name(self, instance):
        return {'fr': instance.name_fr, 'en': instance.name_en}

    def get_description(self, instance):
        return {'fr': instance.description_fr, 'en': instance.description_en}


class ProductSerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()
    description = serializers.SerializerMethodField()
    details = serializers.SerializerMethodField()
    applications = ProductApplicationSerializer(many=True, read_only=True)
    specs = ProductSpecSerializer(many=True, read_only=True)
    models = ProductModelSerializer(many=True, read_only=True)
    category = serializers.CharField(source='category.slug')

    class Meta:
        model = Product
        fields = [
            'id', 'category', 'name', 'description', 'details',
            'image', 'applications', 'specs', 'models',
        ]

    def get_name(self, instance):
        return {'fr': instance.name_fr, 'en': instance.name_en}

    def get_description(self, instance):
        return {'fr': instance.description_fr, 'en': instance.description_en}

    def get_details(self, instance):
        return {'fr': instance.details_fr, 'en': instance.details_en}
