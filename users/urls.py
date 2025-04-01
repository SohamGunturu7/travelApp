from django.urls import path
from . import views

urlpatterns = [
    path('register/', views.register, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('home/', views.home, name='home'),
    path('itinerary/create/', views.create_itinerary, name='create_itinerary'),
    path('itinerary/<int:pk>/', views.view_itinerary, name='view_itinerary'),
] 