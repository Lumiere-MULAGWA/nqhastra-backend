from django.contrib import admin

from .models import Sale, SaleLine


class SaleLineInline(admin.TabularInline):
    model = SaleLine
    extra = 0
    readonly_fields = ('sku_snapshot', 'name_snapshot', 'line_total')


@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = ('reference', 'cashier', 'payment_method', 'status', 'total', 'amount_paid', 'change_due', 'created_at')
    list_filter = ('payment_method', 'status', 'created_at')
    search_fields = ('reference', 'customer_name', 'customer_phone')
    readonly_fields = ('reference', 'total', 'amount_paid', 'change_due', 'created_at', 'cashier')
    inlines = [SaleLineInline]
    actions = ('mark_paid',)

    @admin.action(description='Marquer les ventes à crédit comme payées')
    def mark_paid(self, request, queryset):
        for sale in queryset.filter(status='credit'):
            sale.status = 'paid'
            sale.amount_paid = sale.total
            sale.save(update_fields=['status', 'amount_paid'])
        self.message_user(request, 'Ventes à crédit soldées.')
