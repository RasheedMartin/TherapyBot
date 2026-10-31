"""Sign-up, sign-in (incl. Google), email verification, passwords, profile, data export and deletion."""

import logging

from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.utils import timezone
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from rest_framework import status
from rest_framework.decorators import (
    api_view,
    authentication_classes,
    permission_classes,
    throttle_classes,
)
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from therapybot.models import (
    Conversation,
    Plan,
    Profile,
    SavedProvider,
    ClinicalDocument,
)
from therapybot.serializers import (
    ChangePasswordSerializer,
    ConversationDetailSerializer,
    PlanSerializer,
    ProfileSerializer,
    RegisterSerializer,
    SavedProviderSerializer,
    SessionNoteSerializer,
    UserSerializer,
)
from therapybot.verification import (
    email_verification_token,
    is_email_verified,
    send_verification_email,
)
from therapybot.views.common import AuthThrottle, get_profile

logger = logging.getLogger(__name__)


@api_view(["GET"])
def current_user(request):
    return Response(UserSerializer(request.user).data)


@api_view(["GET", "PATCH"])
def profile(request):
    instance = get_profile(request.user)
    if request.method == "GET":
        return Response(ProfileSerializer(instance).data)
    serializer = ProfileSerializer(instance, data=request.data, partial=True)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    if serializer.context.get("email_changed"):
        send_verification_email(instance.user)  # request.user still holds the old address
    return Response(serializer.data)


