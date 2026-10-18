from django.contrib import admin

from orders import models as order_models
from payments.models import Payment

from products.models import ProductVariant

STOCK_BAS = 'Quantité ≤ seuil'

class OrderItemInline(admin.TabularInline):
    model = order_models.OrderItem
    extra = 0
    fields = ('variant', 'quantity', 'price_at_order')
    readonly_fields = ('price_at_order',)


class PaymentInline(admin.TabularInline):
    model = Payment
    extra = 0
    fields = ('provider', 'amount', 'currency', 'status', 'provider_reference', 'operator', 'checkout_url')
    readonly_fields = ('created_at',)
    can_delete = False


@admin.register(order_models.Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        'reference', 'customer_name', 'customer_company', 'delivery_city',
        'status', 'payment_status', 'total_amount', 'created_at',
    )
    list_filter = ('status', 'payment_status', 'delivery_city', 'created_at')
    search_fields = ('reference', 'customer_name', 'customer_email', 'customer_company')
    readonly_fields = ('reference', 'created_at', 'updated_at', 'total_amount', 'user')
    inlines = [OrderItemInline, PaymentInline]
    actions = ('confirm_orders', 'prepare_orders', 'ship_orders', 'deliver_orders', 'cancel_orders')

    @admin.action(description='Confirmer les commandes sélectionnées')
    def confirm_orders(self, request, queryset):
        for order in queryset.filter(status='pending'):
            order.status = 'confirmed'
            order.save(update_fields=['status', 'updated_at'])
        self.message_user(request, 'Commandes confirmées.')

    @admin.action(description="Passer en préparation")
    def prepare_orders(self, request, queryset):
        updated = queryset.filter(status='confirmed').update(status='preparing')
        self.message_user(request, f'{updated} commande(s) passée(s) en préparation.')

    @admin.action(description='Marquer comme expédiée')
    def ship_orders(self, request, queryset):
        updated = queryset.filter(status='preparing').update(status='shipped')
        self.message_user(request, f'{updated} commande(s) expédiée(s).')

    @admin.action(description='Marquer comme livrée')
    def deliver_orders(self, request, queryset):
        updated = queryset.filter(status='shipped').update(status='delivered')
        self.message_user(request, f'{updated} commande(s) livrée(s).')

    @admin.action(description='Annuler')
    def cancel_orders(self, request, queryset):
        updated = queryset.filter(status__in=('pending', 'confirmed')).update(status='cancelled')
        self.message_user(request, f'{updated} commande(s) annulée(s).')
