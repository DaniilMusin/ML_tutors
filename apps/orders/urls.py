from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import OrderViewSet, ApplicationViewSet, BookingViewSet

app_name = 'orders'

router = DefaultRouter()
router.register(r'orders', OrderViewSet, basename='order')
router.register(r'applications', ApplicationViewSet, basename='application')
router.register(r'bookings', BookingViewSet, basename='booking')

urlpatterns = [
    path('', include(router.urls)),
]