"""
URL configuration for tutors_platform project.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/auth/', include('apps.users.urls')),
    path('api/orders/', include('apps.orders.urls')),
    path('api/tutors/', include('apps.tutors.urls')),
    path('api/ml/', include('apps.ml.urls')),
    path('api/payments/', include('apps.payments.urls')),
    path('', include('apps.frontend.urls')),
]

# Prometheus metrics (optional, enable if needed)
# if not settings.DEBUG:
#     urlpatterns.append(path('api/metrics/', include('django_prometheus.urls')))

# Static files serving in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)