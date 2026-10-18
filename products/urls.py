from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import CategoryViewSet, ProductViewSet
from .staff_views import StaffProductViewSet, StaffVariantViewSet, low_stock_list

public_router = DefaultRouter()
public_router.register('categories', CategoryViewSet, basename='category')
public_router.register('products', ProductViewSet, basename='product')

staff_router = DefaultRouter()
staff_router.register('staff/products', StaffProductViewSet, basename='staff-product')
staff_router.register('staff/variants', StaffVariantViewSet, basename='staff-variant')

urlpatterns = [
    *public_router.urls,
    # Routes du back-office (staff only, sous /api/v1/staff/)
    path('staff/low-stock/', low_stock_list, name='staff-low-stock'),
    *staff_router.urls,
]
