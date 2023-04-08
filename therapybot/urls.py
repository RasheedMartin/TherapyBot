from therapybot import views
from django.urls import path

urlpatterns = [
    path('', views.index, name='index') # Home Page

]