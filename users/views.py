from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django import forms
from .forms import UserRegisterForm, ItineraryForm, UserUpdateForm, PackingChecklistForm
from django.urls import reverse_lazy
from .models import Itinerary, Activity, PackingChecklist
import google.generativeai as genai
import json
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.db import models
from django.conf import settings
import requests
from django.views.decorators.http import require_POST
from django.utils.timezone import now
from datetime import datetime, timedelta

# Configure Gemini API
# probably don't commit an api key to a github
genai.configure(api_key='AIzaSyDCJW588azq9bd0cTEH9uoYroc7MWoC8h4')


def list_available_models():
    try:
        # List all available models
        for m in genai.list_models():
            print(m.name, m.supported_generation_methods)
    except Exception as e:
        print(f"Error listing models: {str(e)}")


def register(request):
    if request.method == 'POST':
        form = UserRegisterForm(request.POST)
        if form.is_valid():
            form.save()
            username = form.cleaned_data.get('username')
            messages.success(
                request, f'Account created for {username}! You can now log in')
            return redirect('login')
    else:
        form = UserRegisterForm()
    return render(request, 'users/register.html', {'form': form})


def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            return redirect('home')
        else:
            messages.error(request, 'Invalid username or password.')

    return render(request, 'users/login.html')


def logout_view(request):
    logout(request)
    messages.info(request, 'You have been logged out.')
    return redirect('login')


@login_required
def home(request):
    itineraries = Itinerary.objects.filter(
        user=request.user).order_by('-created_at')
    return render(request, 'users/home.html', {'itineraries': itineraries})


@login_required
def delete_account(request):
    if request.method == 'POST':
        user = request.user
        logout(request)
        user.delete()
        return redirect('home')
    return render(request, 'users/delete_account_confirm.html')


@login_required
def update_profile(request):
    if request.method == 'POST':
        form = UserUpdateForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request,
                             "Your profile has been successfully updated!")
            return redirect('home')
    else:
        form = UserUpdateForm(instance=request.user)
    return render(request, 'users/update_profile.html', {'form': form})


