from therapybot import views
from django.urls import path
from django.conf.urls import include


urlpatterns = [
    path('', views.index, name='index'),  # Home Page
    path('register/', views.register, name="register"),
    path('get_started/', views.get_started, name="get_started")
]
