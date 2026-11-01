from django.conf import settings
from django.contrib import admin
from django.urls import include, path
from rest_framework_simplejwt.views import TokenBlacklistView, TokenObtainPairView, TokenRefreshView

from therapybot.views.common import AuthThrottle


class ThrottledTokenObtainPairView(TokenObtainPairView):
    throttle_classes = [AuthThrottle]


urlpatterns = [
    path("api/token/", ThrottledTokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("api/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("api/token/logout/", TokenBlacklistView.as_view(), name="token_blacklist"),
    path("api/", include("therapybot.urls")),
]
if settings.ADMIN_ENABLED:
    urlpatterns.append(path("admin/", admin.site.urls))
