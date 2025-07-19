import pytest
import django
from django.conf import settings

# Настройка Django перед импортом моделей
if not settings.configured:
    django.setup()

from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from decimal import Decimal

from apps.tutors.models import TutorProfile, Subject
from apps.orders.models import Order

User = get_user_model()


@pytest.fixture
def api_client():
    """Provide API client for testing."""
    return APIClient()


@pytest.fixture
def student_user():
    """Create a test student user."""
    return User.objects.create_user(
        username='teststudent',
        email='student@test.com',
        password='testpass123',
        first_name='Test',
        last_name='Student'
    )


@pytest.fixture
def tutor_user():
    """Create a test tutor user."""
    return User.objects.create_user(
        username='testtutor',
        email='tutor@test.com',
        password='testpass123',
        first_name='Test',
        last_name='Tutor'
    )


@pytest.fixture
def tutor_profile(tutor_user):
    """Create a test tutor profile."""
    return TutorProfile.objects.create(
        user=tutor_user,
        bio='Experienced tutor with 5 years of teaching',
        experience_years=5,
        hourly_rate=Decimal('1500.00'),
        city='Moscow',
        region='Moscow Region',
        is_verified=True
    )


@pytest.fixture
def math_subject():
    """Create a mathematics subject."""
    return Subject.objects.create(
        name='Mathematics',
        description='Mathematics and calculus',
        category='Science',
        icon='calculator'
    )


@pytest.fixture
def test_order(student_user, math_subject):
    """Create a test order."""
    return Order.objects.create(
        student=student_user,
        subject=math_subject,
        title='Need help with calculus',
        description='I need help understanding derivatives and integrals',
        budget_min=Decimal('1000'),
        budget_max=Decimal('2000'),
        format_online=True,
        city='Moscow'
    )


@pytest.fixture
def authenticated_client(api_client, student_user):
    """Provide authenticated API client with student user."""
    api_client.force_authenticate(user=student_user)
    return api_client


@pytest.fixture
def tutor_authenticated_client(api_client, tutor_user):
    """Provide authenticated API client with tutor user."""
    api_client.force_authenticate(user=tutor_user)
    return api_client