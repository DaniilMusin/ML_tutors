from rest_framework import serializers
from .models import TutorProfile, Subject, TutorReview
from django.contrib.auth import get_user_model

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name', 'email', 'date_joined']


class SubjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subject
        fields = ['id', 'name', 'description', 'category', 'icon', 'created_at']


class TutorReviewSerializer(serializers.ModelSerializer):
    student = UserSerializer(read_only=True)
    
    class Meta:
        model = TutorReview
        fields = ['id', 'student', 'rating', 'review_text', 'created_at']
        read_only_fields = ['id', 'student', 'created_at']


class TutorProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    subjects = SubjectSerializer(many=True, read_only=True)
    subject_ids = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True,
        required=False
    )
    reviews = TutorReviewSerializer(many=True, read_only=True)
    subjects_display = serializers.ReadOnlyField()
    
    class Meta:
        model = TutorProfile
        fields = [
            'id', 'user', 'bio', 'experience_years', 'hourly_rate',
            'rating', 'rating_count', 'availability', 'city', 'region',
            'is_verified', 'verification_documents', 'subjects',
            'subject_ids', 'reviews', 'subjects_display',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'user', 'rating', 'rating_count', 'is_verified',
            'created_at', 'updated_at'
        ]

    def update(self, instance, validated_data):
        subject_ids = validated_data.pop('subject_ids', None)
        
        # Обновляем основные поля
        instance = super().update(instance, validated_data)
        
        # Обновляем связанные предметы
        if subject_ids is not None:
            subjects = Subject.objects.filter(id__in=subject_ids)
            instance.subjects.set(subjects)
        
        return instance


class TutorProfileCreateSerializer(serializers.ModelSerializer):
    subject_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False
    )
    
    class Meta:
        model = TutorProfile
        fields = [
            'bio', 'experience_years', 'hourly_rate', 'availability',
            'city', 'region', 'subject_ids'
        ]

    def create(self, validated_data):
        subject_ids = validated_data.pop('subject_ids', [])
        validated_data['user'] = self.context['request'].user
        
        tutor_profile = TutorProfile.objects.create(**validated_data)
        
        if subject_ids:
            subjects = Subject.objects.filter(id__in=subject_ids)
            tutor_profile.subjects.set(subjects)
        
        return tutor_profile