@login_required
def create_itinerary(request):
    if request.method == 'POST':
        form = ItineraryForm(request.POST)
        if form.is_valid():
            itinerary = form.save(commit=False)
            itinerary.user = request.user
            itinerary.save()

            # Generate itinerary using Gemini
            try:
                # Configure the model with maximum possible tokens
                generation_config = {
                    "temperature": 0.9,
                    "top_p": 1,
                    "top_k": 1,
                    "max_output_tokens": 30000,  # Maximum allowed tokens
                }

                # Create the model
                model = genai.GenerativeModel(
                    model_name="models/gemini-1.5-pro",
                    generation_config=generation_config)

                # For longer trips, break into chunks of 5 days each
                total_days = itinerary.duration_days
                chunk_size = 5
                num_chunks = (total_days + chunk_size - 1) // chunk_size
                full_itinerary = []

                for chunk in range(num_chunks):
                    start_day = chunk * chunk_size + 1
                    end_day = min((chunk + 1) * chunk_size, total_days)

                    chunk_prompt = f"""Create a detailed daily travel itinerary for days {start_day} to {end_day} of a {total_days}-day trip to {itinerary.destination}.

CRITICAL REQUIREMENT: You MUST generate EXACTLY {end_day - start_day + 1} days of detailed itinerary, from Day {start_day} to Day {end_day}. Any summarizing or skipping of days will make the response unusable.

Trip Details:
- Total Trip Duration: {total_days} days
- Current Section: Days {start_day} to {end_day}
- Dates: {itinerary.start_date} to {itinerary.end_date}
- Daily Budget: ${itinerary.budget / total_days:.2f}
- Number of people: {itinerary.number_of_people}
- Interests: {', '.join(itinerary.interests)}
- Preferred pace: {itinerary.preferred_pace}

ABSOLUTELY REQUIRED:
1. Generate EXACTLY {end_day - start_day + 1} individual day schedules
2. Each day MUST be fully detailed from morning to night
3. NO SUMMARIZING or phrases like "similar to previous days"
4. NO SKIPPING any days or activities
5. If you run out of unique activities, create variations or revisit popular spots at different times
6. The response MUST contain "Day {start_day}" through "Day {end_day}" with no gaps
7. DO NOT include dollar signs ($) in any cost values - write numbers only
8. For each activity, provide the exact location name and address in the format: [Location: Place Name, Address]
9. For each location, provide the exact coordinates in the format: [Coordinates: latitude, longitude]

Format each day EXACTLY as follows:

Day [X]
[Time] - [Activity] - [Cost] - [Details] [Location: Place Name, Address] [Coordinates: latitude, longitude]
Example of REQUIRED format:
Day 1
07:00 - Breakfast at Morning Cafe - 15 - Local specialties [Location: Morning Cafe, 123 Main St, City] [Coordinates: 40.7128, -74.0060]
08:30 - Transit to Location - 3 - Bus details [Location: Main Bus Station, 456 Transit Ave, City] [Coordinates: 40.7130, -74.0062]
09:00 - Activity - 25 - Full details [Location: Museum Name, 789 Museum St, City] [Coordinates: 40.7132, -74.0064]
(... complete day schedule ...)
22:00 - Return to Hotel - 10 - Transport details [Location: Hotel Name, 101 Hotel Blvd, City] [Coordinates: 40.7134, -74.0066]

Required for EACH day:
- Breakfast (07:00-08:30)
- Morning activity
- Mid-morning break
- Lunch (12:00-13:30)
- Afternoon activities
- Evening activity
- Dinner (18:00-20:00)
- Return to hotel
- ALL transit times
- ALL costs (numbers only, NO dollar signs)
- ALL locations with exact addresses
- ALL coordinates for each location

CRITICAL: Your response must contain EXACTLY {end_day - start_day + 1} days of detailed schedules with exact locations, addresses, and coordinates."""

                    response = model.generate_content(chunk_prompt)
                    if response.text:
                        full_itinerary.append(response.text)
                    else:
                        raise Exception(
                            f"No response generated for days {start_day}-{end_day}"
                        )

                # Combine all chunks into final itinerary
                complete_itinerary = "\n\n".join(full_itinerary)

                # Verify all days are present
                expected_days = set(range(1, total_days + 1))
                found_days = set()
                for line in complete_itinerary.split('\n'):
                    if line.startswith('Day '):
                        try:
                            day_num = int(line.split(' ')[1])
                            found_days.add(day_num)
                        except:
                            continue

                missing_days = expected_days - found_days
                if missing_days:
                    raise Exception(
                        f"Missing days in generated itinerary: {missing_days}")

                itinerary.generated_plan = complete_itinerary
                itinerary.save()
                return redirect('view_itinerary', pk=itinerary.pk)

            except Exception as e:
                messages.error(request,
                               f'Error generating itinerary: {str(e)}')
                return redirect('home')
    else:
        form = ItineraryForm()

    return render(request, 'users/create_itinerary.html', {'form': form})


@login_required
def view_itinerary(request, pk):
    itinerary = get_object_or_404(Itinerary, pk=pk, user=request.user)

    # Get all activities for this itinerary
    activities = Activity.objects.filter(itinerary=itinerary).order_by(
        'day_number', 'time')

    # Group activities by day
    days = {}
    for activity in activities:
        if activity.day_number not in days:
            days[activity.day_number] = {
                'day_number': activity.day_number,
                'activities': []
            }
        days[activity.day_number]['activities'].append(activity)

    # Convert to sorted list for template
    days_list = [days[day_num] for day_num in sorted(days.keys())]

    # If no activities exist yet and we have a generated plan, create initial activities
    if not activities.exists() and itinerary.generated_plan:
        generated_days = itinerary.days_itinerary
        for day in generated_days:
            day_number = int(day['day_number'])
            for order, activity_data in enumerate(day['activities'], 1):
                activity = Activity.objects.create(
                    itinerary=itinerary,
                    day_number=day_number,
                    time=activity_data['time'],
                    activity=activity_data['activity'],
                    description=activity_data.get('description', ''),
                    cost=activity_data.get('cost', ''),
                    location=activity_data.get('location', ''),
                    order=order)

                # Save coordinates if available
                if activity_data.get('coordinates'):
                    activity.latitude = activity_data['coordinates'][
                        'latitude']
                    activity.longitude = activity_data['coordinates'][
                        'longitude']
                    activity.save()

                # If we have a location but no coordinates, try to geocode it
                elif activity.location:
                    try:
                        # Use Mapbox Geocoding API to get coordinates
                        geocode_url = f"https://api.mapbox.com/geocoding/v5/mapbox.places/{activity.location}.json"
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
                                activity.longitude = coordinates[0]
                                activity.latitude = coordinates[1]
                                activity.save()
                    except Exception as e:
                        print(f"Error geocoding location: {e}")
        # Refresh the activities after creating them
        return redirect('view_itinerary', pk=pk)

    return render(
        request, 'users/view_itinerary.html', {
            'itinerary': itinerary,
            'days': days_list,
            'mapbox_access_token': settings.MAPBOX_ACCESS_TOKEN
        })


