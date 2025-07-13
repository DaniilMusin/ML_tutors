from django.db import models
from django.contrib.auth import get_user_model
from apps.tutors.models import TutorProfile, Subject

User = get_user_model()


class Order(models.Model):
    """
    Order created by student looking for a tutor.
    """
    STATUS_CHOICES = [
        ('open', 'Open'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]

    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='orders')
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='orders')
    
    title = models.CharField(max_length=200)
    description = models.TextField()
    goal_text = models.TextField(blank=True)
    
    # Budget and pricing
    budget_min = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    budget_max = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Schedule
    schedule_json = models.JSONField(default=dict, help_text="Preferred schedule")
    timezone = models.CharField(max_length=50, default='UTC')
    
    # Format preferences
    format_online = models.BooleanField(default=True)
    format_offline = models.BooleanField(default=False)
    
    # Location (for offline)
    city = models.CharField(max_length=100, blank=True)
    region = models.CharField(max_length=100, blank=True)
    
    # Order status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')
    
    # Meta fields
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'orders'
        verbose_name = 'Order'
        verbose_name_plural = 'Orders'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} - {self.student.username}"

    @property
    def applications_count(self):
        return self.applications.count()

    @property
    def budget_display(self):
        if self.budget_min == self.budget_max:
            return f"{self.budget_min} ₽/час"
        return f"{self.budget_min}-{self.budget_max} ₽/час"


class Application(models.Model):
    """
    Application from tutor to student's order.
    """
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='applications')
    tutor = models.ForeignKey(TutorProfile, on_delete=models.CASCADE, related_name='applications')
    
    # Tutor's proposal
    price = models.DecimalField(max_digits=10, decimal_places=2)
    message = models.TextField()
    
    # Selection
    is_chosen = models.BooleanField(default=False)
    
    # Meta fields
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'applications'
        verbose_name = 'Application'
        verbose_name_plural = 'Applications'
        unique_together = ['order', 'tutor']
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.tutor.user.username} -> {self.order.title}"


class Booking(models.Model):
    """
    Booking represents a confirmed tutoring session.
    """
    STATUS_CHOICES = [
        ('pending', 'Pending Payment'),
        ('confirmed', 'Confirmed'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('refunded', 'Refunded'),
    ]

    application = models.OneToOneField(Application, on_delete=models.CASCADE, related_name='booking')
    
    # Payment details
    stripe_session_id = models.CharField(max_length=255, blank=True)
    stripe_payment_intent_id = models.CharField(max_length=255, blank=True)
    
    # Booking details
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    platform_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    tutor_amount = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Session details
    session_start = models.DateTimeField(null=True, blank=True)
    session_end = models.DateTimeField(null=True, blank=True)
    session_notes = models.TextField(blank=True)
    
    # Meta fields
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'bookings'
        verbose_name = 'Booking'
        verbose_name_plural = 'Bookings'
        ordering = ['-created_at']

    def __str__(self):
        return f"Booking #{self.id} - {self.application.order.title}"

    @property
    def student(self):
        return self.application.order.student

    @property
    def tutor(self):
        return self.application.tutor


class EmbeddingCache(models.Model):
    """
    Cache for OpenAI embeddings to avoid repeated API calls.
    """
    text = models.TextField()
    text_hash = models.CharField(max_length=64, unique=True)  # SHA256 hash
    vector = models.JSONField()  # Store as JSON array
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'embedding_cache'
        verbose_name = 'Embedding Cache'
        verbose_name_plural = 'Embedding Cache'

    def __str__(self):
        return f"Embedding cache for {self.text[:50]}..."