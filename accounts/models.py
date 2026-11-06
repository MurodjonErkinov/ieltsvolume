from django.conf import settings
from django.core.validators import RegexValidator
from django.db import models
from django.db.models import F, Q

from common.models import TimestampedModel


class Profile(TimestampedModel):
    class Role(models.TextChoices):
        STUDENT = "student", "Student"
        MENTOR = "mentor", "Mentor"

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="profile")
    role = models.CharField(max_length=10, choices=Role, default=Role.STUDENT)
    phone = models.CharField(
        max_length=16, unique=True, null=True, blank=True,
        validators=[RegexValidator(r"^\+[1-9]\d{7,14}$", "Use international phone format.")],
    )
    telegram_id = models.BigIntegerField(unique=True, null=True, blank=True)
    telegram_chat_id = models.BigIntegerField(null=True, blank=True)
    phone_verified_at = models.DateTimeField(null=True, blank=True)
    language = models.CharField(max_length=2, choices=settings.LANGUAGES, default="uz")

    def __str__(self):
        return self.user.get_username()


class TelegramChallenge(TimestampedModel):
    """Store a Django password hash of an OTP, never its plaintext value."""

    class Purpose(models.TextChoices):
        REGISTER = "register", "Registration"
        RESET_PASSWORD = "reset_password", "Password reset"

    phone = models.CharField(max_length=16)
    telegram_id = models.BigIntegerField()
    purpose = models.CharField(max_length=20, choices=Purpose)
    code_hash = models.CharField(max_length=256)
    expires_at = models.DateTimeField()
    consumed_at = models.DateTimeField(null=True, blank=True)
    failed_attempts = models.PositiveSmallIntegerField(default=0)

    class Meta:
        indexes = [models.Index(fields=["telegram_id", "purpose", "-created_at"])]
        constraints = [
            models.CheckConstraint(condition=Q(expires_at__gt=F("created_at")), name="otp_expiry_after_creation"),
        ]
