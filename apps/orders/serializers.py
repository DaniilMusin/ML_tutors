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

    def validate(self, attrs):
        """Validate order data."""
        budget_min = attrs.get('budget_min', 0)
        budget_max = attrs.get('budget_max', 0)

        # Validate budget values are positive
        if budget_min < 0:
            raise serializers.ValidationError({
                'budget_min': 'Минимальный бюджет не может быть отрицательным'
            })

        if budget_max < 0:
            raise serializers.ValidationError({
                'budget_max': 'Максимальный бюджет не может быть отрицательным'
            })

        # Validate budget_max >= budget_min
        if budget_max < budget_min:
            raise serializers.ValidationError({
                'budget_max': 'Максимальный бюджет должен быть больше или равен минимальному'
            })

        # Validate at least one budget is set
        if budget_max == 0 and budget_min == 0:
            raise serializers.ValidationError({
                'budget_max': 'Укажите бюджет для заказа'
            })

        # Validate format is selected
        format_online = attrs.get('format_online', False)
        format_offline = attrs.get('format_offline', False)
        if not format_online and not format_offline:
            raise serializers.ValidationError({
                'format_online': 'Выберите хотя бы один формат занятий (онлайн или оффлайн)'
            })

        # Validate offline location
        if format_offline:
            if not attrs.get('city'):
                raise serializers.ValidationError({
                    'city': 'Укажите город для оффлайн занятий'
                })

        return attrs

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

        # Validate user is a tutor
        if user.role != 'tutor':
            raise serializers.ValidationError(
                "Только репетиторы могут откликаться на заказы"
            )

        # Get tutor profile (must exist, don't create automatically)
        try:
            tutor_profile = TutorProfile.objects.get(user=user)
        except TutorProfile.DoesNotExist:
            raise serializers.ValidationError(
                "Профиль репетитора не найден. Пожалуйста, создайте профиль сначала."
            )

        # Validate tutor profile is complete
        if not tutor_profile.bio or tutor_profile.hourly_rate <= 0:
            raise serializers.ValidationError(
                "Заполните профиль репетитора перед откликом на заказы"
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