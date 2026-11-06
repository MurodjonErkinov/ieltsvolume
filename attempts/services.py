from datetime import timedelta

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from billing.models import AccessGrant, Order
from notifications.services import enqueue

from .models import Attempt, AttemptSection, Evaluation, SectionEvaluation


@transaction.atomic
def start_attempt(*, user, access_id, acknowledged=False):
    if not acknowledged:
        raise ValidationError("Confirm that this is a single attempt and you have time to finish.")
    access = AccessGrant.objects.select_for_update().get(pk=access_id, order__user=user)
    if not user.is_active or access.revoked_at or access.order.status != Order.Status.PAID:
        raise PermissionDenied("Access is unavailable.")
    existing = Attempt.objects.filter(access=access).first()
    if existing:
        if existing.status == Attempt.Status.IN_PROGRESS:
            return existing  # Resume the same attempt, without resetting its timers.
        raise ValidationError("This purchase's single attempt has already been used.")
    sections = list(access.order.exam.sections.all())
    if not sections:
        raise ValidationError("Exam has no sections.")
    now = timezone.now()
    attempt = Attempt.objects.create(access=access, started_at=now)
    for position, section in enumerate(sections):
        AttemptSection.objects.create(
            attempt=attempt, section=section,
            started_at=now if position == 0 else None,
            deadline_at=now + timedelta(seconds=section.duration_seconds) if position == 0 else None,
        )
    return attempt


@transaction.atomic
def submit_attempt(*, user, attempt_id):
    attempt = Attempt.objects.select_for_update().get(pk=attempt_id, access__order__user=user)
    if not user.is_active:
        raise PermissionDenied("Account is inactive.")
    if attempt.status == Attempt.Status.SUBMITTED:
        return attempt
    now = timezone.now()
    # Section navigation/timeout handlers must finish each section first.
    if attempt.sections.filter(submitted_at__isnull=True).exists():
        raise ValidationError("Finish all purchased sections before submitting the attempt.")
    attempt.status, attempt.submitted_at = Attempt.Status.SUBMITTED, now
    attempt.full_clean()
    attempt.save(update_fields=["status", "submitted_at", "updated_at"])
    Evaluation.objects.create(attempt=attempt, source=Evaluation.Source.AI)
    order = attempt.access.order
    if order.mentor_id:
        Evaluation.objects.create(
            attempt=attempt, source=Evaluation.Source.MENTOR,
            mentor=order.mentor, due_at=now + timedelta(hours=12),
        )
        enqueue(order.mentor.user, "mentor_review_requested", f"mentor-review:{attempt.pk}", {"attempt_id": attempt.pk})
    return attempt


@transaction.atomic
def complete_mentor_evaluation(*, actor, evaluation_id):
    evaluation = Evaluation.objects.select_for_update().get(pk=evaluation_id, source=Evaluation.Source.MENTOR)
    if not actor.is_active or evaluation.mentor.user_id != actor.pk:
        raise PermissionDenied("Only the assigned mentor can submit this review.")
    if evaluation.status == Evaluation.Status.COMPLETED:
        return evaluation
    expected = set(evaluation.attempt.sections.values_list("pk", flat=True))
    results = list(SectionEvaluation.objects.filter(evaluation=evaluation))
    if {result.attempt_section_id for result in results} != expected:
        raise ValidationError("Review every purchased section before submitting feedback.")
    for result in results:
        result.full_clean()
        if result.band_score is None or not (result.feedback.strip() or result.audio_feedback):
            raise ValidationError("Each section needs a band score and text or audio feedback.")
    # Overall is only meaningful for a complete, four-skill mock.
    if len(expected) == 4 and evaluation.overall_band is None:
        raise ValidationError("A full mock needs an overall band.")
    evaluation.status, evaluation.completed_at = Evaluation.Status.COMPLETED, timezone.now()
    evaluation.full_clean()
    evaluation.save(update_fields=["status", "completed_at", "updated_at"])
    enqueue(evaluation.attempt.access.order.user, "mentor_feedback_ready", f"mentor-feedback:{evaluation.pk}", {"attempt_id": evaluation.attempt_id})
    return evaluation
