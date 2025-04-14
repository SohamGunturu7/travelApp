from django.urls import path
from django.urls import reverse_lazy
from . import views
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('register/', views.register, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('home/', views.home, name='home'),
    path('map/', views.map_view, name='map'),
    path('delete_account/', views.delete_account, name='delete_account'),
    path('profile/update/', views.update_profile, name='update_profile'),
    path('itinerary/create/', views.create_itinerary, name='create_itinerary'),
    path('itinerary/<int:pk>/', views.view_itinerary, name='view_itinerary'),
    path('itinerary/<int:pk>/activity/add/',
         views.add_activity,
         name='add_activity'),
    path('itinerary/<int:pk>/activity/<int:activity_id>/edit/',
         views.edit_activity,
         name='edit_activity'),
    path('itinerary/<int:pk>/activity/<int:activity_id>/delete/',
         views.delete_activity,
         name='delete_activity'),
    path('itinerary/<int:pk>/recommendations/',
         views.get_recommendations,
         name='get_recommendations'),

    # Password reset views:
    path('password_reset/',
         views.LoggedInPasswordResetView.as_view(
             template_name='users/password_reset.html',
             email_template_name='users/password_reset_email.html',
             subject_template_name='users/password_reset_subject.txt',
         ),
         name='password_reset'),

    # The done page should be at /password_reset_done/
    path('password_reset_done/',
         auth_views.PasswordResetDoneView.as_view(
             template_name='users/password_reset_done.html'),
         name='password_reset_done'),

    # Other URL patterns for resetting and confirming...
    path('reset/<uidb64>/<token>/',
         auth_views.PasswordResetConfirmView.as_view(
             template_name='users/password_reset_confirm.html',
             success_url=reverse_lazy('password_reset_complete'),
         ),
         name='password_reset_confirm'),
    path('reset/done/',
         auth_views.PasswordResetCompleteView.as_view(
             template_name='users/password_reset_complete.html'),
         name='password_reset_complete'),
]
