from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import TutorProfileViewSet, SubjectViewSet, TutorReviewViewSet

app_name = 'tutors'

router = DefaultRouter()
router.register(r'profiles', TutorProfileViewSet, basename='tutorprofile')
router.register(r'subjects', SubjectViewSet, basename='subject')
router.register(r'reviews', TutorReviewViewSet, basename='tutorreview')

urlpatterns = [
    path('', include(router.urls)),
]