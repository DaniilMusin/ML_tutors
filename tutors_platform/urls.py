"""
URL configuration for tutors_platform project.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    # path('api/auth/', include('apps.users.urls')),  # временно отключено
    # path('api/orders/', include('apps.orders.urls')),  # временно отключено
    # path('api/tutors/', include('apps.tutors.urls')),  # временно отключено
    # path('api/ml/', include('apps.ml.urls')),  # временно отключено
    # path('api/payments/', include('apps.payments.urls')),  # временно отключено
    # path('api/metrics/', include('django_prometheus.urls')),  # временно отключено
    # path('', include('apps.frontend.urls')),  # временно отключено
]

# Static files serving in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)