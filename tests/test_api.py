import pytest
import json
from rest_framework.test import APIClient
from rest_framework import status
from django.contrib.auth import get_user_model
from decimal import Decimal
from unittest.mock import patch

from apps.tutors.models import TutorProfile, Subject
from apps.orders.models import Order, Application, Booking

User = get_user_model()


@pytest.mark.django_db
class TestOrderAPI:
    """Test Order API endpoints."""
    
    def setup_method(self):
        """Setup test data."""
        self.client = APIClient()
        self.student = User.objects.create_user(
            username='student',
            email='student@test.com',
            password='testpass123'
        )
        self.tutor_user = User.objects.create_user(
            username='tutor',
            email='tutor@test.com',
            password='testpass123'
        )
        self.tutor = TutorProfile.objects.create(
            user=self.tutor_user,
            hourly_rate=Decimal('1500')
        )
        self.subject = Subject.objects.create(name='Mathematics')
    
    def test_create_order_authenticated(self):
        """Test creating order as authenticated student."""
        self.client.force_authenticate(user=self.student)
        
        data = {
            'subject': self.subject.id,
            'title': 'Need calculus help',
            'description': 'Struggling with derivatives',
            'budget_min': '1000',
            'budget_max': '2000',
            'format_online': True,
            'city': 'Moscow'
        }
        
        response = self.client.post('/api/orders/', data)
        assert response.status_code == status.HTTP_201_CREATED
        assert Order.objects.count() == 1
        
        order = Order.objects.first()
        assert order.student == self.student
        assert order.title == 'Need calculus help'
    
    def test_create_order_unauthenticated(self):
        """Test creating order without authentication."""
        data = {
            'subject': self.subject.id,
            'title': 'Test order',
            'description': 'Test description',
            'budget_min': '1000',
            'budget_max': '2000'
        }
        
        response = self.client.post('/api/orders/', data)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    def test_list_orders(self):
        """Test listing orders."""
        # Create test orders
        Order.objects.create(
            student=self.student,
            subject=self.subject,
            title='Order 1',
            budget_min=Decimal('1000'),
            budget_max=Decimal('2000')
        )
        Order.objects.create(
            student=self.student,
            subject=self.subject,
            title='Order 2',
            budget_min=Decimal('1500'),
            budget_max=Decimal('2500')
        )
        
        response = self.client.get('/api/orders/')
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['results']) == 2
    
    def test_retrieve_order(self):
        """Test retrieving single order."""
        order = Order.objects.create(
            student=self.student,
            subject=self.subject,
            title='Test Order',
            description='Test description',
            budget_min=Decimal('1000'),
            budget_max=Decimal('2000')
        )
        
        response = self.client.get(f'/api/orders/{order.id}/')
        assert response.status_code == status.HTTP_200_OK
        assert response.data['title'] == 'Test Order'
        assert response.data['description'] == 'Test description'


@pytest.mark.django_db
class TestApplicationAPI:
    """Test Application API endpoints."""
    
    def setup_method(self):
        """Setup test data."""
        self.client = APIClient()
        self.student = User.objects.create_user(
            username='student',
            email='student@test.com',
            password='testpass123'
        )
        self.tutor_user = User.objects.create_user(
            username='tutor',
            email='tutor@test.com',
            password='testpass123'
        )
        self.tutor = TutorProfile.objects.create(
            user=self.tutor_user,
            hourly_rate=Decimal('1500')
        )
        self.subject = Subject.objects.create(name='Physics')
        self.order = Order.objects.create(
            student=self.student,
            subject=self.subject,
            title='Physics help needed',
            budget_min=Decimal('1000'),
            budget_max=Decimal('2000')
        )
    
    def test_create_application_as_tutor(self):
        """Test tutor creating application."""
        self.client.force_authenticate(user=self.tutor_user)
        
        data = {
            'order': self.order.id,
            'price': '1500',
            'message': 'I have 5 years of physics teaching experience'
        }
        
        response = self.client.post('/api/orders/applications/', data)
        assert response.status_code == status.HTTP_201_CREATED
        assert Application.objects.count() == 1
        
        application = Application.objects.first()
        assert application.tutor == self.tutor
        assert application.price == Decimal('1500')
    
    def test_create_application_as_student_fails(self):
        """Test that student cannot create application."""
        self.client.force_authenticate(user=self.student)
        
        data = {
            'order': self.order.id,
            'price': '1500',
            'message': 'Test message'
        }
        
        response = self.client.post('/api/orders/applications/', data)
        assert response.status_code == status.HTTP_403_FORBIDDEN
    
    def test_list_applications_for_order(self):
        """Test listing applications for specific order."""
        # Create applications
        Application.objects.create(
            order=self.order,
            tutor=self.tutor,
            price=Decimal('1500'),
            message='Application 1'
        )
        
        # Create another tutor and application
        tutor2_user = User.objects.create_user(username='tutor2', email='t2@test.com', password='pass')
        tutor2 = TutorProfile.objects.create(user=tutor2_user)
        Application.objects.create(
            order=self.order,
            tutor=tutor2,
            price=Decimal('1800'),
            message='Application 2'
        )
        
        self.client.force_authenticate(user=self.student)
        response = self.client.get(f'/api/orders/{self.order.id}/applications/')
        
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 2


