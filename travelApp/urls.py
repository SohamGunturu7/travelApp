"""
URL configuration for travelApp project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.urls import path, include
from django.http import HttpResponse
from django.views.generic import RedirectView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("users.urls")),
    path("users/login/", RedirectView.as_view(url="/login/", permanent=True)),
    path("users/register/", RedirectView.as_view(url="/register/", permanent=True)),
    path("users/logout/", RedirectView.as_view(url="/logout/", permanent=True)),
    path("users/home/", RedirectView.as_view(url="/home/", permanent=True)),
    path("", RedirectView.as_view(url="/login/", permanent=True), name="index"),
    path('favicon.ico', lambda request: HttpResponse(status=204)),
]
