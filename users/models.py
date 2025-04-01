from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
from django.utils import timezone

class Itinerary(models.Model):
    INTEREST_CHOICES = [
        ('food', 'Food & Dining'),
        ('history', 'History & Culture'),
        ('nature', 'Nature & Outdoors'),
        ('adventure', 'Adventure & Sports'),
        ('arts', 'Arts & Museums'),
        ('shopping', 'Shopping & Markets'),
        ('nightlife', 'Nightlife & Entertainment'),
        ('relaxation', 'Relaxation & Wellness'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    destination = models.CharField(max_length=200)
    start_date = models.DateField()
    end_date = models.DateField()
    budget = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    interests = models.JSONField(default=list)  # Store multiple interests as a list
    number_of_people = models.PositiveIntegerField(default=1)
    preferred_pace = models.CharField(max_length=20, choices=[
        ('relaxed', 'Relaxed'),
        ('moderate', 'Moderate'),
        ('busy', 'Busy'),
    ], default='moderate')
    generated_plan = models.TextField(blank=True)  # Store the Gemini-generated itinerary
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = 'Itineraries'

    def __str__(self):
        return f"{self.destination} - {self.start_date} to {self.end_date}"

    @property
    def duration_days(self):
        return (self.end_date - self.start_date).days + 1

    @property
    def is_future_trip(self):
        return self.start_date > timezone.now().date()
