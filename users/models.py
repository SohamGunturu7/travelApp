from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.utils.timezone import now
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
                    activity_name = time_match.group(2).strip()
                    details = time_match.group(3).strip() if time_match.group(3) else ""
                    
                    # Initialize default values
                    location = None
                    coordinates = None
                    cost = ""
                    description = ""
                    
                    # Extract location if present
                    location_match = re.search(r'\[Location:\s*(.*?)\]', details)
                    if location_match:
                        location = location_match.group(1).strip()
                        details = re.sub(r'\[Location:.*?\]', '', details).strip()
                    
                    # Extract coordinates if present
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
                            pass
                        details = re.sub(r'\[Coordinates:.*?\]', '', details).strip()
                    
                    # Try to extract cost from the beginning of details (it should be just a number)
                    cost_match = re.match(r'^(\d+(?:\.\d+)?)\s*(?:-\s*(.*))?$', details)
                    if cost_match:
                        cost = cost_match.group(1)
                        if cost_match.group(2):
                            description = cost_match.group(2).strip()
                    else:
                        # If we don't find a clear cost at the beginning, check for cost in standard format
                        parts = details.split(' - ', 1)
                        first_part = parts[0].strip() if parts else ""
                        
                        # Extract number from the first part if it exists
                        number_match = re.match(r'^(\d+(?:\.\d+)?)(?:.*)?$', first_part)
                        if number_match:
                            cost = number_match.group(1)
                            if len(parts) > 1:
                                description = parts[1].strip()
                            else:
                                # If no clear description part, try to extract description from remaining text
                                remaining = re.sub(r'^\d+(?:\.\d+)?', '', first_part).strip()
                                if remaining:
                                    if remaining.startswith('-'):
                                        description = remaining[1:].strip()
                                    else:
                                        description = remaining
                        else:
                            # No numeric cost found
                            if parts and len(parts) > 1:
                                description = parts[1].strip()
                            else:
                                description = details
                    
                    # If we have a numeric-only or very short activity name, try to improve it
                    if activity_name and (activity_name.isdigit() or len(activity_name.split()) <= 1):
                        if description and len(description.split()) > 1:
                            # Use first part of description as activity name if it's better
                            better_name_match = re.match(r'^([^.,:;]+)(?:[.,:;]\s*)?(.*)$', description)
                            if better_name_match:
                                better_name = better_name_match.group(1).strip()
                                remaining_desc = better_name_match.group(2).strip()
                                if len(better_name.split()) > 1:
                                    activity_name = better_name
                                    description = remaining_desc
                    
                    # Clean up cost - ensure it's only a number
                    if cost:
                        cost = re.sub(r'[^\d.]', '', cost)
                        if not re.match(r'^\d+(?:\.\d+)?$', cost):
                            cost = ""
                    
                    # Final activity data
                    current_activities.append({
                        'time': time,
                        'activity': activity_name,
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
        # Clean up the activity title if it's too short
        if len(self.activity.split()) <= 1 and self.description:
            # Try to extract a better title from the description
            better_title_match = re.match(r'^([^.,:;]+)(?:[.,:;]\s*)?(.*)$', self.description)
            if better_title_match:
                better_title = better_title_match.group(1).strip()
                if len(better_title.split()) > 1:
                    self.activity = better_title
                    self.description = better_title_match.group(2).strip()
        
        # Clean cost - ensure it's only numeric
        if self.cost:
            # Remove any non-numeric characters (except decimal point)
            numeric_cost = re.sub(r'[^\d.]', '', self.cost)
            # Make sure it's a valid numeric value
            try:
                float(numeric_cost)
                self.cost = numeric_cost
            except ValueError:
                # If it's not a valid number, set it to empty
                self.cost = ''
        
        # Handle description with cost pattern (e.g., "20 - Donuts and coffee")
        if self.description:
            cost_match = re.match(r'^(\d+(?:\.\d+)?)\s*-\s*(.*)$', self.description)
            if cost_match and (not self.cost or self.cost == ''):
                try:
                    # Extract cost from description and move description text
                    numeric_cost = cost_match.group(1).strip()
                    float(numeric_cost)  # Validate it's a number
                    self.cost = numeric_cost
                    self.description = cost_match.group(2).strip()
                except (ValueError, IndexError):
                    pass
        
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

class PackingChecklist(models.Model):
    itinerary = models.OneToOneField(Itinerary, on_delete=models.CASCADE, related_name='packing_checklist')
    items = models.JSONField(default=list)  # Store packing items as a list of dictionaries

    def __str__(self):
        return f"Packing Checklist for {self.itinerary.destination}"

