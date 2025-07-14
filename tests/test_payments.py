import pytest
import json
from unittest.mock import patch, Mock
from django.test import Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta

from apps.payments.models import StripeWebhookEvent, Payment
from apps.tutors.models import TutorProfile, Subject
from apps.orders.models import Booking

User = get_user_model()


@pytest.mark.django_db
class TestStripeWebhookIdempotency:
    """Test Stripe webhook idempotency."""
    
    def setup_method(self):
        """Setup test data."""
        self.client = Client()
        self.webhook_url = reverse('stripe_webhook')
        
        # Create test user and tutor
        self.user = User.objects.create_user(
            username='testtutor',
            email='tutor@test.com',
            password='testpass123'
        )
        
        self.tutor_profile = TutorProfile.objects.create(
            user=self.user,
            bio='Test tutor',
            experience_years=3,
            hourly_rate=1000,
            stripe_customer_id='cus_test123'
        )
    
    @patch('stripe.Webhook.construct_event')
    def test_webhook_idempotency_first_call(self, mock_construct_event):
        """Test webhook processes successfully on first call."""
        # Mock Stripe event
        mock_event = {
            'id': 'evt_test123',
            'type': 'checkout.session.completed',
            'data': {'object': {'id': 'cs_test123'}}
        }
        mock_construct_event.return_value = mock_event
        
        # First call should process successfully
        response = self.client.post(
            self.webhook_url,
            data='test_payload',
            content_type='application/json',
            HTTP_STRIPE_SIGNATURE='test_signature'
        )
        
        assert response.status_code == 200
        assert StripeWebhookEvent.objects.filter(stripe_event_id='evt_test123').exists()
    
    @patch('stripe.Webhook.construct_event')
    def test_webhook_idempotency_duplicate_call(self, mock_construct_event):
        """Test webhook skips processing on duplicate call."""
        # Create existing webhook event
        StripeWebhookEvent.objects.create(
            stripe_event_id='evt_test123',
            event_type='checkout.session.completed'
        )
        
        # Mock Stripe event
        mock_event = {
            'id': 'evt_test123',
            'type': 'checkout.session.completed',
            'data': {'object': {'id': 'cs_test123'}}
        }
        mock_construct_event.return_value = mock_event
        
        # Second call should skip processing
        response = self.client.post(
            self.webhook_url,
            data='test_payload',
            content_type='application/json',
            HTTP_STRIPE_SIGNATURE='test_signature'
        )
        
        assert response.status_code == 200
        # Should only have one record
        assert StripeWebhookEvent.objects.filter(stripe_event_id='evt_test123').count() == 1
    
    @patch('stripe.Webhook.construct_event')
    def test_webhook_subscription_payment(self, mock_construct_event):
        """Test subscription payment processing."""
        mock_event = {
            'id': 'evt_test456',
            'type': 'invoice.payment_succeeded',
            'data': {
                'object': {
                    'customer': 'cus_test123'
                }
            }
        }
        mock_construct_event.return_value = mock_event
        
        # Process webhook
        response = self.client.post(
            self.webhook_url,
            data='test_payload',
            content_type='application/json',
            HTTP_STRIPE_SIGNATURE='test_signature'
        )
        
        assert response.status_code == 200
        
        # Check that tutor premium was extended
        self.tutor_profile.refresh_from_db()
        assert self.tutor_profile.is_premium
        assert self.tutor_profile.premium_expires_at > timezone.now()
    
    @patch('stripe.Webhook.construct_event')
    def test_webhook_subscription_cancelled(self, mock_construct_event):
        """Test subscription cancellation processing."""
        # Set up premium tutor
        self.tutor_profile.is_premium = True
        self.tutor_profile.premium_expires_at = timezone.now() + timedelta(days=10)
        self.tutor_profile.save()
        
        mock_event = {
            'id': 'evt_test789',
            'type': 'customer.subscription.deleted',
            'data': {
                'object': {
                    'customer': 'cus_test123'
                }
            }
        }
        mock_construct_event.return_value = mock_event
        
        # Process webhook
        response = self.client.post(
            self.webhook_url,
            data='test_payload',
            content_type='application/json',
            HTTP_STRIPE_SIGNATURE='test_signature'
        )
        
        assert response.status_code == 200
        
        # Check that tutor premium was cancelled
        self.tutor_profile.refresh_from_db()
        assert not self.tutor_profile.is_premium


@pytest.mark.django_db
class TestPaymentModels:
    """Test payment models."""
    
    def setup_method(self):
        """Setup test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='user@test.com',
            password='testpass123'
        )
    
    def test_stripe_webhook_event_creation(self):
        """Test StripeWebhookEvent model creation."""
        event = StripeWebhookEvent.objects.create(
            stripe_event_id='evt_test123',
            event_type='checkout.session.completed'
        )
        
        assert event.stripe_event_id == 'evt_test123'
        assert event.event_type == 'checkout.session.completed'
        assert event.processed_at is not None
        
    def test_stripe_webhook_event_uniqueness(self):
        """Test that webhook event IDs are unique."""
        StripeWebhookEvent.objects.create(
            stripe_event_id='evt_test123',
            event_type='checkout.session.completed'
        )
        
        # Creating duplicate should raise error
        with pytest.raises(Exception):  # IntegrityError
            StripeWebhookEvent.objects.create(
                stripe_event_id='evt_test123',
                event_type='checkout.session.completed'
            )
    
    def test_payment_model_creation(self):
        """Test Payment model creation."""
        payment = Payment.objects.create(
            stripe_session_id='cs_test123',
            amount=1500.00,
            currency='RUB',
            payment_type='premium',
            user=self.user
        )
        
        assert payment.amount == 1500.00
        assert payment.currency == 'RUB'
        assert payment.payment_type == 'premium'
        assert payment.status == 'pending'
        assert payment.user == self.user


@pytest.mark.django_db 
class TestTutorProfileCustomerId:
    """Test TutorProfile customer_id functionality."""
    
    def setup_method(self):
        """Setup test data."""
        self.user = User.objects.create_user(
            username='testtutor',
            email='tutor@test.com', 
            password='testpass123'
        )
        
        self.tutor_profile = TutorProfile.objects.create(
            user=self.user,
            bio='Test tutor',
            experience_years=2,
            hourly_rate=1200
        )
    
    def test_tutor_profile_customer_id_field(self):
        """Test that customer_id field works correctly."""
        # Initially no customer_id
        assert self.tutor_profile.stripe_customer_id is None
        
        # Set customer_id
        self.tutor_profile.stripe_customer_id = 'cus_test123'
        self.tutor_profile.save()
        
        # Refresh and check
        self.tutor_profile.refresh_from_db()
        assert self.tutor_profile.stripe_customer_id == 'cus_test123'
    
    def test_find_tutor_by_customer_id(self):
        """Test finding tutor by Stripe customer ID."""
        self.tutor_profile.stripe_customer_id = 'cus_test456'
        self.tutor_profile.save()
        
        # Should find tutor by customer_id
        found_tutor = TutorProfile.objects.filter(
            stripe_customer_id='cus_test456'
        ).first()
        
        assert found_tutor == self.tutor_profile
        
        # Should not find with wrong customer_id
        not_found = TutorProfile.objects.filter(
            stripe_customer_id='cus_wrong'
        ).first()
        
        assert not_found is None