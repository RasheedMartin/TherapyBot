from django.http import JsonResponse
from therapybot import views
from django.urls import include, path
from rest_framework.routers import DefaultRouter

router = DefaultRouter()

urlpatterns = [
    path("", include(router.urls)),
    path("current_user/", views.current_user, name="current_user"),
    path("get_started/", views.get_started, name="get_started"),
    path("register_user/", views.register_user, name="register_user"),
    path('forgot-password/', views.forgot_password, name='forgot-password'),
    path('reset-password/', views.reset_password, name='reset-password'),
]