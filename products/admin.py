from django.contrib import admin
from .models import Category, Product, ProductModel, ProductVariant, ProductAttribute, ProductApplication, ProductSpec

class ProductAttributeInline(admin.TabularInline):
    model = ProductAttribute
    extra = 1

class ProductVariantInline(admin.StackedInline):
    model = ProductVariant
    extra = 1
    show_change_link = True

class ProductModelInline(admin.StackedInline):
    model = ProductModel
    extra = 1
    show_change_link = True

class ProductApplicationInline(admin.TabularInline):
    model = ProductApplication
    extra = 1

class ProductSpecInline(admin.TabularInline):
    model = ProductSpec
    extra = 1

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('slug', 'name_fr', 'name_en')

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('id', 'category', 'name_fr', 'name_en')
    list_filter = ('category',)
    search_fields = ('id', 'name_fr', 'name_en')
    inlines = [ProductApplicationInline, ProductSpecInline, ProductModelInline]

@admin.register(ProductModel)
class ProductModelAdmin(admin.ModelAdmin):
    list_display = ('name_fr', 'product')
    list_filter = ('product',)
    inlines = [ProductVariantInline]

@admin.register(ProductVariant)
class ProductVariantAdmin(admin.ModelAdmin):
    list_display = (
        'sku', 'name_fr', 'model', 'stock_status', 'price',
        'quantity', 'low_stock_threshold',
    )
    list_filter = ('stock_status', 'model__product__category')
    search_fields = ('sku', 'name_fr', 'name_en')
    list_editable = ('price', 'quantity', 'low_stock_threshold', 'stock_status')
    actions = ('show_low_stock',)

    @admin.action(description='Filtrer les variantes en stock bas')
    def show_low_stock(self, request, queryset):
        lows = [str(variant) for variant in queryset
                if variant.quantity <= variant.low_stock_threshold and variant.stock_status != 'on_request']
        if lows:
            self.message_user(request, 'Stock bas : ' + ', '.join(lows))
        else:
            self.message_user(request, 'Aucune variante sélectionnée en stock bas.')
