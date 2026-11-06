import uuid

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import F, Q

from common.models import TimestampedModel, band_constraint, nonnegative, validate_band


def audio_path(instance, filename):
    extension = filename.rsplit(".", 1)[-1].lower()
    return f"private/audio/{uuid.uuid4()}.{extension}"


class Attempt(TimestampedModel):
    class Status(models.TextChoices):
        IN_PROGRESS = "in_progress", "In progress"
        SUBMITTED = "submitted", "Submitted"

    access = models.OneToOneField("billing.AccessGrant", on_delete=models.PROTECT, related_name="attempt")
    status = models.CharField(max_length=15, choices=Status, default=Status.IN_PROGRESS)
    started_at = models.DateTimeField()
    submitted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(status="in_progress", submitted_at__isnull=True)
                | Q(status="submitted", submitted_at__gte=F("started_at")),
                name="attempt_submission_state_valid",
            ),
            models.CheckConstraint(condition=~Q(status="submitted") | Q(submitted_at__isnull=False), name="submitted_attempt_has_time"),
        ]


class AttemptSection(TimestampedModel):
    attempt = models.ForeignKey(Attempt, on_delete=models.PROTECT, related_name="sections")
    section = models.ForeignKey("exams.Section", on_delete=models.PROTECT, related_name="attempt_sections")
    started_at = models.DateTimeField(null=True, blank=True)
    deadline_at = models.DateTimeField(null=True, blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["attempt", "section"], name="unique_attempt_section"),
            models.CheckConstraint(
                condition=Q(started_at__isnull=True, deadline_at__isnull=True)
                | Q(started_at__isnull=False, deadline_at__isnull=False, deadline_at__gt=F("started_at")),
                name="section_deadline_valid",
            ),
            models.CheckConstraint(
                condition=Q(submitted_at__isnull=True) | Q(started_at__isnull=False, submitted_at__gte=F("started_at")),
                name="section_submission_time_valid",
            ),
        ]

    def clean(self):
        super().clean()
        if self.attempt_id and self.section_id and self.section.exam_id != self.attempt.access.order.exam_id:
            raise ValidationError({"section": "Section must belong to the purchased exam."})


class Answer(TimestampedModel):
    attempt_section = models.ForeignKey(AttemptSection, on_delete=models.PROTECT, related_name="answers")
    question = models.ForeignKey("exams.Question", on_delete=models.PROTECT, related_name="answers")
    response = models.JSONField(default=dict, blank=True)
    audio = models.FileField(upload_to=audio_path, blank=True)
    recording_started_at = models.DateTimeField(null=True, blank=True)
    recording_submitted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["attempt_section", "question"], name="unique_section_question_answer"),
            models.CheckConstraint(
                condition=Q(recording_submitted_at__isnull=True)
                | Q(recording_started_at__isnull=False, recording_submitted_at__gte=F("recording_started_at")),
                name="recording_submission_time_valid",
            ),
        ]

    def clean(self):
        super().clean()
        if self.attempt_section_id and self.question_id and self.question.group.section_id != self.attempt_section.section_id:
            raise ValidationError({"question": "Question must belong to the attempted section."})


class Evaluation(TimestampedModel):
    class Source(models.TextChoices):
        AI = "ai", "AI"
        MENTOR = "mentor", "Mentor"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PROCESSING = "processing", "Processing"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

    attempt = models.ForeignKey(Attempt, on_delete=models.PROTECT, related_name="evaluations")
    source = models.CharField(max_length=6, choices=Source)
    mentor = models.ForeignKey("accounts.Profile", on_delete=models.PROTECT, null=True, blank=True, related_name="evaluations")
    status = models.CharField(max_length=12, choices=Status, default=Status.PENDING)
    overall_band = models.DecimalField(max_digits=2, decimal_places=1, null=True, blank=True, validators=[validate_band])
    feedback = models.TextField(blank=True)
    due_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    # Model/prompt version and criteria make AI results auditable.
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        indexes = [models.Index(fields=["mentor", "status", "due_at"])]
        constraints = [
            models.UniqueConstraint(fields=["attempt", "source"], name="unique_attempt_evaluation_source"),
            models.CheckConstraint(
                condition=Q(source="ai", mentor__isnull=True, due_at__isnull=True)
                | Q(source="mentor", mentor__isnull=False, due_at__isnull=False),
                name="evaluation_source_matches_mentor",
            ),
            models.CheckConstraint(condition=~Q(status="completed") | Q(completed_at__isnull=False), name="completed_evaluation_has_time"),
            band_constraint("overall_band"),
        ]

    def clean(self):
        super().clean()
        if self.source == self.Source.MENTOR and self.attempt_id:
            purchased_mentor = self.attempt.access.order.mentor_id
            if not purchased_mentor or self.mentor_id != purchased_mentor:
                raise ValidationError({"mentor": "Only the purchased mentor may review this attempt."})
        if self.attempt_id and self.attempt.status != Attempt.Status.SUBMITTED:
            raise ValidationError({"attempt": "Submit the attempt before evaluating it."})


class SectionEvaluation(TimestampedModel):
    evaluation = models.ForeignKey(Evaluation, on_delete=models.PROTECT, related_name="sections")
    attempt_section = models.ForeignKey(AttemptSection, on_delete=models.PROTECT, related_name="evaluations")
    raw_score = models.DecimalField(max_digits=9, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0)])
    band_score = models.DecimalField(max_digits=2, decimal_places=1, null=True, blank=True, validators=[validate_band])
    feedback = models.TextField(blank=True)
    audio_feedback = models.FileField(upload_to=audio_path, blank=True)
    criteria = models.JSONField(default=dict, blank=True, help_text="Writing/Speaking criterion scores and explanations.")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["evaluation", "attempt_section"], name="unique_evaluation_section"),
            nonnegative("raw_score"), band_constraint("band_score"),
        ]

    def clean(self):
        super().clean()
        if self.evaluation_id and self.attempt_section_id and self.evaluation.attempt_id != self.attempt_section.attempt_id:
            raise ValidationError({"attempt_section": "Section must belong to this evaluation's attempt."})


class AnswerEvaluation(TimestampedModel):
    section_evaluation = models.ForeignKey(SectionEvaluation, on_delete=models.PROTECT, related_name="answers")
    answer = models.ForeignKey(Answer, on_delete=models.PROTECT, related_name="evaluations")
    score = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0)])
    feedback = models.TextField(blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["section_evaluation", "answer"], name="unique_evaluation_answer"),
            nonnegative("score"),
        ]

    def clean(self):
        super().clean()
        if self.answer_id:
            if self.section_evaluation_id and self.answer.attempt_section_id != self.section_evaluation.attempt_section_id:
                raise ValidationError({"answer": "Answer must belong to this evaluated section."})
            if self.score is not None and self.score > self.answer.question.max_score:
                raise ValidationError({"score": "Score exceeds the question's maximum."})
