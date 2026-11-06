from django.conf import settings
from django.db import models

from common.models import TimestampedModel


class Notification(TimestampedModel):
    class Channel(models.TextChoices):
        SITE = "site", "Website"
        TELEGRAM = "telegram", "Telegram"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending delivery"
        SENT = "sent", "Sent"
        FAILED = "failed", "Failed"

    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="notifications")
    channel = models.CharField(max_length=10, choices=Channel)
    event = models.CharField(max_length=60)
    deduplication_key = models.CharField(max_length=180)
    payload = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=10, choices=Status, default=Status.PENDING)
    sent_at = models.DateTimeField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    delivery_attempts = models.PositiveIntegerField(default=0)
    last_error = models.TextField(blank=True)

    class Meta:
        indexes = [models.Index(fields=["recipient", "channel", "read_at"]), models.Index(fields=["channel", "status", "created_at"])]
        constraints = [models.UniqueConstraint(fields=["recipient", "channel", "deduplication_key"], name="unique_notification_delivery")]
