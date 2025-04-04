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
    itinerary = Itinerary.objects.get(pk=pk, user=request.user)
    return render(request, 'users/view_itinerary.html', {'itinerary': itinerary})
