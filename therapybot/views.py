from django.shortcuts import render
from django.http import HttpResponse

#l
# Import any models that you need

# Import any forms

# Create your views here.

def index(request):
    return render(request, 'therapy/HomePage.html')