@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([AuthThrottle])
def verify_email(request):
    try:
        user = User.objects.get(pk=force_str(urlsafe_base64_decode(request.data.get("uid") or "")))
    except (User.DoesNotExist, ValueError, TypeError, OverflowError):
        user = None
    if user is None or not email_verification_token.check_token(user, request.data.get("token") or ""):
        return Response(
            {"detail": "This verification link is invalid or has expired. Sign in to request a new one."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    profile = get_profile(user)
    profile.email_verified_at = timezone.now()
    profile.save(update_fields=["email_verified_at"])
    return Response({"detail": "Email verified."})


@api_view(["POST"])
@throttle_classes([AuthThrottle])
def resend_verification(request):
    if is_email_verified(request.user):
        return Response({"detail": "Your email is already verified."})
    send_verification_email(request.user)
    return Response({"detail": f"We sent a new link to {request.user.email}."})


@api_view(["POST"])
@throttle_classes([AuthThrottle])
def change_password(request):
    serializer = ChangePasswordSerializer(data=request.data, context={"request": request})
    serializer.is_valid(raise_exception=True)
    request.user.set_password(serializer.validated_data["new_password"])
    request.user.save()
    return Response({"detail": "Password updated."})


@api_view(["GET"])
def export_data(request):
    """Everything we store about the user, as a downloadable JSON file."""
    user = request.user
    payload = {
        "exported_at": timezone.now().isoformat(),
        "account": UserSerializer(user).data,
        "profile": ProfileSerializer(get_profile(user)).data,
        "conversations": ConversationDetailSerializer(
            Conversation.objects.filter(user=user).prefetch_related("messages"), many=True
        ).data,
        "plans": PlanSerializer(Plan.objects.filter(user=user).prefetch_related("steps__check_ins"), many=True).data,
        "saved_providers": SavedProviderSerializer(SavedProvider.objects.filter(user=user), many=True).data,
        "session_notes": SessionNoteSerializer(ClinicalDocument.objects.filter(owner=user), many=True).data,
    }
    response = Response(payload)
    response["Content-Disposition"] = 'attachment; filename="therapybot-data.json"'
    return response


@api_view(["POST"])
@throttle_classes([AuthThrottle])
def delete_account(request):
    if request.user.has_usable_password():
        if not request.user.check_password(request.data.get("password") or ""):
            return Response({"password": ["Your password is incorrect."]}, status=status.HTTP_400_BAD_REQUEST)
    elif request.data.get("confirm") != "DELETE":
        return Response({"confirm": ['Type "DELETE" to confirm.']}, status=status.HTTP_400_BAD_REQUEST)
    user_id = request.user.pk
    request.user.delete()  # cascades to profile, conversations and messages
    logger.info("Deleted account %s at the user's request", user_id)
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([AuthThrottle])
def register_user(request):
    serializer = RegisterSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    user = serializer.save()
    send_verification_email(user)
    return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)


RESET_SENT_MESSAGE = "If an account with that email exists, a reset link has been sent."


@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([AuthThrottle])
def forgot_password(request):
    email = (request.data.get("email") or "").strip()
    if not email:
        return Response({"detail": "Email is required."}, status=status.HTTP_400_BAD_REQUEST)

    # Respond identically whether or not the account exists
    for user in User.objects.filter(email__iexact=email, is_active=True):
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        reset_url = f"{settings.FRONTEND_URL}/reset-password?uid={uid}&token={token}"
        try:
            send_mail(
                subject="Reset your TherapyBot password",
                message=(
                    f"Hi {user.username},\n\n"
                    f"We received a request to reset your password. Use the link below to choose a new one:\n\n"
                    f"{reset_url}\n\n"
                    f"If you didn't request this, you can safely ignore this email."
                ),
                from_email=None,
                recipient_list=[user.email],
            )
        except Exception:
            logger.exception("Failed to send password reset email to user %s", user.pk)

    return Response({"detail": RESET_SENT_MESSAGE})


@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([AuthThrottle])
def reset_password(request):
    uid = request.data.get("uid")
    token = request.data.get("token")
    new_password = request.data.get("new_password")

    if not all([uid, token, new_password]):
        return Response({"detail": "uid, token, and new_password are required."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        user = User.objects.get(pk=force_str(urlsafe_base64_decode(uid)))
    except (User.DoesNotExist, ValueError, TypeError, OverflowError):
        user = None

    if user is None or not default_token_generator.check_token(user, token):
        return Response(
            {"detail": "This reset link is invalid or has expired. Please request a new one."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        validate_password(new_password, user=user)
    except ValidationError as e:
        return Response({"new_password": e.messages}, status=status.HTTP_400_BAD_REQUEST)

    user.set_password(new_password)
    user.save()
    return Response({"detail": "Password reset successful."})


def _unique_username(email: str) -> str:
    base = "".join(c for c in email.split("@")[0] if c.isalnum() or c in "._-")[:30] or "user"
    candidate, n = base, 1
    while User.objects.filter(username__iexact=candidate).exists():
        n += 1
        candidate = f"{base}{n}"
    return candidate


@api_view(["POST"])
@permission_classes([AllowAny])
@authentication_classes([])
@throttle_classes([AuthThrottle])
def google_sign_in(request):
    """
    Exchange a Google ID token for our JWTs. New users must also send confirm_age and accept_terms;
    without them the response is 400 with consent_required so the app can ask.
    """
    from google.auth.transport import requests as google_requests
    from google.oauth2 import id_token
    from rest_framework_simplejwt.tokens import RefreshToken

    if not settings.GOOGLE_CLIENT_ID:
        return Response({"detail": "Google sign-in isn't configured."}, status=status.HTTP_404_NOT_FOUND)
    try:
        claims = id_token.verify_oauth2_token(
            request.data.get("credential") or "", google_requests.Request(), settings.GOOGLE_CLIENT_ID
        )
    except ValueError:
        return Response({"detail": "Google sign-in failed. Please try again."}, status=status.HTTP_400_BAD_REQUEST)
    if not claims.get("email") or not claims.get("email_verified"):
        return Response({"detail": "Your Google account's email isn't verified."}, status=status.HTTP_400_BAD_REQUEST)

    email = claims["email"].lower()
    user = User.objects.filter(email__iexact=email).first()
    created = user is None
    now = timezone.now()
    if created:
        if not (request.data.get("confirm_age") is True and request.data.get("accept_terms") is True):
            return Response(
                {"consent_required": True, "detail": "Please confirm you're 18+ and accept the terms."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        user = User(username=_unique_username(email), email=email)
        user.set_unusable_password()
        user.save()
        Profile.objects.create(
            user=user,
            display_name=(claims.get("given_name") or "")[:80],
            email_verified_at=now,
            age_confirmed_at=now,
            terms_accepted_at=now,
        )
    else:
        # Google has proven ownership of this address, so it counts as verified
        profile = get_profile(user)
        if not profile.email_verified_at:
            profile.email_verified_at = now
            profile.save(update_fields=["email_verified_at"])
    if not user.is_active:
        return Response({"detail": "This account is disabled."}, status=status.HTTP_403_FORBIDDEN)

    refresh = RefreshToken.for_user(user)
    return Response({"access": str(refresh.access_token), "refresh": str(refresh), "created": created})
