from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from exams.models import Exam, MentorOffer
from notifications.services import enqueue

from .models import AccessGrant, Order, PaymentAccount, PaymentReceipt


@transaction.atomic
def create_order(*, user, exam_id, mentor_offer_id=None):
    if not user.is_active:
        raise PermissionDenied("Account is inactive.")
    exam = Exam.objects.select_for_update().get(pk=exam_id, is_published=True)
    if not exam.sections.exists():
        raise ValidationError("An exam must have sections before it can be purchased.")
    mentor = None
    mentor_price = Decimal("0")
    if mentor_offer_id is not None:
        offer = MentorOffer.objects.select_for_update().select_related("mentor__user").get(
            pk=mentor_offer_id, exam=exam, is_active=True,
        )
        offer.full_clean()
        if not offer.mentor.user.is_active:
            raise ValidationError("Mentor is unavailable.")
        mentor, mentor_price = offer.mentor, offer.surcharge
    order = Order(
        user=user, exam=exam, mentor=mentor, exam_title=exam.title,
        mentor_name=(mentor.user.get_full_name() or mentor.user.get_username()) if mentor else "",
        base_price=exam.price, mentor_price=mentor_price,
        total_amount=exam.price + mentor_price, currency=exam.currency,
    )
    order.full_clean()
    order.save()
    return order


@transaction.atomic
def submit_receipt(*, user, order_id, payment_account_id, image):
    order = Order.objects.select_for_update().get(pk=order_id, user=user)
    if order.status not in {Order.Status.PENDING, Order.Status.UNDER_REVIEW}:
        raise ValidationError("This order no longer accepts receipts.")
    account = PaymentAccount.objects.get(pk=payment_account_id, is_active=True)
    receipt = PaymentReceipt(order=order, payment_account=account, image=image)
    receipt.full_clean()
    receipt.save()
    order.status = Order.Status.UNDER_REVIEW
    order.save(update_fields=["status", "updated_at"])
    for admin in get_user_model().objects.filter(is_active=True, is_staff=True):
        if admin.has_perm("billing.change_paymentreceipt"):
            enqueue(admin, "receipt_submitted", f"receipt:{receipt.pk}", {"order_id": order.pk, "receipt_id": receipt.pk, "user_id": user.pk})
    return receipt


@transaction.atomic
def review_receipt(*, actor, receipt_id, approve, note=""):
    if not actor.is_active or not actor.is_staff or not actor.has_perm("billing.change_paymentreceipt"):
        raise PermissionDenied("Payment review permission is required.")
    if approve and not actor.has_perm("billing.add_accessgrant"):
        raise PermissionDenied("Access grant permission is required.")
    # Lock the order first for every receipt of this purchase.
    order_id = PaymentReceipt.objects.values_list("order_id", flat=True).get(pk=receipt_id)
    order = Order.objects.select_for_update().get(pk=order_id)
    receipt = PaymentReceipt.objects.select_for_update().get(pk=receipt_id)
    target = PaymentReceipt.Status.APPROVED if approve else PaymentReceipt.Status.REJECTED
    if receipt.status == target:
        return receipt  # A retried approval never grants another attempt.
    if receipt.status != PaymentReceipt.Status.PENDING or order.status != Order.Status.UNDER_REVIEW:
        raise ValidationError("Receipt or order has already been reviewed.")
    now = timezone.now()
    receipt.status, receipt.reviewed_by, receipt.reviewed_at = target, actor, now
    receipt.review_note = note
    receipt.full_clean()
    receipt.save()
    if approve:
        order.status, order.paid_at = Order.Status.PAID, now
        order.full_clean()
        order.save(update_fields=["status", "paid_at", "updated_at"])
        access = AccessGrant(order=order, granted_by=actor, granted_at=now)
        access.full_clean()
        access.save()
    elif not order.receipts.filter(status=PaymentReceipt.Status.PENDING).exists():
        order.status = Order.Status.PENDING
        order.save(update_fields=["status", "updated_at"])
    enqueue(order.user, f"payment_{target}", f"receipt:{receipt.pk}:{target}", {"order_id": order.pk})
    return receipt
