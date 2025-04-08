from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from .forms import UserRegisterForm, ItineraryForm
from .models import Itinerary, Activity
import google.generativeai as genai
import json
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.db import models

# Configure Gemini API
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
            messages.success(request, f'Account created for {username}! You can now log in')
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
    itineraries = Itinerary.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'users/home.html', {'itineraries': itineraries})


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
                    generation_config=generation_config
                )

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

Format each day EXACTLY as follows:

Day [X] - [Full Date]
07:00 - [Activity] - [Cost] - [Details]
08:30 - [Next Activity] - [Cost] - [Details]
(Continue with FULL day schedule)
22:00 - Return to Hotel - [Cost] - [Transport Details]

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
- ALL costs

Example of REQUIRED format:
Day {start_day} - [Date]
07:00 - Breakfast at Morning Cafe - $15 - Local specialties
08:30 - Transit to Location - $3 - Bus details
09:00 - Activity - $25 - Full details
(... complete day schedule ...)
22:00 - Return to Hotel - $10 - Transport details

CRITICAL: Your response must contain EXACTLY {end_day - start_day + 1} days of detailed schedules."""

                    response = model.generate_content(chunk_prompt)
                    if response.text:
                        full_itinerary.append(response.text)
                    else:
                        raise Exception(f"No response generated for days {start_day}-{end_day}")

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
                    raise Exception(f"Missing days in generated itinerary: {missing_days}")

                itinerary.generated_plan = complete_itinerary
                itinerary.save()
                return redirect('view_itinerary', pk=itinerary.pk)
            
            except Exception as e:
                messages.error(request, f'Error generating itinerary: {str(e)}')
                return redirect('home')
    else:
        form = ItineraryForm()
    
    return render(request, 'users/create_itinerary.html', {'form': form})


@login_required
def view_itinerary(request, pk):
    itinerary = get_object_or_404(Itinerary, pk=pk, user=request.user)
    
    # Get all activities for this itinerary
    activities = Activity.objects.filter(itinerary=itinerary).order_by('day_number', 'order')
    
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
                Activity.objects.create(
                    itinerary=itinerary,
                    day_number=day_number,
                    time=activity_data['time'],
                    activity=activity_data['activity'],
                    description=activity_data.get('description', ''),
                    cost=activity_data.get('cost', ''),
                    order=order
                )
        # Refresh the activities after creating them
        return redirect('view_itinerary', pk=pk)
    
    return render(request, 'users/view_itinerary.html', {
        'itinerary': itinerary,
        'days': days_list
    })

@login_required
@require_http_methods(["POST"])
def add_activity(request, pk):
    try:
        itinerary = get_object_or_404(Itinerary, pk=pk, user=request.user)
        data = json.loads(request.body)
        
        # Validate required fields
        if not all(key in data for key in ['day_number', 'time', 'activity']):
            return JsonResponse({'error': 'Missing required fields'}, status=400)
        
        # Get the maximum order for the day
        max_order = Activity.objects.filter(
            itinerary=itinerary,
            day_number=data['day_number']
        ).aggregate(models.Max('order'))['order__max'] or 0
        
        activity = Activity.objects.create(
            itinerary=itinerary,
            day_number=data['day_number'],
            time=data['time'],
            activity=data['activity'],
            description=data.get('description', ''),
            cost=data.get('cost', ''),
            order=max_order + 1
        )
        
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
        activity = get_object_or_404(Activity, id=activity_id, itinerary__pk=pk, itinerary__user=request.user)
        data = json.loads(request.body)
        
        # Update the activity fields
        activity.time = data['time']
        activity.activity = data['activity']
        activity.description = data.get('description', '')
        activity.cost = data.get('cost', '')
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
        activity = get_object_or_404(Activity, id=activity_id, itinerary__pk=pk, itinerary__user=request.user)
        activity.delete()
        return JsonResponse({'status': 'success'})
    except Activity.DoesNotExist:
        return JsonResponse({'error': 'Activity not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)
