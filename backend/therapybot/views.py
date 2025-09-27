from django.http import HttpResponse
from django.shortcuts import render

# Import any models that you need

# Import any forms

# Create your views here.

# therapybot/views.py

def index(request):
    return render(request, 'index.html')  # <-- relative to template dirs