@login_required
def get_tips_safety(request, pk):
    itinerary = get_object_or_404(Itinerary, pk=pk, user=request.user)
    try:
        generation_config = {
            "temperature": 0.7,
            "top_p": 1,
            "top_k": 1,
            "max_output_tokens": 1500,  # Adjust token count as needed
        }
        model = genai.GenerativeModel(model_name="models/gemini-1.5-pro",
                                      generation_config=generation_config)

        # Build a prompt that instructs for structured JSON output with icons
        prompt = f"""
You are a travel expert. Based on the following trip details, provide general travel tips and safety recommendations in valid JSON format. Use appropriate Font Awesome icon classes for each tip item.
Trip Details:
- Destination: {itinerary.destination}
- Duration: {itinerary.duration_days} days
- Dates: {itinerary.start_date} to {itinerary.end_date}
- Daily Budget (numbers only): {itinerary.budget / itinerary.duration_days:.2f}
- Number of People: {itinerary.number_of_people}
- Interests: {', '.join(itinerary.interests)}
- Preferred Pace: {itinerary.preferred_pace}

Please respond in valid JSON with the following structure exactly:
{{
  "general_travel_tips": [
    {{
      "icon": "string (e.g., 'fa-suitcase', 'fa-plane')",
      "title": "string",
      "description": "string"
    }}
    // provide at least 3 items
  ],
  "safety_recommendations": [
    {{
      "icon": "string (e.g., 'fa-shield-alt', 'fa-exclamation-triangle')",
      "title": "string",
      "description": "string"
    }}
    // provide at least 3 items
  ]
}}

Make sure the JSON is valid and contains no additional text.
"""

        response = model.generate_content(prompt)
        if not response.text:
            raise ValueError("No response received from the AI model")

        # Attempt to parse the generated response as JSON
        try:
            tips_data = json.loads(response.text)
        except json.JSONDecodeError:
            # Sometimes the model returns extra text; try to extract the JSON using a regex
            import re
            json_match = re.search(r'\{[\s\S]*\}', response.text)
            if json_match:
                tips_data = json.loads(json_match.group(0))
            else:
                raise ValueError("The AI response did not contain valid JSON.")

        # Validate basic structure
        if (not isinstance(tips_data, dict)
                or "general_travel_tips" not in tips_data
                or "safety_recommendations" not in tips_data):
            raise ValueError("Missing required sections in response JSON.")

        return JsonResponse(tips_data)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_http_methods(["POST"])
