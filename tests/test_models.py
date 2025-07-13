import pytest
from django.test import TestCase
from django.contrib.auth import get_user_model
from decimal import Decimal
from datetime import datetime, timedelta
from django.utils import timezone

from apps.users.models import User
from apps.tutors.models import TutorProfile, Subject, TutorReview
from apps.orders.models import Order, Application, Booking

User = get_user_model()


@pytest.mark.django_db
class TestTutorProfile:
    """Test TutorProfile model functionality."""
    
    def test_create_tutor_profile(self):
        """Test creating a tutor profile."""
        user = User.objects.create_user(
            username='testtutor',
            email='tutor@test.com',
            password='testpass123'
        )
        
        profile = TutorProfile.objects.create(
            user=user,
            bio='Experienced math tutor',
            experience_years=5,
            hourly_rate=Decimal('1500.00'),
            city='Moscow',
            region='Moscow Region'
        )
        
        assert profile.user == user
        assert profile.bio == 'Experienced math tutor'
        assert profile.experience_years == 5
        assert profile.hourly_rate == Decimal('1500.00')
        assert profile.is_premium is False
        assert profile.is_verified is False
        assert str(profile) == "testtutor - 1500.00/час"
    
    def test_add_rating(self):
        """Test adding rating to tutor profile."""
        user = User.objects.create_user(username='tutor', email='t@test.com', password='pass')
        profile = TutorProfile.objects.create(user=user, hourly_rate=Decimal('1000'))
        
        # Add first rating
        profile.add_rating(5)
        assert profile.rating == Decimal('5.00')
        assert profile.rating_count == 1
        
        # Add second rating
        profile.add_rating(4)
        assert profile.rating == Decimal('4.50')
        assert profile.rating_count == 2
    
    def test_premium_subscription(self):
        """Test premium subscription functionality."""
        user = User.objects.create_user(username='premium', email='p@test.com', password='pass')
        profile = TutorProfile.objects.create(user=user)
        
        # Activate premium
        profile.is_premium = True
        profile.premium_expires_at = timezone.now() + timedelta(days=30)
        profile.save()
        
        assert profile.is_premium is True
        assert profile.premium_expires_at is not None


@pytest.mark.django_db
class TestOrder:
    """Test Order model functionality."""
    
    def test_create_order(self):
        """Test creating an order."""
        student = User.objects.create_user(username='student', email='s@test.com', password='pass')
        subject = Subject.objects.create(name='Mathematics', category='Science')
        
        order = Order.objects.create(
            student=student,
            subject=subject,
            title='Need help with calculus',
            description='I need help understanding derivatives',
            budget_min=Decimal('1000'),
            budget_max=Decimal('2000'),
            format_online=True,
            city='Saint Petersburg'
        )
        
        assert order.student == student
        assert order.subject == subject
        assert order.title == 'Need help with calculus'
        assert order.status == 'open'
        assert order.budget_min == Decimal('1000')
        assert order.budget_max == Decimal('2000')
        assert order.format_online is True
    
    def test_order_properties(self):
        """Test order computed properties."""
        student = User.objects.create_user(username='student', email='s@test.com', password='pass')
        subject = Subject.objects.create(name='Physics')
        
        order = Order.objects.create(
            student=student,
            subject=subject,
            title='Physics help',
            budget_min=Decimal('800'),
            budget_max=Decimal('1200')
        )
        
        assert order.applications_count == 0
        assert order.budget_display == "800.00 - 1200.00 руб/час"


@pytest.mark.django_db
class TestApplication:
    """Test Application model functionality."""
    
    def test_create_application(self):
        """Test creating a tutor application."""
        # Create users and models
        student = User.objects.create_user(username='student', email='s@test.com', password='pass')
        tutor_user = User.objects.create_user(username='tutor', email='t@test.com', password='pass')
        tutor = TutorProfile.objects.create(user=tutor_user, hourly_rate=Decimal('1500'))
        subject = Subject.objects.create(name='Chemistry')
        
        order = Order.objects.create(
            student=student,
            subject=subject,
            title='Chemistry tutoring',
            budget_min=Decimal('1000'),
            budget_max=Decimal('2000')
        )
        
        application = Application.objects.create(
            order=order,
            tutor=tutor,
            price=Decimal('1500'),
            message='I have 3 years of chemistry teaching experience'
        )
        
        assert application.order == order
        assert application.tutor == tutor
        assert application.price == Decimal('1500')
        assert application.is_chosen is False
        
        # Test applications count update
        assert order.applications_count == 1


@pytest.mark.django_db
class TestBooking:
    """Test Booking model functionality."""
    
    def test_create_booking(self):
        """Test creating a booking."""
        # Setup
        student = User.objects.create_user(username='student', email='s@test.com', password='pass')
        tutor_user = User.objects.create_user(username='tutor', email='t@test.com', password='pass')
        tutor = TutorProfile.objects.create(user=tutor_user)
        subject = Subject.objects.create(name='Biology')
        
        order = Order.objects.create(student=student, subject=subject, title='Biology help')
        application = Application.objects.create(order=order, tutor=tutor, price=Decimal('1200'))
        
        booking = Booking.objects.create(
            application=application,
            total_amount=Decimal('1200'),
            platform_fee=Decimal('120'),
            tutor_amount=Decimal('1080'),
            status='pending'
        )
        
        assert booking.application == application
        assert booking.total_amount == Decimal('1200')
        assert booking.platform_fee == Decimal('120')
        assert booking.tutor_amount == Decimal('1080')
        assert booking.status == 'pending'
        assert booking.student == student
        assert booking.tutor == tutor


@pytest.mark.django_db
class TestSubject:
    """Test Subject model functionality."""
    
    def test_create_subject(self):
        """Test creating a subject."""
        subject = Subject.objects.create(
            name='Programming',
            description='Computer programming and software development',
            category='Technology',
            icon='code'
        )
        
        assert subject.name == 'Programming'
        assert subject.description == 'Computer programming and software development'
        assert subject.category == 'Technology'
        assert subject.icon == 'code'
        assert str(subject) == 'Programming'
    
    def test_subject_tutors_relationship(self):
        """Test many-to-many relationship with tutors."""
        subject = Subject.objects.create(name='English')
        user = User.objects.create_user(username='englishtutor', email='e@test.com', password='pass')
        tutor = TutorProfile.objects.create(user=user)
        
        subject.tutors.add(tutor)
        
        assert tutor in subject.tutors.all()
        assert subject in tutor.subjects.all()


@pytest.mark.django_db
class TestTutorReview:
    """Test TutorReview model functionality."""
    
    def test_create_review(self):
        """Test creating a tutor review."""
        student = User.objects.create_user(username='student', email='s@test.com', password='pass')
        tutor_user = User.objects.create_user(username='tutor', email='t@test.com', password='pass')
        tutor = TutorProfile.objects.create(user=tutor_user)
        
        review = TutorReview.objects.create(
            tutor=tutor,
            student=student,
            rating=5,
            review_text='Excellent tutor, very patient and knowledgeable!'
        )
        
        assert review.tutor == tutor
        assert review.student == student
        assert review.rating == 5
        assert review.review_text == 'Excellent tutor, very patient and knowledgeable!'
        assert str(review) == f"Review for {tutor.user.username} by {student.username} (5/5)"