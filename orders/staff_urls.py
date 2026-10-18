"""Montées de routes staff des commandes (sous /api/v1/staff/)."""
from django.urls import path

from .staff_views import order_status

urlpatterns = [
    path('orders/<str:reference>/status/', order_status, name='staff-order-status'),
]
