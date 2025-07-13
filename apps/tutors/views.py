from rest_framework import viewsets, status, permissions, serializers
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db import models
from django.db.models import Q, Avg
from .models import TutorProfile, Subject, TutorReview
from .serializers import (
    TutorProfileSerializer, TutorProfileCreateSerializer,
    SubjectSerializer, TutorReviewSerializer
)


class TutorProfileViewSet(viewsets.ModelViewSet):
    """
    ViewSet для управления профилями репетиторов.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        if self.action == 'create':
            return TutorProfileCreateSerializer
        return TutorProfileSerializer

    def get_queryset(self):
        queryset = TutorProfile.objects.select_related('user').prefetch_related(
            'subjects', 'reviews'
        ).all()
        
        # Фильтрация
        subject_id = self.request.query_params.get('subject', None)
        city = self.request.query_params.get('city', None)
        min_rating = self.request.query_params.get('min_rating', None)
        max_price = self.request.query_params.get('max_price', None)
        verified_only = self.request.query_params.get('verified', None)
        
        if subject_id:
            queryset = queryset.filter(subjects__id=subject_id)
        if city:
            queryset = queryset.filter(city__icontains=city)
        if min_rating:
            queryset = queryset.filter(rating__gte=float(min_rating))
        if max_price:
            queryset = queryset.filter(hourly_rate__lte=float(max_price))
        if verified_only == 'true':
            queryset = queryset.filter(is_verified=True)
            
        return queryset.order_by('-rating', '-created_at')

    def perform_create(self, serializer):
        # Проверяем, что у пользователя еще нет профиля репетитора
        if TutorProfile.objects.filter(user=self.request.user).exists():
            raise serializers.ValidationError(
                "У вас уже есть профиль репетитора"
            )
        serializer.save()

    @action(detail=False, methods=['get'])
    def my_profile(self, request):
        """Получить профиль текущего пользователя"""
        try:
            profile = TutorProfile.objects.get(user=request.user)
            serializer = self.get_serializer(profile)
            return Response(serializer.data)
        except TutorProfile.DoesNotExist:
            return Response(
                {'error': 'Профиль репетитора не найден'}, 
                status=status.HTTP_404_NOT_FOUND
            )

    @action(detail=True, methods=['post'])
    def add_review(self, request, pk=None):
        """Добавить отзыв репетитору"""
        tutor = self.get_object()
        
        # Проверяем, что пользователь не оставляет отзыв самому себе
        if tutor.user == request.user:
            return Response(
                {'error': 'Нельзя оставлять отзыв самому себе'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Проверяем, что пользователь еще не оставлял отзыв
        if TutorReview.objects.filter(tutor=tutor, student=request.user).exists():
            return Response(
                {'error': 'Вы уже оставляли отзыв этому репетитору'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = TutorReviewSerializer(data=request.data)
        if serializer.is_valid():
            review = serializer.save(tutor=tutor, student=request.user)
            
            # Обновляем рейтинг репетитора
            tutor.add_rating(review.rating)
            
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['get'])
    def search(self, request):
        """Поиск репетиторов"""
        query = request.query_params.get('q', '')
        
        if not query:
            return Response([])
        
        tutors = self.get_queryset().filter(
            Q(user__first_name__icontains=query) |
            Q(user__last_name__icontains=query) |
            Q(bio__icontains=query) |
            Q(subjects__name__icontains=query)
        ).distinct()
        
        serializer = self.get_serializer(tutors, many=True)
        return Response(serializer.data)


class SubjectViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet для просмотра предметов.
    """
    queryset = Subject.objects.all().order_by('name')
    serializer_class = SubjectSerializer
    permission_classes = [permissions.IsAuthenticated]

    @action(detail=False, methods=['get'])
    def popular(self, request):
        """Получить популярные предметы"""
        # Предметы с наибольшим количеством репетиторов
        popular_subjects = Subject.objects.annotate(
            tutors_count=models.Count('tutors')
        ).filter(tutors_count__gt=0).order_by('-tutors_count')[:10]
        
        serializer = self.get_serializer(popular_subjects, many=True)
        return Response(serializer.data)


class TutorReviewViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet для просмотра отзывов.
    """
    serializer_class = TutorReviewSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        tutor_id = self.request.query_params.get('tutor', None)
        if tutor_id:
            return TutorReview.objects.filter(tutor_id=tutor_id).select_related(
                'student', 'tutor'
            ).order_by('-created_at')
        return TutorReview.objects.all().select_related(
            'student', 'tutor'
        ).order_by('-created_at')