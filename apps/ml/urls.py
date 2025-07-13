from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import MatchView

app_name = 'ml'

router = DefaultRouter()

urlpatterns = [
    path('', include(router.urls)),
    path('match/', MatchView.as_view(), name='match'),
]