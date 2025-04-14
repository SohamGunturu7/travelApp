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
            line = line.strip()
            if not line:
                continue

            day_match = re.match(r'^Day\s+(\d+)(?:\s*-\s*(.*?))?$', line)
            
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
                day_title = day_match.group(2).strip() if day_match.group(2) else ""
                current_day = {
                    'day_number': day_number,
                    'day_title': day_title
                }
                current_activities = []
            elif current_day is not None:
                # Check for activity lines (usually start with a time)
                time_match = re.match(r'^(\d{1,2}:\d{2})\s*-\s*(.*?)(?:\s*-\s*(.*))?$', line)
                
                if time_match:
                    time = time_match.group(1)
                    activity = time_match.group(2).strip()
                    details = time_match.group(3).strip() if time_match.group(3) else ""
                    
                # Extract location information if present
                    location = None
                    location_match = re.search(r'\[Location:\s*(.*?)\]', details)
                    if location_match:
                        location = location_match.group(1).strip()
                        # Remove location from details
                        details = re.sub(r'\[Location:.*?\]', '', details).strip()

                    # Extract coordinates if present
                    coordinates = None
                    coords_match = re.search(r'\[Coordinates:\s*([-\d.]+),\s*([-\d.]+)\]', details)
                    if coords_match:
                        try:
                            latitude = float(coords_match.group(1))
                            longitude = float(coords_match.group(2))
                            coordinates = {
                                'latitude': latitude,
                                'longitude': longitude
                            }
                        except ValueError:
                            coordinates = None
                        # Remove coordinates from details
                        details = re.sub(r'\[Coordinates:.*?\]', '', details).strip()

                    # Split details into cost and description
                    parts = details.split(' - ', 1)
                    cost = parts[0].strip() if parts else ""
                    description = parts[1].strip() if len(parts) > 1 else ""
                    
                    current_activities.append({
                        'time': time,
                        'activity': activity,
                        'cost': cost,
                        'description': description,
                        'location': location,
                        'coordinates': coordinates
                    })
                elif line and current_activities:
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
    location = models.CharField(max_length=200, blank=True, null=True)  # Human-readable address
    latitude = models.DecimalField(max_digits=9, decimal_places=6, blank=True, null=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, blank=True, null=True)  # Store coordinates as "longitude,latitude"


    class Meta:
        ordering = ['day_number', 'order', 'time']
        verbose_name_plural = 'Activities'

    def __str__(self):
        return f"Day {self.day_number} - {self.time} - {self.activity}"
    
    def save(self, *args, **kwargs):
            # If location is provided but coordinates aren't, try to geocode
            if self.location and not (self.latitude and self.longitude):
                try:
                    from django.conf import settings
                    import requests

                    # Use Mapbox Geocoding API to get coordinates
                    geocode_url = f"https://api.mapbox.com/geocoding/v5/mapbox.places/{self.location}.json"
                    params = {
                        'access_token': settings.MAPBOX_ACCESS_TOKEN,
                        'types': 'poi,address',
                        'limit': 1
                    }

                    response = requests.get(geocode_url, params=params)
                    if response.status_code == 200:
                        data = response.json()
                        if data['features']:
                            coordinates = data['features'][0]['center']
                            self.longitude = coordinates[0]
                            self.latitude = coordinates[1]
                except Exception as e:
                    print(f"Error geocoding location: {e}")

            super().save(*args, **kwargs)
