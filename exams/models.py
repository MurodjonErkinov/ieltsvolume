from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models

from common.models import TimestampedModel, nonnegative, positive


class Exam(TimestampedModel):
    """Academic mock. Its sections determine whether it is full or partial."""

    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=14, decimal_places=2, validators=[MinValueValidator(0)])
    currency = models.CharField(max_length=3, default="UZS")
    is_published = models.BooleanField(default=False)
    published_at = models.DateTimeField(null=True, blank=True)
    version = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])
    previous_version = models.ForeignKey("self", on_delete=models.PROTECT, null=True, blank=True, related_name="versions")

    class Meta:
        constraints = [nonnegative("price"), positive("version")]
        indexes = [models.Index(fields=["is_published", "-created_at"])]

    def __str__(self):
        return self.title


class MentorOffer(TimestampedModel):
    exam = models.ForeignKey(Exam, on_delete=models.PROTECT, related_name="mentor_offers")
    mentor = models.ForeignKey("accounts.Profile", on_delete=models.PROTECT, related_name="offers")
    surcharge = models.DecimalField(max_digits=14, decimal_places=2, validators=[MinValueValidator(0)])
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["exam", "mentor"], name="unique_exam_mentor_offer"),
            nonnegative("surcharge"),
        ]

    def clean(self):
        super().clean()
        if self.mentor_id and self.mentor.role != "mentor":
            raise ValidationError({"mentor": "Select a mentor profile."})


class Section(models.Model):
    class Skill(models.TextChoices):
        LISTENING = "listening", "Listening"
        READING = "reading", "Reading"
        WRITING = "writing", "Writing"
        SPEAKING = "speaking", "Speaking"

    exam = models.ForeignKey(Exam, on_delete=models.PROTECT, related_name="sections")
    skill = models.CharField(max_length=10, choices=Skill)
    title = models.CharField(max_length=255)
    instructions = models.TextField(blank=True)
    position = models.PositiveSmallIntegerField(validators=[MinValueValidator(1)])
    duration_seconds = models.PositiveIntegerField(validators=[MinValueValidator(1)])

    class Meta:
        ordering = ["position"]
        constraints = [
            models.UniqueConstraint(fields=["exam", "position"], name="unique_exam_section_position"),
            models.UniqueConstraint(fields=["exam", "skill"], name="unique_exam_skill"),
            positive("position"), positive("duration_seconds"),
        ]

    def __str__(self):
        return f"{self.exam}: {self.get_skill_display()}"


class QuestionGroup(models.Model):
    section = models.ForeignKey(Section, on_delete=models.PROTECT, related_name="groups")
    title = models.CharField(max_length=255, blank=True)
    content = models.TextField(blank=True)
    asset = models.FileField(upload_to="exam-assets/%Y/%m/", blank=True)
    position = models.PositiveSmallIntegerField(validators=[MinValueValidator(1)])
    preparation_seconds = models.PositiveIntegerField(default=0)
    response_seconds = models.PositiveIntegerField(null=True, blank=True, validators=[MinValueValidator(1)])

    class Meta:
        ordering = ["position"]
        constraints = [
            models.UniqueConstraint(fields=["section", "position"], name="unique_section_group_position"),
            positive("position"), positive("response_seconds"),
        ]


class Question(models.Model):
    class Kind(models.TextChoices):
        SINGLE_CHOICE = "single_choice", "Single choice"
        MULTIPLE_CHOICE = "multiple_choice", "Multiple choice"
        SHORT_ANSWER = "short_answer", "Short answer / completion"
        TRUE_FALSE_NOT_GIVEN = "true_false_not_given", "True / False / Not given"
        YES_NO_NOT_GIVEN = "yes_no_not_given", "Yes / No / Not given"
        MATCHING = "matching", "Matching"
        ESSAY = "essay", "Writing task"
        AUDIO_RESPONSE = "audio_response", "Speaking response"

    group = models.ForeignKey(QuestionGroup, on_delete=models.PROTECT, related_name="questions")
    kind = models.CharField(max_length=25, choices=Kind)
    prompt = models.TextField()
    position = models.PositiveSmallIntegerField(validators=[MinValueValidator(1)])
    max_score = models.DecimalField(max_digits=7, decimal_places=2, default=1, validators=[MinValueValidator(Decimal("0.01"))])
    answer_key = models.JSONField(null=True, blank=True, help_text="Private. Never expose during an active attempt.")
    explanation = models.TextField(blank=True)
    config = models.JSONField(default=dict, blank=True, help_text="Word limits, matching layout, Writing task weight, etc.")

    class Meta:
        ordering = ["position"]
        constraints = [
            models.UniqueConstraint(fields=["group", "position"], name="unique_group_question_position"),
            positive("position"), positive("max_score"),
        ]

    def clean(self):
        super().clean()
        if self.kind in {self.Kind.ESSAY, self.Kind.AUDIO_RESPONSE} and self.answer_key is not None:
            raise ValidationError({"answer_key": "Writing and Speaking use assessment, not an answer key."})
        if self.group_id:
            skill = self.group.section.skill
            expected = {Section.Skill.WRITING: self.Kind.ESSAY, Section.Skill.SPEAKING: self.Kind.AUDIO_RESPONSE}
            if skill in expected and self.kind != expected[skill]:
                raise ValidationError({"kind": "Question type does not match this section."})
            if skill in {Section.Skill.READING, Section.Skill.LISTENING}:
                if self.kind in expected.values() or self.answer_key is None:
                    raise ValidationError("Reading/Listening require an objective question and answer key.")


class QuestionOption(models.Model):
    question = models.ForeignKey(Question, on_delete=models.PROTECT, related_name="options")
    label = models.CharField(max_length=20)
    content = models.TextField()
    position = models.PositiveSmallIntegerField(validators=[MinValueValidator(1)])

    class Meta:
        ordering = ["position"]
        constraints = [
            models.UniqueConstraint(fields=["question", "label"], name="unique_question_option_label"),
            models.UniqueConstraint(fields=["question", "position"], name="unique_question_option_position"),
            positive("position"),
        ]
