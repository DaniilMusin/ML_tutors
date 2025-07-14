import stripe
import json
import logging
from django.conf import settings
from django.http import HttpResponse, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.utils.decorators import method_decorator
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from datetime import datetime, timedelta
from django.utils import timezone
from django.db import transaction

from apps.tutors.models import TutorProfile
from apps.orders.models import Booking
from .models import StripeWebhookEvent, Payment

stripe.api_key = settings.STRIPE_SECRET_KEY
logger = logging.getLogger(__name__)


class CreateCheckoutSessionView(APIView):
    """
    Create Stripe checkout session for premium subscription or booking payment.
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        try:
            payment_type = request.data.get('type')  # 'premium' or 'booking'
            
            if payment_type == 'premium':
                return self._create_premium_session(request)
            elif payment_type == 'booking':
                return self._create_booking_session(request)
            else:
                return Response(
                    {'error': 'Invalid payment type. Use "premium" or "booking"'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
                
        except Exception as e:
            logger.error(f"Stripe session creation failed: {str(e)}")
            return Response(
                {'error': 'Payment session creation failed'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _create_premium_session(self, request):
        """Create checkout session for premium subscription."""
        try:
            tutor_profile = request.user.tutor_profile
        except TutorProfile.DoesNotExist:
            return Response(
                {'error': 'Tutor profile not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
        if tutor_profile.is_premium:
            return Response(
                {'error': 'Already have premium subscription'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Create Stripe checkout session for premium subscription
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'rub',
                    'recurring': {
                        'interval': 'month',
                    },
                    'product_data': {
                        'name': 'Tutors Platform Premium',
                        'description': 'Премиум подписка для репетиторов',
                    },
                    'unit_amount': 99900,  # 999 рублей
                },
                'quantity': 1,
            }],
            metadata={
                'type': 'premium',
                'user_id': request.user.id,
                'tutor_profile_id': tutor_profile.id,
            },
            mode='subscription',
            success_url=request.build_absolute_uri('/premium/success/'),
            cancel_url=request.build_absolute_uri('/premium/cancel/'),
        )
        
        return Response({
            'checkout_url': checkout_session.url,
            'session_id': checkout_session.id,
        })
    
    def _create_booking_session(self, request):
        """Create checkout session for booking payment."""
        booking_id = request.data.get('booking_id')
        if not booking_id:
            return Response(
                {'error': 'booking_id is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            booking = Booking.objects.get(id=booking_id, application__order__student=request.user)
        except Booking.DoesNotExist:
            return Response(
                {'error': 'Booking not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
        if booking.status != 'pending':
            return Response(
                {'error': 'Booking is not pending payment'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Create Stripe checkout session for booking
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'rub',
                    'product_data': {
                        'name': f'Занятие с {booking.tutor.user.get_full_name()}',
                        'description': booking.application.order.title,
                    },
                    'unit_amount': int(booking.total_amount * 100),  # Convert to kopecks
                },
                'quantity': 1,
            }],
            metadata={
                'type': 'booking',
                'booking_id': booking.id,
                'user_id': request.user.id,
            },
            mode='payment',
            success_url=request.build_absolute_uri(f'/booking/{booking.id}/success/'),
            cancel_url=request.build_absolute_uri(f'/booking/{booking.id}/cancel/'),
        )
        
        # Update booking with session info
        booking.stripe_session_id = checkout_session.id
        booking.save()
        
        return Response({
            'checkout_url': checkout_session.url,
            'session_id': checkout_session.id,
        })


@method_decorator(csrf_exempt, name='dispatch')
@require_POST
def stripe_webhook(request):
    """
    Handle Stripe webhooks for payment processing with idempotency.
    """
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
    endpoint_secret = settings.STRIPE_WEBHOOK_SECRET
    
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, endpoint_secret
        )
    except ValueError:
        logger.error("Invalid payload in Stripe webhook")
        return HttpResponseBadRequest("Invalid payload")
    except stripe.error.SignatureVerificationError:
        logger.error("Invalid signature in Stripe webhook")
        return HttpResponseBadRequest("Invalid signature")
    
    event_id = event['id']
    event_type = event['type']
    
    # Check for idempotency - if we've already processed this event, return success
    with transaction.atomic():
        webhook_event, created = StripeWebhookEvent.objects.get_or_create(
            stripe_event_id=event_id,
            defaults={'event_type': event_type}
        )
        
        if not created:
            logger.info(f"Webhook event {event_id} already processed, skipping")
            return HttpResponse(status=200)
    
    # Handle the event
    try:
        if event_type == 'checkout.session.completed':
            _handle_checkout_completed(event['data']['object'])
        elif event_type == 'invoice.payment_succeeded':
            _handle_subscription_payment(event['data']['object'])
        elif event_type == 'customer.subscription.deleted':
            _handle_subscription_cancelled(event['data']['object'])
        else:
            logger.info(f"Unhandled Stripe event type: {event_type}")
            
    except Exception as e:
        logger.error(f"Error handling Stripe webhook {event_id}: {str(e)}")
        # Delete the webhook event record so it can be retried
        StripeWebhookEvent.objects.filter(stripe_event_id=event_id).delete()
        return HttpResponseBadRequest("Webhook handling failed")
    
    return HttpResponse(status=200)


def _handle_checkout_completed(session):
    """Handle completed checkout session."""
    metadata = session.get('metadata', {})
    payment_type = metadata.get('type')
    
    if payment_type == 'premium':
        _activate_premium_subscription(session, metadata)
    elif payment_type == 'booking':
        _confirm_booking_payment(session, metadata)


def _activate_premium_subscription(session, metadata):
    """Activate premium subscription for tutor."""
    try:
        tutor_profile_id = metadata.get('tutor_profile_id')
        tutor_profile = TutorProfile.objects.get(id=tutor_profile_id)
        
        # Save Stripe customer ID for future subscription management
        customer_id = session.get('customer')
        if customer_id:
            tutor_profile.stripe_customer_id = customer_id
        
        # Activate premium for 1 month
        tutor_profile.is_premium = True
        tutor_profile.premium_expires_at = timezone.now() + timedelta(days=30)
        tutor_profile.save()
        
        logger.info(f"Premium activated for tutor {tutor_profile.id} with customer_id {customer_id}")
        
    except TutorProfile.DoesNotExist:
        logger.error(f"TutorProfile not found: {metadata.get('tutor_profile_id')}")


def _confirm_booking_payment(session, metadata):
    """Confirm booking payment."""
    try:
        booking_id = metadata.get('booking_id')
        booking = Booking.objects.get(id=booking_id)
        
        # Update booking status and payment info
        booking.status = 'confirmed'
        booking.stripe_payment_intent_id = session.get('payment_intent')
        booking.save()
        
        logger.info(f"Booking {booking.id} payment confirmed")
        
    except Booking.DoesNotExist:
        logger.error(f"Booking not found: {metadata.get('booking_id')}")


def _handle_subscription_payment(invoice):
    """Handle successful subscription payment (renewal)."""
    try:
        customer_id = invoice.get('customer')
        
        # Find tutor by Stripe customer ID and extend premium
        tutor_profile = TutorProfile.objects.filter(stripe_customer_id=customer_id).first()
        if tutor_profile:
            # Extend premium subscription by 30 days from current expiry or now
            current_expiry = tutor_profile.premium_expires_at or timezone.now()
            if current_expiry < timezone.now():
                current_expiry = timezone.now()
            
            tutor_profile.premium_expires_at = current_expiry + timedelta(days=30)
            tutor_profile.is_premium = True
            tutor_profile.save()
            
            logger.info(f"Premium subscription extended for tutor {tutor_profile.user.username} until {tutor_profile.premium_expires_at}")
        else:
            logger.error(f"No tutor found with customer_id {customer_id}")
        
    except Exception as e:
        logger.error(f"Error handling subscription payment: {str(e)}")


def _handle_subscription_cancelled(subscription):
    """Handle cancelled subscription."""
    try:
        customer_id = subscription.get('customer')
        
        # Find tutor by Stripe customer ID and deactivate premium
        tutor_profile = TutorProfile.objects.filter(stripe_customer_id=customer_id).first()
        if tutor_profile:
            tutor_profile.is_premium = False
            # Keep the expiry date for records but mark as not premium
            tutor_profile.save()
            
            logger.info(f"Premium subscription cancelled for tutor {tutor_profile.user.username}")
        else:
            logger.error(f"No tutor found with customer_id {customer_id}")
        
    except Exception as e:
        logger.error(f"Error handling subscription cancellation: {str(e)}")