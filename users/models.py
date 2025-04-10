from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
from django.utils import timezone
import re

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
        
    @property
    def days_itinerary(self):
        """Parse the generated plan into a structured day-by-day format"""
        if not self.generated_plan:
            return []
            
        days = []
        current_day = None
        current_activities = []
        
        for line in self.generated_plan.split('\n'):
            # Check for a new day header
            day_match = re.match(r'^Day\s+(\d+)\s*-?\s*(.*?)$', line.strip())
            
            if day_match:
                # Save the previous day if it exists
                if current_day is not None and current_activities:
                    days.append({
                        'day_number': current_day['day_number'],
                        'day_title': current_day['day_title'],
                        'activities': current_activities
                    })
                
                # Start a new day
                day_number = day_match.group(1)
                day_title = day_match.group(2).strip()
                current_day = {
                    'day_number': day_number,
                    'day_title': day_title
                }
                current_activities = []
            elif current_day is not None:
                # Check for activity lines (usually start with a time)
                time_match = re.match(r'^(\d{1,2}:\d{2})\s*-\s*(.*?)(?:\s*-\s*(.*))?$', line.strip())
                
                if time_match:
                    time = time_match.group(1)
                    activity = time_match.group(2).strip()
                    details = time_match.group(3).strip() if time_match.group(3) else ""
                    
                    # Check if details contain cost and description
                    cost_details = details.split(' - ', 1) if ' - ' in details else [details, ""]
                    cost = cost_details[0] if len(cost_details) > 0 else ""
                    description = cost_details[1] if len(cost_details) > 1 else ""
                    
                    current_activities.append({
                        'time': time,
                        'activity': activity,
                        'cost': cost,
                        'description': description
                    })
                elif line.strip() and current_activities:
                    # Append to the previous activity's description if it's a continuation
                    current_activities[-1]['description'] += " " + line.strip()
        
        # Add the last day
        if current_day is not None and current_activities:
            days.append({
                'day_number': current_day['day_number'],
                'day_title': current_day['day_title'],
                'activities': current_activities
            })
            
        return days

class Activity(models.Model):
    itinerary = models.ForeignKey(Itinerary, on_delete=models.CASCADE, related_name='activities')
    day_number = models.PositiveIntegerField()
    time = models.CharField(max_length=10)
    activity = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    cost = models.CharField(max_length=50, blank=True)
    order = models.PositiveIntegerField()
    location = models.CharField(max_length=100, blank=True, null=True)  # Store coordinates as "longitude,latitude"

    class Meta:
        ordering = ['day_number', 'order', 'time']
        verbose_name_plural = 'Activities'

    def __str__(self):
        return f"Day {self.day_number} - {self.time} - {self.activity}"
