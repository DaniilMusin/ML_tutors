from django.db import models
from django.contrib.auth import get_user_model
from pgvector.django import VectorField
import json

User = get_user_model()


class TutorProfile(models.Model):
    """
    Tutor profile with additional information and vector embeddings.
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='tutor_profile')
    bio = models.TextField(blank=True)
    experience_years = models.PositiveIntegerField(default=0)
    hourly_rate = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    rating = models.DecimalField(max_digits=3, decimal_places=2, default=0)
    rating_count = models.PositiveIntegerField(default=0)
    
    # Premium subscription
    is_premium = models.BooleanField(default=False)
    premium_expires_at = models.DateTimeField(null=True, blank=True)
    stripe_customer_id = models.CharField(max_length=255, blank=True, null=True, 
                                         help_text="Stripe customer ID for subscription management")
    
    # Vector embedding for AI matching
    vector = VectorField(dimensions=1536, blank=True, null=True)
    
    # Availability
    availability = models.JSONField(default=dict, help_text="Weekly availability schedule")
    
    # Location
    city = models.CharField(max_length=100, blank=True)
    region = models.CharField(max_length=100, blank=True)
    
    # Verification
    is_verified = models.BooleanField(default=False)
    verification_documents = models.JSONField(default=list, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'tutor_profiles'
        verbose_name = 'Tutor Profile'
        verbose_name_plural = 'Tutor Profiles'

    def __str__(self):
        return f"{self.user.username} - {self.hourly_rate}/час"

    def add_rating(self, rating):
        """
        Add new rating and update average.

        Args:
            rating: Integer rating from 1 to 5

        Raises:
            ValueError: If rating is not in valid range
        """
        from decimal import Decimal
        from django.db import transaction

        # Validate rating range
        if not isinstance(rating, (int, float, Decimal)):
            raise ValueError("Rating must be a number")

        rating = int(rating)
        if rating < 1 or rating > 5:
            raise ValueError("Rating must be between 1 and 5")

        # Use atomic transaction to prevent race conditions
        with transaction.atomic():
            # Lock the row for update
            tutor = TutorProfile.objects.select_for_update().get(pk=self.pk)

            # Calculate new rating using Decimal for precision
            current_total = Decimal(str(tutor.rating)) * tutor.rating_count
            new_total = current_total + Decimal(str(rating))
            tutor.rating_count += 1
            tutor.rating = new_total / tutor.rating_count

            tutor.save(update_fields=['rating', 'rating_count'])

    @property
    def subjects_display(self):
        """Get subjects as comma-separated string."""
        return ', '.join([s.name for s in self.subjects.all()])


class Subject(models.Model):
    """
    Subject that tutors can teach.
    """
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    category = models.CharField(max_length=50, blank=True)
    icon = models.CharField(max_length=50, blank=True)
    
    tutors = models.ManyToManyField(TutorProfile, related_name='subjects', blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'subjects'
        verbose_name = 'Subject'
        verbose_name_plural = 'Subjects'

    def __str__(self):
        return self.name


class TutorReview(models.Model):
    """
    Review for tutor from student.
    """
    tutor = models.ForeignKey(TutorProfile, on_delete=models.CASCADE, related_name='reviews')
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='given_reviews')
    rating = models.PositiveIntegerField(choices=[(i, str(i)) for i in range(1, 6)])
    review_text = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'tutor_reviews'
        verbose_name = 'Tutor Review'
        verbose_name_plural = 'Tutor Reviews'
        unique_together = ['tutor', 'student']

    def __str__(self):
        return f"{self.student.username} -> {self.tutor.user.username}: {self.rating}/5"