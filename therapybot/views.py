from django.contrib.auth import login
from django.shortcuts import render
from django.http import HttpResponse

from django.contrib.auth import login
from django.shortcuts import redirect, render
from django.urls import reverse
from therapybot.forms import CustomUserCreationForm
from testingAI import therapy


# Import any models that you need

# Import any forms
from . import forms


# Create your views here.

def index(request):
    return render(request, 'therapy/HomePage.html')


def register(request):
    if request.method == "GET":
        return render(
            request, "registration/register.html",
            {"form": CustomUserCreationForm}
        )
    elif request.method == "POST":
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect(reverse("index"))

        else:
            for msg in form.error_messages:
                print(form.error_messages[msg])

            return render(request=request,
                          template_name="registration/register.html",
                          context={"form": form})

    form = CustomUserCreationForm
    return render(request=request,
                  template_name="registration/register.html",
                  context={"form": form})


def get_started(request):
    form = forms.FormName()
    therapy_type = ''
    question = ''
    result = ''
    if request.method == 'POST':
        form = forms.FormName(request.POST)

        if form.is_valid():
            # DO SOMETHING CODE
            therapy_type = form.cleaned_data['therapy_type']
            question = form.cleaned_data['question_field']

            result = therapy(question, therapy_type)

    return render(request, 'therapy/get_started.html', context={'form': form, 'result': result, 'question': question})


