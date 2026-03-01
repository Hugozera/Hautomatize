from django.urls import path
from .views import api_users

urlpatterns = [
    path('', api_users, name='api_users'),
]
