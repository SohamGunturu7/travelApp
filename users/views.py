from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from .forms import UserRegisterForm, ItineraryForm
from .models import Itinerary
import google.generativeai as genai
import json

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
                # List available models first (for debugging)
                list_available_models()
                
                # Configure the model
                generation_config = {
                    "temperature": 0.9,
                    "top_p": 1,
                    "top_k": 1,
                    "max_output_tokens": 2048,
                }

                safety_settings = [
                    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
                    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
                    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
                    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
                ]

                # Create the model with the correct name
                model = genai.GenerativeModel(
                    model_name="models/gemini-1.5-pro",
                    generation_config=generation_config
                )

                prompt = f"""Create a detailed daily travel itinerary for a {itinerary.duration_days}-day trip to {itinerary.destination}.

IMPORTANT: You MUST provide a complete schedule for ALL {itinerary.duration_days} days. Do not summarize, skip, or combine days. Each day must be individually detailed regardless of similarities.

Trip Details:
- Duration: {itinerary.duration_days} days (requiring {itinerary.duration_days} individual day schedules)
- Dates: {itinerary.start_date} to {itinerary.end_date}
- Budget: ${itinerary.budget} (${itinerary.budget / itinerary.duration_days:.2f} per day)
- Number of people: {itinerary.number_of_people}
- Interests: {', '.join(itinerary.interests)}
- Preferred pace: {itinerary.preferred_pace}

Strict Formatting Requirements:
1. You MUST provide a detailed schedule for EACH of the {itinerary.duration_days} days
2. Do NOT use phrases like "similar to day X" or "repeat previous activities"
3. Each day must have its own unique activities and schedule
4. Every single day must follow the exact same formatting
5. Each activity must have its own line with exact timestamp
6. Never skip or summarize days, even for longer trips
7. If activities are repeated, still list them in full detail each time

Format each day exactly as follows:

Day [X] - [Full Date]
07:00 - [Activity] - [Cost] - [Details]
08:00 - [Activity] - [Cost] - [Details]
(Continue with activities throughout the day)
22:00 - Return to Hotel - [Cost] - [Transportation Details]

Required Elements for Each Day:
- Morning activities (starting 07:00-08:00)
- Mid-morning break (around 10:30)
- Lunch (12:00-13:30)
- Afternoon activities
- Evening activities
- Dinner (18:00-20:00)
- Return to hotel time
- ALL transit times between locations
- ALL costs for each activity

Example Format:
Day 1 - Monday, March 15
07:00 - Breakfast at Sunrise Cafe - $15 - Local breakfast specialties
08:30 - Transit to Museum - $3 - Bus Line 100, 20-minute ride
09:00 - City Museum Tour - $25 - Guided tour available
10:30 - Coffee Break at Art Cafe - $5 - Famous local pastries
11:00 - Walk to Historical District - $0 - 15-minute walk
12:30 - Lunch at Heritage Restaurant - $30 - Traditional cuisine
14:00 - Afternoon Activities...
(Continue with full day schedule)
22:00 - Return to Hotel - $10 - Evening taxi fare

Remember:
- EVERY day must be fully detailed
- NO summarizing or skipping days
- NO referring to other days
- FULL details for each activity
- EXACT timestamps for everything
- ALL costs must be listed
- ALL transportation details included

Daily Budget Reminder: ${itinerary.budget / itinerary.duration_days:.2f} per day

Generate a complete, detailed schedule for ALL {itinerary.duration_days} days following these exact requirements."""

                response = model.generate_content(prompt)
                
                if response.text:
                    itinerary.generated_plan = response.text
                    itinerary.save()
                    return redirect('view_itinerary', pk=itinerary.pk)
                else:
                    raise Exception("No response generated from the AI model")
            
            except Exception as e:
                messages.error(request, f'Error generating itinerary: {str(e)}')
                return redirect('home')
    else:
        form = ItineraryForm()
    
    return render(request, 'users/create_itinerary.html', {'form': form})


@login_required
def view_itinerary(request, pk):
    itinerary = Itinerary.objects.get(pk=pk, user=request.user)
    return render(request, 'users/view_itinerary.html', {'itinerary': itinerary})
