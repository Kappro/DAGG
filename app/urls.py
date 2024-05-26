from django.urls import path, include
from app import views

urlpatterns = [
    path('', views.ping),
    path('route/', views.route)
]