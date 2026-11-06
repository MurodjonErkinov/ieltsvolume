import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator, MinValueValidator, RegexValidator
from django.db import models
from django.db.models import F, Q

from common.models import TimestampedModel, nonnegative


def receipt_path(instance, filename):
    extension = filename.rsplit(".", 1)[-1].lower()
    return f"private/receipts/{uuid.uuid4()}.{extension}"


class PaymentAccount(TimestampedModel):
    """Receiving card only. Never store CVV, PIN or card expiry."""

    label = models.CharField(max_length=100)
    holder_name = models.CharField(max_length=150)
    card_number = models.CharField(max_length=19, validators=[RegexValidator(r"^\d{16,19}$")])
    instructions = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.label} •••• {self.card_number[-4:]}"


class Order(TimestampedModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Awaiting payment"
        UNDER_REVIEW = "under_review", "Receipt under review"
        PAID = "paid", "Approved"
        CANCELLED = "cancelled", "Cancelled"
        REFUNDED = "refunded", "Refunded"

    reference = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="orders")
    exam = models.ForeignKey("exams.Exam", on_delete=models.PROTECT, related_name="orders")
    mentor = models.ForeignKey("accounts.Profile", on_delete=models.PROTECT, null=True, blank=True, related_name="mentor_orders")
    exam_title = models.CharField(max_length=255)
    mentor_name = models.CharField(max_length=150, blank=True)
    base_price = models.DecimalField(max_digits=14, decimal_places=2, validators=[MinValueValidator(0)])
    mentor_price = models.DecimalField(max_digits=14, decimal_places=2, default=0, validators=[MinValueValidator(0)])
    total_amount = models.DecimalField(max_digits=14, decimal_places=2, validators=[MinValueValidator(0)])
    currency = models.CharField(max_length=3, default="UZS")
    status = models.CharField(max_length=15, choices=Status, default=Status.PENDING)
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=["user", "-created_at"]), models.Index(fields=["status", "-created_at"])]
        constraints = [
            nonnegative("base_price"), nonnegative("mentor_price"), nonnegative("total_amount"),
            models.CheckConstraint(condition=Q(total_amount=F("base_price") + F("mentor_price")), name="order_total_matches_prices"),
            models.CheckConstraint(condition=Q(mentor__isnull=False) | Q(mentor_price=0), name="mentor_price_requires_mentor"),
            models.CheckConstraint(condition=~Q(status="paid") | Q(paid_at__isnull=False), name="paid_order_has_timestamp"),
        ]

    def clean(self):
        super().clean()
        if self.mentor_id and self.mentor.role != "mentor":
            raise ValidationError({"mentor": "Select a mentor profile."})

    def __str__(self):
        return str(self.reference)


class PaymentReceipt(TimestampedModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending review"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    order = models.ForeignKey(Order, on_delete=models.PROTECT, related_name="receipts")
    payment_account = models.ForeignKey(PaymentAccount, on_delete=models.PROTECT, related_name="receipts")
    image = models.FileField(upload_to=receipt_path, validators=[FileExtensionValidator(["jpg", "jpeg", "png", "webp"])])
    status = models.CharField(max_length=10, choices=Status, default=Status.PENDING)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="reviewed_receipts")
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_note = models.TextField(blank=True)

    class Meta:
        indexes = [models.Index(fields=["status", "created_at"])]
        constraints = [
            models.UniqueConstraint(fields=["order"], condition=Q(status="approved"), name="one_approved_receipt_per_order"),
            models.CheckConstraint(
                condition=Q(status="pending", reviewed_by__isnull=True, reviewed_at__isnull=True)
                | Q(status__in=["approved", "rejected"], reviewed_by__isnull=False, reviewed_at__isnull=False),
                name="receipt_review_has_reviewer_and_time",
            ),
        ]


class AccessGrant(TimestampedModel):
    """No expiry. User, exam and mentor are derived from the purchase."""

    order = models.OneToOneField(Order, on_delete=models.PROTECT, related_name="access")
    granted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="granted_accesses")
    granted_at = models.DateTimeField()
    revoked_at = models.DateTimeField(null=True, blank=True)
    revocation_reason = models.TextField(blank=True)

    def clean(self):
        super().clean()
        if self.order_id and self.order.status != Order.Status.PAID:
            raise ValidationError({"order": "Only an approved purchase can grant access."})
