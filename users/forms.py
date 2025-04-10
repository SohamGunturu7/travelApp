from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from .models import Itinerary
from datetime import date


class UserRegisterForm(UserCreationForm):
    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = ['username', 'email', 'password1', 'password2']

    def save(self, commit=True):
        user = super(UserRegisterForm, self).save(commit=False)
        user.email = self.cleaned_data['email']
        if commit:
            user.save()
        return user


class UserUpdateForm(forms.ModelForm):
    username = forms.CharField(max_length=150, required=True, help_text='')

    class Meta:
        model = User
        fields = ['username', 'email']


class ItineraryForm(forms.ModelForm):
    interests = forms.MultipleChoiceField(
        choices=Itinerary.INTEREST_CHOICES,
        widget=forms.CheckboxSelectMultiple,
        help_text="Select all that interest you")

    class Meta:
        model = Itinerary
        fields = [
            'destination', 'start_date', 'end_date', 'budget', 'interests',
            'number_of_people', 'preferred_pace'
        ]
        widgets = {
            'start_date':
            forms.DateInput(attrs={
                'type': 'date',
                'min': date.today().isoformat()
            }),
            'end_date':
            forms.DateInput(attrs={
                'type': 'date',
                'min': date.today().isoformat()
            }),
            'budget':
            forms.NumberInput(attrs={
                'min': '0',
                'step': '0.01'
            }),
            'number_of_people':
            forms.NumberInput(attrs={
                'min': '1',
                'max': '20'
            }),
        }

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')

        if start_date and end_date:
            if start_date < date.today():
                raise forms.ValidationError("Start date cannot be in the past")
            if end_date < start_date:
                raise forms.ValidationError(
                    "End date must be after start date")
            if (end_date - start_date).days > 30:
                raise forms.ValidationError(
                    "Trip duration cannot exceed 30 days")

        return cleaned_data

