from django.urls import path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()

urlpatterns = [
    path('orders/<str:reference>/pay/', views.order_pay, name='order-pay'),
    path('payments/webhook/', views.webhook, name='webhook'),
    path('payments/<str:provider_reference>/simulate/', views.simulate, name='payments-simulate'),
]
