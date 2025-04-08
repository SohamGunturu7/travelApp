from django.urls import path
from . import views

urlpatterns = [
    path('register/', views.register, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('home/', views.home, name='home'),
    path('itinerary/create/', views.create_itinerary, name='create_itinerary'),
    path('itinerary/<int:pk>/', views.view_itinerary, name='view_itinerary'),
    path('itinerary/<int:pk>/activity/add/', views.add_activity, name='add_activity'),
    path('itinerary/<int:pk>/activity/<int:activity_id>/edit/', views.edit_activity, name='edit_activity'),
    path('itinerary/<int:pk>/activity/<int:activity_id>/delete/', views.delete_activity, name='delete_activity'),
    path('itinerary/<int:pk>/recommendations/', views.get_recommendations, name='get_recommendations'),
] 