@pytest.mark.django_db
class TestTutorAPI:
    """Test Tutor API endpoints."""
    
    def setup_method(self):
        """Setup test data."""
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='testtutor',
            email='tutor@test.com',
            password='testpass123'
        )
        self.tutor = TutorProfile.objects.create(
            user=self.user,
            bio='Experienced tutor',
            experience_years=5,
            hourly_rate=Decimal('1500'),
            city='Moscow'
        )
        self.subject = Subject.objects.create(name='Chemistry')
    
    def test_list_tutors(self):
        """Test listing tutors."""
        response = self.client.get('/api/tutors/')
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['results']) == 1
        assert response.data['results'][0]['bio'] == 'Experienced tutor'
    
    def test_retrieve_tutor(self):
        """Test retrieving single tutor."""
        response = self.client.get(f'/api/tutors/{self.tutor.id}/')
        assert response.status_code == status.HTTP_200_OK
        assert response.data['bio'] == 'Experienced tutor'
        assert response.data['experience_years'] == 5
    
    def test_update_tutor_profile_authenticated(self):
        """Test updating tutor profile as owner."""
        self.client.force_authenticate(user=self.user)
        
        data = {
            'bio': 'Updated bio',
            'experience_years': 6,
            'hourly_rate': '1600'
        }
        
        response = self.client.patch(f'/api/tutors/{self.tutor.id}/', data)
        assert response.status_code == status.HTTP_200_OK
        
        self.tutor.refresh_from_db()
        assert self.tutor.bio == 'Updated bio'
        assert self.tutor.experience_years == 6
    
    def test_update_tutor_profile_unauthorized(self):
        """Test updating tutor profile as non-owner."""
        other_user = User.objects.create_user(username='other', email='other@test.com', password='pass')
        self.client.force_authenticate(user=other_user)
        
        data = {'bio': 'Unauthorized update'}
        response = self.client.patch(f'/api/tutors/{self.tutor.id}/', data)
        assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db 
class TestMLAPI:
    """Test ML API endpoints."""
    
    def setup_method(self):
        """Setup test data."""
        self.client = APIClient()
        self.student = User.objects.create_user(
            username='student',
            email='student@test.com',
            password='testpass123'
        )
        self.subject = Subject.objects.create(name='Programming')
        self.order = Order.objects.create(
            student=self.student,
            subject=self.subject,
            title='Learn Python',
            description='Need help with Python basics',
            budget_min=Decimal('1000'),
            budget_max=Decimal('2000')
        )
    
    @patch('apps.ml.services.AIMatchingService.get_ai_matches')
    def test_match_api_success(self, mock_get_matches):
        """Test AI matching API success."""
        # Mock AI service response
        mock_get_matches.return_value = [
            {
                'tutor_id': 1,
                'score': 0.95,
                'reasons': ['Subject match', 'Experience level'],
                'profile': {'name': 'John Doe', 'rating': 4.8}
            }
        ]
        
        self.client.force_authenticate(user=self.student)
        
        data = {
            'order_id': self.order.id,
            'limit': 3
        }
        
        response = self.client.post('/api/ml/match/', data)
        assert response.status_code == status.HTTP_200_OK
        assert response.data['order_id'] == self.order.id
        assert len(response.data['matches']) == 1
        assert response.data['matches'][0]['score'] == 0.95
    
    def test_match_api_invalid_order(self):
        """Test AI matching API with invalid order."""
        self.client.force_authenticate(user=self.student)
        
        data = {
            'order_id': 99999,  # Non-existent order
            'limit': 3
        }
        
        response = self.client.post('/api/ml/match/', data)
        assert response.status_code == status.HTTP_404_NOT_FOUND
    
    def test_match_api_missing_order_id(self):
        """Test AI matching API without order_id."""
        self.client.force_authenticate(user=self.student)
        
        data = {'limit': 3}  # Missing order_id
        
        response = self.client.post('/api/ml/match/', data)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'order_id is required' in response.data['error']


@pytest.mark.django_db
class TestPaymentsAPI:
    """Test Payments API endpoints."""
    
    def setup_method(self):
        """Setup test data."""
        self.client = APIClient()
        self.tutor_user = User.objects.create_user(
            username='tutor',
            email='tutor@test.com',
            password='testpass123'
        )
        self.tutor = TutorProfile.objects.create(
            user=self.tutor_user,
            hourly_rate=Decimal('1500')
        )
    
    @patch('stripe.checkout.Session.create')
    def test_create_premium_checkout_session(self, mock_stripe_create):
        """Test creating premium checkout session."""
        # Mock Stripe response
        mock_stripe_create.return_value.url = 'https://checkout.stripe.com/test'
        mock_stripe_create.return_value.id = 'cs_test_123'
        
        self.client.force_authenticate(user=self.tutor_user)
        
        data = {'type': 'premium'}
        
        response = self.client.post('/api/payments/checkout/', data)
        assert response.status_code == status.HTTP_200_OK
        assert 'checkout_url' in response.data
        assert 'session_id' in response.data
    
    def test_create_checkout_session_invalid_type(self):
        """Test creating checkout session with invalid type."""
        self.client.force_authenticate(user=self.tutor_user)
        
        data = {'type': 'invalid_type'}
        
        response = self.client.post('/api/payments/checkout/', data)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'Invalid payment type' in response.data['error']
    
    def test_create_premium_checkout_already_premium(self):
        """Test creating premium checkout when already premium."""
        # Make tutor premium
        self.tutor.is_premium = True
        self.tutor.save()
        
        self.client.force_authenticate(user=self.tutor_user)
        
        data = {'type': 'premium'}
        
        response = self.client.post('/api/payments/checkout/', data)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'Already have premium subscription' in response.data['error']