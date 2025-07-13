from rest_framework import serializers
from .models import Order, Application, Booking, EmbeddingCache
from apps.tutors.models import TutorProfile, Subject
from django.contrib.auth import get_user_model

User = get_user_model()


class SubjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subject
        fields = ['id', 'name', 'description', 'category', 'icon']


class UserBasicSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name', 'email']


class TutorProfileBasicSerializer(serializers.ModelSerializer):
    user = UserBasicSerializer(read_only=True)
    subjects = SubjectSerializer(many=True, read_only=True)
    
    class Meta:
        model = TutorProfile
        fields = ['id', 'user', 'bio', 'experience_years', 'hourly_rate', 
                 'rating', 'rating_count', 'city', 'region', 'is_verified', 'subjects']


class OrderSerializer(serializers.ModelSerializer):
    student = UserBasicSerializer(read_only=True)
    subject = SubjectSerializer(read_only=True)
    subject_id = serializers.IntegerField(write_only=True)
    applications_count = serializers.ReadOnlyField()
    budget_display = serializers.ReadOnlyField()
    
    class Meta:
        model = Order
        fields = [
            'id', 'student', 'subject', 'subject_id', 'title', 'description', 
            'goal_text', 'budget_min', 'budget_max', 'budget_display',
            'schedule_json', 'timezone', 'format_online', 'format_offline',
            'city', 'region', 'status', 'created_at', 'updated_at', 
            'expires_at', 'applications_count'
        ]
        read_only_fields = ['id', 'student', 'created_at', 'updated_at']

    def create(self, validated_data):
        validated_data['student'] = self.context['request'].user
        return super().create(validated_data)


class ApplicationSerializer(serializers.ModelSerializer):
    tutor = TutorProfileBasicSerializer(read_only=True)
    order = OrderSerializer(read_only=True)
    order_id = serializers.IntegerField(write_only=True)
    
    class Meta:
        model = Application
        fields = [
            'id', 'order', 'order_id', 'tutor', 'price', 'message', 
            'is_chosen', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'tutor', 'is_chosen', 'created_at', 'updated_at']

    def create(self, validated_data):
        user = self.context['request'].user
        # Get or create tutor profile for the user
        tutor_profile, created = TutorProfile.objects.get_or_create(
            user=user,
            defaults={
                'bio': '',
                'experience_years': 0,
                'hourly_rate': 0
            }
        )
        validated_data['tutor'] = tutor_profile
        return super().create(validated_data)


class BookingSerializer(serializers.ModelSerializer):
    application = ApplicationSerializer(read_only=True)
    student = serializers.ReadOnlyField(source='application.order.student.username')
    tutor = serializers.ReadOnlyField(source='application.tutor.user.username')
    
    class Meta:
        model = Booking
        fields = [
            'id', 'application', 'student', 'tutor', 'stripe_session_id',
            'stripe_payment_intent_id', 'total_amount', 'platform_fee',
            'tutor_amount', 'status', 'session_start', 'session_end',
            'session_notes', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'stripe_session_id', 'stripe_payment_intent_id', 
            'created_at', 'updated_at'
        ]


class EmbeddingCacheSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmbeddingCache
        fields = ['id', 'text', 'text_hash', 'vector', 'created_at']
        read_only_fields = ['id', 'created_at']