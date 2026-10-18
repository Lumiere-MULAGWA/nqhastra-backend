"""Routes staff des ventes (sous /api/v1/staff/)."""
from django.urls import path

from .views import DailyRateView, register_sessions, register_close, register_detail

urlpatterns = [
    path('rate/', DailyRateView.as_view(), name='staff-daily-rate'),
    path('register/', register_sessions, name='staff-register'),
    path('register/<int:pk>/close/', register_close, name='staff-register-close'),
    path('register/<int:pk>/', register_detail, name='staff-register-detail'),
]
