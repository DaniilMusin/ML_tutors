from django.urls import re_path
from apps.orders.consumers import OrderConsumer, TutorNotificationConsumer

websocket_urlpatterns = [
    re_path(r'ws/order/(?P<order_id>\d+)/$', OrderConsumer.as_asgi()),
    re_path(r'ws/tutor/notifications/$', TutorNotificationConsumer.as_asgi()),
]