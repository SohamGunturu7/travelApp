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

                prompt = f"""Create a detailed daily travel itinerary for a trip to {itinerary.destination}.
                Trip Details:
                - Duration: {itinerary.duration_days} days
                - Dates: {itinerary.start_date} to {itinerary.end_date}
                - Budget: ${itinerary.budget}
                - Number of people: {itinerary.number_of_people}
                - Interests: {', '.join(itinerary.interests)}
                - Preferred pace: {itinerary.preferred_pace}

                Please provide a day-by-day itinerary including:
                - Morning, afternoon, and evening activities
                - Recommended restaurants and cuisine
                - Estimated costs for activities and meals
                - Travel tips and local customs
                - Must-see attractions based on the specified interests
                
                Format the response in a clear, organized manner with daily schedules."""

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
