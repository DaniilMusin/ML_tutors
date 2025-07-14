from django.db import models
from django.utils import timezone


class StripeWebhookEvent(models.Model):
    """
    Model to track processed Stripe webhook events for idempotency.
    """
    stripe_event_id = models.CharField(max_length=255, unique=True, db_index=True)
    event_type = models.CharField(max_length=100)
    processed_at = models.DateTimeField(default=timezone.now)
    
    class Meta:
        db_table = 'payments_stripe_webhook_events'
        verbose_name = 'Stripe Webhook Event'
        verbose_name_plural = 'Stripe Webhook Events'
    
    def __str__(self):
        return f"{self.event_type} - {self.stripe_event_id}"


class Payment(models.Model):
    """
    Model to track payments and subscriptions.
    """
    stripe_payment_intent_id = models.CharField(max_length=255, unique=True, null=True, blank=True)
    stripe_session_id = models.CharField(max_length=255, unique=True, null=True, blank=True)
    stripe_customer_id = models.CharField(max_length=255, null=True, blank=True)
    
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default='RUB')
    
    payment_type = models.CharField(max_length=20, choices=[
        ('premium', 'Premium Subscription'),
        ('booking', 'Booking Payment'),
    ])
    
    status = models.CharField(max_length=20, choices=[
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
    ], default='pending')
    
    user = models.ForeignKey('users.User', on_delete=models.CASCADE, related_name='payments')
    
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'payments_payment'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.payment_type} - {self.amount} {self.currency} - {self.status}"