from datetime import timedelta

from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils import timezone
from rest_framework import serializers

from therapybot.models import Conversation, Message, Plan, PlanStep, Profile, SavedProvider, SessionNote
from therapybot.verification import is_email_verified

THERAPY_TYPES = [
    "General Therapy",
    "Cognitive Behavioural Therapy (CBT)",
    "Dialectical Behaviour Therapy (DBT)",
    "Anxiety Support",
    "Family Therapy",
    "Teen Counseling",
]


class UserSerializer(serializers.ModelSerializer):
    display_name = serializers.SerializerMethodField()
    email_verified = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ("id", "username", "email", "email_verified", "display_name", "date_joined")

    def get_email_verified(self, user):
        return is_email_verified(user)

    def get_display_name(self, user):
        profile = getattr(user, "profile", None)
        return (profile.display_name if profile else "") or user.username


class ProfileSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)
    email = serializers.EmailField(source="user.email")
    date_joined = serializers.DateTimeField(source="user.date_joined", read_only=True)
    has_password = serializers.BooleanField(source="user.has_usable_password", read_only=True)

    class Meta:
        model = Profile
        fields = (
            "username",
            "email",
            "date_joined",
            "has_password",
            "display_name",
            "goals",
            "zip_code",
            "insurance",
            "session_format",
            "timezone",
            "reminders_enabled",
            "reminder_time",
        )

    def validate_email(self, value):
        user = self.instance.user
        if User.objects.filter(email__iexact=value).exclude(pk=user.pk).exists():
            raise serializers.ValidationError("An account with that email already exists.")
        return value.lower()

    def validate_timezone(self, value):
        import zoneinfo

        if value:
            try:
                zoneinfo.ZoneInfo(value)
            except (zoneinfo.ZoneInfoNotFoundError, ValueError):
                raise serializers.ValidationError("Unknown time zone.")
        return value

    def validate_zip_code(self, value):
        value = value.strip()
        if value and not (len(value) == 5 and value.isdigit()):
            raise serializers.ValidationError("Enter a 5-digit US ZIP code.")
        return value

    def update(self, instance, validated_data):
        user_data = validated_data.pop("user", {})
        new_email = user_data.get("email")
        if new_email and new_email != instance.user.email:
            instance.user.email = new_email
            instance.user.save(update_fields=["email"])
            # A new address has to be confirmed again
            validated_data["email_verified_at"] = None
            self.context["email_changed"] = True
        return super().update(instance, validated_data)


class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(required=False, allow_blank=True)
    new_password = serializers.CharField()

    def validate_current_password(self, value):
        user = self.context["request"].user
        # Accounts created with Google have no password yet, so they can set one directly
        if user.has_usable_password() and not user.check_password(value):
            raise serializers.ValidationError("Your current password is incorrect.")
        return value

    def validate_new_password(self, value):
        try:
            validate_password(value, user=self.context["request"].user)
        except DjangoValidationError as e:
            raise serializers.ValidationError(list(e.messages))
        return value


class RegisterSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
    confirm_age = serializers.BooleanField()
    accept_terms = serializers.BooleanField()

    def validate_confirm_age(self, value):
        if not value:
            raise serializers.ValidationError("You must be 18 or older to use TherapyBot.")
        return value

    def validate_accept_terms(self, value):
        if not value:
            raise serializers.ValidationError("Please accept the Terms and Privacy Policy to continue.")
        return value

    def validate_username(self, value):
        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError("That username is already taken.")
        return value

    def validate_email(self, value):
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("An account with that email already exists.")
        return value.lower()

    def validate(self, attrs):
        candidate = User(username=attrs["username"], email=attrs["email"])
        try:
            validate_password(attrs["password"], user=candidate)
        except DjangoValidationError as e:
            raise serializers.ValidationError({"password": list(e.messages)})
        return attrs

    def create(self, validated_data):
        validated_data.pop("confirm_age")
        validated_data.pop("accept_terms")
        user = User.objects.create_user(**validated_data)
        now = timezone.now()
        Profile.objects.create(user=user, age_confirmed_at=now, terms_accepted_at=now)
        return user


class MessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Message
        fields = ("id", "role", "content", "is_crisis", "risk_level", "suggested_action", "sources", "created_at")


class ConversationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Conversation
        fields = ("id", "title", "therapy_type", "created_at", "updated_at")
        read_only_fields = ("created_at", "updated_at")

    def validate_therapy_type(self, value):
        if value not in THERAPY_TYPES:
            raise serializers.ValidationError("Unknown therapy type.")
        return value


class ConversationDetailSerializer(ConversationSerializer):
    messages = MessageSerializer(many=True, read_only=True)

    class Meta(ConversationSerializer.Meta):
        fields = ConversationSerializer.Meta.fields + ("messages",)


class SendMessageSerializer(serializers.Serializer):
    content = serializers.CharField(max_length=settings.CHAT_MAX_MESSAGE_LENGTH, trim_whitespace=True)


class SavedProviderSerializer(serializers.ModelSerializer):
    class Meta:
        model = SavedProvider
        fields = ("id", "npi", "details", "status", "notes", "created_at", "updated_at")
        read_only_fields = ("created_at", "updated_at")

    def validate_details(self, value):
        if not isinstance(value, dict) or not value.get("name"):
            raise serializers.ValidationError("Provider details must include a name.")
        allowed = {"name", "credential", "is_organization", "type", "type_label", "specialty", "license_state",
                   "street", "city", "state", "zip", "phone", "lat", "lng"}
        return {k: v for k, v in value.items() if k in allowed}


CHECK_IN_WINDOW_DAYS = 60


class PlanStepSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=False)
    check_ins = serializers.SerializerMethodField()

    class Meta:
        model = PlanStep
        fields = ("id", "title", "details", "frequency", "weekday", "time_of_day", "action", "order", "check_ins")

    def get_check_ins(self, step):
        since = timezone.localdate() - timedelta(days=CHECK_IN_WINDOW_DAYS)
        return [c.date.isoformat() for c in step.check_ins.all() if c.date >= since]

    def validate(self, attrs):
        if attrs.get("frequency") == PlanStep.Frequency.WEEKLY:
            if attrs.get("weekday") is None:
                raise serializers.ValidationError({"weekday": "Choose a day for weekly steps."})
            if not 0 <= attrs["weekday"] <= 6:
                raise serializers.ValidationError({"weekday": "Day must be between 0 (Monday) and 6 (Sunday)."})
        else:
            attrs["weekday"] = None
        return attrs


class PlanSerializer(serializers.ModelSerializer):
    steps = PlanStepSerializer(many=True)

    class Meta:
        model = Plan
        fields = ("id", "title", "summary", "conversation", "archived", "steps", "created_at", "updated_at")
        read_only_fields = ("created_at", "updated_at")

    def validate_conversation(self, value):
        if value and value.user_id != self.context["request"].user.pk:
            raise serializers.ValidationError("Conversation not found.")
        return value

    def validate_steps(self, value):
        if not value:
            raise serializers.ValidationError("A plan needs at least one step.")
        if len(value) > 12:
            raise serializers.ValidationError("Keep plans to 12 steps or fewer.")
        return value

    def _save_steps(self, plan, steps):
        """Update steps that kept their id, create new ones, delete the rest (check-ins follow their step)."""
        existing = {s.id: s for s in plan.steps.all()}
        keep = []
        for order, data in enumerate(steps):
            data = {**data, "order": order}
            step = existing.get(data.pop("id", None))
            if step:
                for field, value in data.items():
                    setattr(step, field, value)
                step.save()
            else:
                step = PlanStep.objects.create(plan=plan, **data)
            keep.append(step.id)
        plan.steps.exclude(id__in=keep).delete()

    def create(self, validated_data):
        steps = validated_data.pop("steps")
        plan = Plan.objects.create(user=self.context["request"].user, **validated_data)
        self._save_steps(plan, steps)
        return plan

    def update(self, instance, validated_data):
        steps = validated_data.pop("steps", None)
        instance = super().update(instance, validated_data)
        if steps is not None:
            self._save_steps(instance, steps)
        return instance


class SessionNoteListSerializer(serializers.ModelSerializer):
    class Meta:
        model = SessionNote
        fields = ("id", "title", "session_date", "created_at")


class SessionNoteSerializer(serializers.ModelSerializer):
    class Meta:
        model = SessionNote
        fields = ("id", "title", "session_date", "original_text", "explanation", "created_at")
        read_only_fields = ("original_text", "explanation", "created_at")
