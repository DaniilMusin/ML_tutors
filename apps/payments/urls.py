from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import CreateCheckoutSessionView, stripe_webhook

app_name = 'payments'

router = DefaultRouter()

urlpatterns = [
    path('', include(router.urls)),
    path('checkout/', CreateCheckoutSessionView.as_view(), name='checkout'),
    path('webhook/', stripe_webhook, name='stripe_webhook'),
]