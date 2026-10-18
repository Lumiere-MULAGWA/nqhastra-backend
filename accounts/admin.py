from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import Group

from .models import BusinessProfile, User


class BusinessProfileInline(admin.StackedInline):
    model = BusinessProfile
    can_delete = False
    verbose_name_plural = "Profil d'entreprise"


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('email', 'first_name', 'last_name', 'get_company', 'get_role', 'is_active')
    list_filter = ('groups', 'is_active')
    search_fields = ('email', 'first_name', 'last_name', 'profile__company')
    ordering = ('email',)
    inlines = [BusinessProfileInline]

    fieldsets = (
        (None, {'fields': ('email', 'username', 'password')}),
        ('Informations personnelles', {'fields': ('first_name', 'last_name')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups')}),
        ('Dates importantes', {'fields': ('last_login', 'date_joined')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'username', 'password1', 'password2'),
        }),
    )

    @admin.display(description='Entreprise')
    def get_company(self, obj):
        return obj.profile.company if hasattr(obj, 'profile') else '—'

    @admin.display(description='Rôle')
    def get_role(self, obj):
        if obj.is_store_admin():
            return 'Admin'
        if obj.is_sales():
            return 'Commercial'
        return 'Client'