def add_activity(request, pk):
    try:
        itinerary = get_object_or_404(Itinerary, pk=pk, user=request.user)
        data = json.loads(request.body)

        # Validate required fields
        if not all(key in data for key in ['day_number', 'time', 'activity']):
            return JsonResponse({'error': 'Missing required fields'},
                                status=400)

        # Convert input time to a comparable format (for ordering)
        input_time = data['time']

        # Get all activities for the day and determine the correct order
        day_activities = Activity.objects.filter(
            itinerary=itinerary,
            day_number=data['day_number']).order_by('time')

        # Determine the correct order based on time
        order = 1
        if day_activities.exists():
            # Insert at the right position based on time comparison
            inserted = False
            for i, existing_activity in enumerate(day_activities):
                if input_time < existing_activity.time:
                    # Insert before this activity
                    order = i + 1
                    inserted = True
                    break

            if not inserted:
                # New activity has the latest time, append at the end
                order = day_activities.count() + 1

            # Update the order of all activities that come after
            Activity.objects.filter(
                itinerary=itinerary,
                day_number=data['day_number'],
                order__gte=order).update(order=models.F('order') + 1)

        activity = Activity.objects.create(itinerary=itinerary,
                                           day_number=data['day_number'],
                                           time=data['time'],
                                           activity=data['activity'],
                                           description=data.get(
                                               'description', ''),
                                           cost=data.get('cost', ''),
                                           location=data.get('location', ''),
                                           order=order)

        return JsonResponse({
            'id': activity.id,
            'time': activity.time,
            'activity': activity.activity,
            'description': activity.description,
            'cost': activity.cost
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


@login_required
@require_http_methods(["POST"])
def edit_activity(request, pk, activity_id):
    try:
        activity = get_object_or_404(Activity,
                                     id=activity_id,
                                     itinerary__pk=pk,
                                     itinerary__user=request.user)
        data = json.loads(request.body)

        # Check if time has changed
        old_time = activity.time
        new_time = data['time']

        if old_time != new_time:
            # Time has changed, we need to reorder activities

            # First, remove this activity from the order
            Activity.objects.filter(
                itinerary=activity.itinerary,
                day_number=activity.day_number,
                order__gt=activity.order).update(order=models.F('order') - 1)

            # Find the new position
            day_activities = Activity.objects.filter(
                itinerary=activity.itinerary,
                day_number=activity.day_number).exclude(
                    id=activity.id).order_by('time')

            new_order = 1
            if day_activities.exists():
                inserted = False
                for i, existing_activity in enumerate(day_activities):
                    if new_time < existing_activity.time:
                        new_order = i + 1
                        inserted = True
                        break

                if not inserted:
                    # Activity has the latest time, append at the end
                    new_order = day_activities.count() + 1

                # Update the order of all activities that come after
                Activity.objects.filter(
                    itinerary=activity.itinerary,
                    day_number=activity.day_number,
                    order__gte=new_order).update(order=models.F('order') + 1)

            activity.order = new_order

        # Update the activity fields
        activity.time = new_time
        activity.activity = data['activity']
        activity.description = data.get('description', '')
        activity.cost = data.get('cost', '')
        activity.location = data.get('location', '')
        activity.save()

        return JsonResponse({
            'id': activity.id,
            'time': activity.time,
            'activity': activity.activity,
            'description': activity.description,
            'cost': activity.cost
        })
    except Activity.DoesNotExist:
        return JsonResponse({'error': 'Activity not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


@login_required
@require_http_methods(["DELETE"])
def delete_activity(request, pk, activity_id):
    try:
        activity = get_object_or_404(Activity,
                                     id=activity_id,
                                     itinerary__pk=pk,
                                     itinerary__user=request.user)
        activity.delete()
        return JsonResponse({'status': 'success'})
    except Activity.DoesNotExist:
        return JsonResponse({'error': 'Activity not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


@login_required
def get_recommendations(request, pk):
    itinerary = get_object_or_404(Itinerary, pk=pk, user=request.user)

    try:
        # Configure the model
        generation_config = {
            "temperature": 0.9,
            "top_p": 1,
            "top_k": 1,
            "max_output_tokens": 2048,
        }

        # Configure Gemini API
        genai.configure(api_key='AIzaSyDCJW588azq9bd0cTEH9uoYroc7MWoC8h4')

        model = genai.GenerativeModel(model_name="models/gemini-1.5-pro",
                                      generation_config=generation_config)

        # Create prompt for recommendations
        prompt = f"""You are a travel expert. Given the following travel details, recommend real and accurate restaurants and hotels that fit within the budget. Make sure to keep the recommendations realistic and within the specified budget constraints.

Destination: {itinerary.destination}
Total Budget: ${itinerary.budget} for {itinerary.duration_days} days
Daily Budget: ${float(itinerary.budget) / itinerary.duration_days:.2f}
Number of People: {itinerary.number_of_people}
Duration: {itinerary.duration_days} days
Interests: {', '.join(itinerary.interests)}

Please provide recommendations in the following JSON format exactly:
{{
    "restaurants": [
        {{
            "name": "string",
            "cuisine": "string",
            "price_range": "string (in $ format)",
            "description": "string",
            "match_reason": "string"
        }}
    ],
    "hotels": [
        {{
            "name": "string",
            "price_per_night": "string (in $ format)",
            "location": "string",
            "amenities": ["string"],
            "match_reason": "string"
        }}
    ]
}}

Important:
- Provide 5 restaurant recommendations
- Provide 3 hotel recommendations
- Ensure prices are realistic and within budget
- Focus on options that match the user's interests
- Only return valid JSON format
"""

        # Generate recommendations
        response = model.generate_content(prompt)

        if not response.text:
            raise ValueError("No response received from the AI model")

        try:
            # Try to parse the response as JSON
            recommendations = json.loads(response.text)

            # Validate the structure
            if not isinstance(recommendations, dict):
                raise ValueError("Response is not a dictionary")
            if "restaurants" not in recommendations or "hotels" not in recommendations:
                raise ValueError("Missing required sections in response")
            if not isinstance(recommendations["restaurants"],
                              list) or not isinstance(
                                  recommendations["hotels"], list):
                raise ValueError(
                    "Restaurants or hotels are not in list format")

            return JsonResponse(recommendations)

        except json.JSONDecodeError as e:
            # If JSON parsing fails, try to extract JSON from the response
            # Sometimes the AI might include additional text before or after the JSON
            import re
            json_match = re.search(r'\{[\s\S]*\}', response.text)
            if json_match:
                try:
                    recommendations = json.loads(json_match.group(0))
                    return JsonResponse(recommendations)
                except json.JSONDecodeError:
                    raise ValueError(
                        f"Could not parse JSON from response: {response.text[:200]}"
                    )
            else:
                raise ValueError(
                    f"Invalid JSON format in response: {response.text[:200]}")

    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"Error generating recommendations: {str(e)}\n{error_details}")
        return JsonResponse(
            {'error': f'Error generating recommendations: {str(e)}'},
            status=500)


class LoggedInPasswordResetView(auth_views.PasswordResetView):
    success_url = reverse_lazy('password_reset_done')

    def get_initial(self):
        initial = super().get_initial()
        return initial

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        return form


@login_required
def map_view(request):
    itinerary_id = request.GET.get('itinerary_id')
    day_number = request.GET.get('day')

    context = {
        'mapbox_access_token': settings.MAPBOX_ACCESS_TOKEN,
        'itinerary_id': itinerary_id,
        'day_number': day_number,
        'destination': {
            'name': 'Unknown',
            'coordinates': {
                'lng': 0,
                'lat': 0
            }
        },
        'activities': []
    }

    if itinerary_id and day_number:
        try:
            itinerary = Itinerary.objects.get(id=itinerary_id,
                                              user=request.user)
            activities = Activity.objects.filter(
                itinerary=itinerary, day_number=day_number).order_by('time')

            # Get destination coordinates using Mapbox Geocoding API
            geocode_url = f"https://api.mapbox.com/geocoding/v5/mapbox.places/{itinerary.destination}.json"
            params = {
                'access_token': settings.MAPBOX_ACCESS_TOKEN,
                'types': 'place',
                'limit': 1
            }

            response = requests.get(geocode_url, params=params)
            if response.status_code == 200:
                data = response.json()
                if data['features']:
                    coordinates = data['features'][0]['center']
                    context['destination'] = {
                        'name': itinerary.destination,
                        'coordinates': {
                            'lng': coordinates[0],
                            'lat': coordinates[1]
                        }
                    }
                else:
                    context['destination'] = {
                        'name': itinerary.destination,
                        'coordinates': {
                            'lng': 0,
                            'lat': 0
                        }
                    }
            else:
                context['destination'] = {
                    'name': itinerary.destination,
                    'coordinates': {
                        'lng': 0,
                        'lat': 0
                    }
                }

            # Process activities and geocode their locations if needed
            processed_activities = []
            for activity in activities:
                activity_data = {
                    'id': activity.id,
                    'time': activity.time,
                    'activity': activity.activity,
                    'description': activity.description,
                    'location':
                    'null'  # Use string 'null' instead of Python None
                }

                # If activity has coordinates, use them
                if activity.latitude and activity.longitude:
                    activity_data[
                        'location'] = f"{activity.longitude},{activity.latitude}"
                # If activity has a location string, try to geocode it
                elif activity.location:
                    try:
                        coords = activity.location.split(',')
                        if len(coords) == 2:
                            activity_data['location'] = activity.location
                    except:
                        pass

                # If still no location, try to geocode the activity name
                if activity_data['location'] == 'null':
                    search_query = f"{activity.activity}, {itinerary.destination}"
                    geocode_url = f"https://api.mapbox.com/geocoding/v5/mapbox.places/{search_query}.json"
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
                            activity_data[
                                'location'] = f"{coordinates[0]},{coordinates[1]}"

                processed_activities.append(activity_data)

            context['activities'] = processed_activities

        except Itinerary.DoesNotExist:
            pass
        except Exception as e:
            print(f"Error in map_view: {str(e)}")

    return render(request, 'map.html', context)


@login_required
def get_hidden_gems(request, pk):
    itinerary = get_object_or_404(Itinerary, pk=pk, user=request.user)

    try:
        # Configure Gemini API
        genai.configure(api_key='AIzaSyDCJW588azq9bd0cTEH9uoYroc7MWoC8h4')

        generation_config = {
            "temperature": 0.9,
            "top_p": 1,
            "top_k": 1,
            "max_output_tokens": 2048,
        }

        model = genai.GenerativeModel(model_name="models/gemini-1.5-pro",
                                      generation_config=generation_config)

        prompt = f"""As a local expert in {itinerary.destination}, recommend 5 hidden gems and unique experiences that most tourists miss. Consider these user interests: {', '.join(itinerary.interests)}.

Focus on:
- Local favorites
- Off-the-beaten-path locations
- Authentic cultural experiences
- Unique activities matching user interests
- Places with historical or cultural significance
- Local markets or artisan shops
- Hidden viewpoints or photo spots
- Family-run establishments

Return the response in this exact JSON format:
{{
    "hidden_gems": [
        {{
            "name": "string",
            "category": "string (e.g., 'Local Market', 'Viewpoint', 'Cultural Site')",
            "description": "string",
            "best_time": "string",
            "insider_tips": "string",
            "why_special": "string",
            "match_interests": "string (explain how it matches user interests)",
            "estimated_cost": "string (in $ format)",
            "time_needed": "string"
        }}
    ]
}}

Ensure recommendations are:
- Genuinely local and unique
- Not typically found in standard tourist guides
- Accessible and safe
- Aligned with user interests: {', '.join(itinerary.interests)}
- Within reasonable budget considering total trip budget: ${itinerary.budget}
"""

        response = model.generate_content(prompt)

        if not response.text:
            raise ValueError("No response received from the AI model")

        try:
            recommendations = json.loads(response.text)
            return JsonResponse(recommendations)
        except json.JSONDecodeError:
            # Try to extract JSON if there's additional text
            import re
            json_match = re.search(r'\{[\s\S]*\}', response.text)
            if json_match:
                recommendations = json.loads(json_match.group(0))
                return JsonResponse(recommendations)
            else:
                raise ValueError("Invalid JSON format in response")

    except Exception as e:
        print(f"Error generating hidden gems: {str(e)}")
        return JsonResponse({'error': f'Error finding hidden gems: {str(e)}'},
                            status=500)


@login_required
def packing_checklist(request, pk):
    itinerary = get_object_or_404(Itinerary, pk=pk, user=request.user)

    if request.method == 'POST' and 'regenerate' in request.POST:
        try:
            # Configure Gemini API
            genai.configure(api_key='AIzaSyDCJW588azq9bd0cTEH9uoYroc7MWoC8h4')

            generation_config = {
                "temperature": 0.9,
                "top_p": 1,
                "top_k": 1,
                "max_output_tokens": 2048,
            }

            model = genai.GenerativeModel(model_name="models/gemini-1.5-pro",
                                          generation_config=generation_config)

            # Create prompt
            prompt = f"""Create a detailed packing list for {itinerary.duration_days} days in {itinerary.destination}.
            
            Format each section exactly like this:
            
            CLOTHING:
            - 5 t-shirts
            - 3 pairs of pants
            
            TOILETRIES:
            - Toothbrush and toothpaste
            - Shampoo and conditioner
            
            ELECTRONICS:
            - Phone charger
            - Camera
            
            DOCUMENTS:
            - Passport
            - Travel insurance
            
            Be specific about quantities and include items based on:
            - Duration: {itinerary.duration_days} days
            - Destination: {itinerary.destination}
            - Activities: {', '.join(itinerary.interests)}"""

            # Get response
            response = model.generate_content(prompt)
            print("Raw response:", response.text)  # Debug print

            # Process sections
            sections = {
                'CLOTHING': [],
                'TOILETRIES': [],
                'ELECTRONICS': [],
                'DOCUMENTS': []
            }

            current_section = None

            # Parse response
            for line in response.text.split('\n'):
                line = line.strip()
                if not line:
                    continue

                # Check for section headers
                if line.endswith(':'):
                    current_section = line.rstrip(':').upper()
                    continue

                # Add items to current section
                if current_section and line.startswith('-'):
                    item = line.lstrip('- ').strip()
                    if item and current_section in sections:
                        sections[current_section].append(item)

            print("Processed sections:", sections)  # Debug print

            # Save to database
            checklist, created = PackingChecklist.objects.get_or_create(
                itinerary=itinerary)
            checklist.items = sections
            checklist.save()

            messages.success(request,
                             "Packing checklist generated successfully!")

        except Exception as e:
            print(f"Error generating packing list: {str(e)}")  # Debug print
            messages.error(request, f"Error: {str(e)}")

        return redirect('packing_checklist', pk=pk)

    return render(request, 'users/packing_checklist.html',
                  {'itinerary': itinerary})


@login_required
@require_http_methods(["GET"])
def get_weather(request, pk):
    itinerary = get_object_or_404(Itinerary, pk=pk, user=request.user)
    
    try:
        # Configure Gemini API
        genai.configure(api_key='AIzaSyDCJW588azq9bd0cTEH9uoYroc7MWoC8h4')
        
        generation_config = {
            "temperature": 0.7,
            "top_p": 1,
            "top_k": 1,
            "max_output_tokens": 2048,
        }
        
        model = genai.GenerativeModel(model_name="models/gemini-1.5-pro",
                                     generation_config=generation_config)
        
        # Create prompt for weather forecast
        prompt = f"""As a weather expert, generate a 5-day weather forecast for {itinerary.destination} during the trip dates of {itinerary.start_date} to {itinerary.end_date}.
        
        Return the response in this exact JSON format:
        {{
            "forecast": [
                {{
                    "date": "string (e.g., 'Monday, March 25')",
                    "temperature": "number (in Celsius)",
                    "condition": "string (e.g., 'Partly cloudy')",
                    "humidity": "number (percentage)",
                    "wind_speed": "number (in km/h)",
                    "icon": "string (choose from: 'fa-sun', 'fa-cloud-sun', 'fa-cloud', 'fa-cloud-showers-heavy', 'fa-cloud-rain', 'fa-snowflake', 'fa-bolt', 'fa-smog')"
                }}
            ]
        }}
        
        Important:
        - Generate realistic weather data based on the destination's typical climate
        - Include typical temperature ranges for the season
        - Consider the destination's geographical location
        - Make the forecast realistic but varied
        - Choose appropriate weather icons based on the condition
        - Return only valid JSON format
        """
        
        response = model.generate_content(prompt)
        
        if not response.text:
            raise ValueError("No response received from the AI model")
        
        try:
            # Try to parse the response as JSON
            weather_data = json.loads(response.text)
            
            # Validate the structure
            if not isinstance(weather_data, dict) or "forecast" not in weather_data:
                raise ValueError("Invalid response format")
            
            return JsonResponse(weather_data)
            
        except json.JSONDecodeError:
            # Try to extract JSON if there's additional text
            import re
            json_match = re.search(r'\{[\s\S]*\}', response.text)
            if json_match:
                weather_data = json.loads(json_match.group(0))
                return JsonResponse(weather_data)
            else:
                raise ValueError("Invalid JSON format in response")
                
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

