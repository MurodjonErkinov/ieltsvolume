from datetime import timedelta
from decimal import Decimal
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.utils import timezone

from accounts.models import Profile
from billing.models import AccessGrant, Order, PaymentAccount, PaymentReceipt
from billing.services import create_order, review_receipt, submit_receipt
from exams.models import Exam, MentorOffer, Question, QuestionGroup, Section
from notifications.models import Notification

from .models import Answer, Attempt, AttemptSection, Evaluation, SectionEvaluation
from .services import complete_mentor_evaluation, start_attempt, submit_attempt


class FoundationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        users = get_user_model()
        cls.student = users.objects.create_user("student", password="test-password")
        cls.other = users.objects.create_user("other", password="test-password")
        cls.admin = users.objects.create_superuser("admin", password="test-password")
        cls.mentor_user = users.objects.create_user("mentor", password="test-password")
        cls.mentor = Profile.objects.create(user=cls.mentor_user, role=Profile.Role.MENTOR)
        cls.exam = Exam.objects.create(title="Academic mock", slug="academic-1", price=100000, is_published=True)
        cls.section = Section.objects.create(exam=cls.exam, skill="reading", title="Reading", position=1, duration_seconds=3600)
        cls.group = QuestionGroup.objects.create(section=cls.section, position=1)
        cls.question = Question.objects.create(group=cls.group, kind="short_answer", prompt="Answer", position=1, answer_key=["answer"])
        cls.offer = MentorOffer.objects.create(exam=cls.exam, mentor=cls.mentor, surcharge=50000)
        cls.card = PaymentAccount.objects.create(label="Main", holder_name="Test", card_number="1234567812345678")

    def purchase(self, mentor=True):
        order = create_order(user=self.student, exam_id=self.exam.pk, mentor_offer_id=self.offer.pk if mentor else None)
        order.status = Order.Status.UNDER_REVIEW
        order.save()
        receipt = PaymentReceipt.objects.create(order=order, payment_account=self.card, image="private/receipts/test.png")
        review_receipt(actor=self.admin, receipt_id=receipt.pk, approve=True)
        return Order.objects.get(pk=order.pk), receipt

    def attempt(self, mentor=True):
        order, _ = self.purchase(mentor=mentor)
        return start_attempt(user=self.student, access_id=order.access.pk, acknowledged=True)

    def submitted(self, mentor=True):
        attempt = self.attempt(mentor=mentor)
        attempt.sections.update(submitted_at=timezone.now())
        return submit_attempt(user=self.student, attempt_id=attempt.pk)

    def test_checkout_snapshots_server_prices_and_mentor(self):
        order = create_order(user=self.student, exam_id=self.exam.pk, mentor_offer_id=self.offer.pk)
        self.assertEqual(order.total_amount, Decimal("150000"))
        self.assertEqual(order.mentor_id, self.mentor.pk)
        Exam.objects.filter(pk=self.exam.pk).update(price=200000)
        MentorOffer.objects.filter(pk=self.offer.pk).update(surcharge=80000)
        order.refresh_from_db()
        self.assertEqual(order.total_amount, Decimal("150000"))

    def test_mentor_offer_from_other_exam_cannot_be_purchased(self):
        second = Exam.objects.create(title="Other", slug="other", price=1, is_published=True)
        offer = MentorOffer.objects.create(exam=second, mentor=self.mentor, surcharge=1)
        with self.assertRaises(MentorOffer.DoesNotExist):
            create_order(user=self.student, exam_id=self.exam.pk, mentor_offer_id=offer.pk)

    def test_order_total_is_enforced_in_database(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Order.objects.create(user=self.student, exam=self.exam, exam_title="x", base_price=10, total_amount=1)

    def test_receipt_enqueues_both_admin_notifications(self):
        order = create_order(user=self.student, exam_id=self.exam.pk)
        with TemporaryDirectory() as media, override_settings(MEDIA_ROOT=media):
            submit_receipt(user=self.student, order_id=order.pk, payment_account_id=self.card.pk,
                           image=SimpleUploadedFile("receipt.png", b"fixture", content_type="image/png"))
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.UNDER_REVIEW)
        self.assertEqual(set(Notification.objects.filter(recipient=self.admin).values_list("channel", flat=True)), {"site", "telegram"})

    def test_receipt_approval_is_idempotent(self):
        order, receipt = self.purchase()
        review_receipt(actor=self.admin, receipt_id=receipt.pk, approve=True)
        self.assertEqual(AccessGrant.objects.filter(order=order).count(), 1)
        self.assertEqual(Notification.objects.filter(recipient=self.student, event="payment_approved").count(), 2)

    def test_unprivileged_user_cannot_approve_payment(self):
        order = create_order(user=self.student, exam_id=self.exam.pk)
        receipt = PaymentReceipt.objects.create(order=order, payment_account=self.card, image="x.png")
        with self.assertRaises(PermissionDenied):
            review_receipt(actor=self.student, receipt_id=receipt.pk, approve=True)
        self.assertFalse(AccessGrant.objects.exists())

    def test_rejected_receipt_does_not_grant_access(self):
        order = create_order(user=self.student, exam_id=self.exam.pk)
        order.status = Order.Status.UNDER_REVIEW
        order.save()
        receipt = PaymentReceipt.objects.create(order=order, payment_account=self.card, image="x.png")
        review_receipt(actor=self.admin, receipt_id=receipt.pk, approve=False, note="Payment not received")
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PENDING)
        self.assertFalse(AccessGrant.objects.exists())

    def test_pending_payment_cannot_pass_access_validation(self):
        order = create_order(user=self.student, exam_id=self.exam.pk)
        access = AccessGrant(order=order, granted_by=self.admin, granted_at=timezone.now())
        with self.assertRaises(ValidationError):
            access.full_clean()

    def test_access_requires_acknowledgement_and_correct_owner(self):
        order, _ = self.purchase()
        with self.assertRaises(ValidationError):
            start_attempt(user=self.student, access_id=order.access.pk)
        with self.assertRaises(AccessGrant.DoesNotExist):
            start_attempt(user=self.other, access_id=order.access.pk, acknowledged=True)

    def test_revoked_access_cannot_start(self):
        order, _ = self.purchase()
        AccessGrant.objects.filter(pk=order.access.pk).update(revoked_at=timezone.now())
        with self.assertRaises(PermissionDenied):
            start_attempt(user=self.student, access_id=order.access.pk, acknowledged=True)

    def test_resuming_does_not_reset_timer(self):
        attempt = self.attempt()
        deadline = attempt.sections.get().deadline_at
        resumed = start_attempt(user=self.student, access_id=attempt.access_id, acknowledged=True)
        self.assertEqual(resumed.pk, attempt.pk)
        self.assertEqual(resumed.sections.get().deadline_at, deadline)

    def test_single_attempt_is_enforced_in_database(self):
        attempt = self.attempt()
        with self.assertRaises(IntegrityError), transaction.atomic():
            Attempt.objects.create(access=attempt.access, started_at=timezone.now())

    def test_cannot_restart_completed_exam(self):
        attempt = self.submitted()
        with self.assertRaises(ValidationError):
            start_attempt(user=self.student, access_id=attempt.access_id, acknowledged=True)

    def test_all_sections_must_finish_before_submission(self):
        attempt = self.attempt()
        with self.assertRaises(ValidationError):
            submit_attempt(user=self.student, attempt_id=attempt.pk)
        self.assertFalse(Evaluation.objects.exists())

    def test_submission_creates_separate_evaluations_and_twelve_hour_deadline(self):
        attempt = self.submitted()
        submit_attempt(user=self.student, attempt_id=attempt.pk)
        self.assertEqual(attempt.evaluations.count(), 2)
        mentor = attempt.evaluations.get(source="mentor")
        self.assertEqual(mentor.mentor_id, self.mentor.pk)
        self.assertEqual(mentor.due_at, attempt.submitted_at + timedelta(hours=12))
        self.assertEqual(Notification.objects.filter(recipient=self.mentor_user).count(), 2)

    def test_ai_only_purchase_has_no_mentor_review(self):
        attempt = self.submitted(mentor=False)
        self.assertEqual(list(attempt.evaluations.values_list("source", flat=True)), ["ai"])

    def test_cross_exam_sections_and_answers_are_rejected(self):
        attempt = self.attempt()
        other_exam = Exam.objects.create(title="Other", slug="other", price=1)
        section = Section.objects.create(exam=other_exam, skill="reading", title="R", position=1, duration_seconds=60)
        with self.assertRaises(ValidationError):
            AttemptSection(attempt=attempt, section=section).full_clean()
        group = QuestionGroup.objects.create(section=section, position=1)
        question = Question.objects.create(group=group, kind="short_answer", prompt="Other", position=1, answer_key=["x"])
        with self.assertRaises(ValidationError):
            Answer(attempt_section=attempt.sections.get(), question=question).full_clean()

    def test_band_scores_require_half_point_steps(self):
        attempt = self.submitted()
        evaluation = attempt.evaluations.get(source="ai")
        with self.assertRaises(IntegrityError), transaction.atomic():
            Evaluation.objects.filter(pk=evaluation.pk).update(overall_band=Decimal("6.3"))
        evaluation.overall_band = Decimal("6.3")
        with self.assertRaises(ValidationError):
            evaluation.full_clean()

    def test_only_purchased_mentor_can_complete_review(self):
        evaluation = self.submitted().evaluations.get(source="mentor")
        with self.assertRaises(PermissionDenied):
            complete_mentor_evaluation(actor=self.other, evaluation_id=evaluation.pk)

    def test_mentor_must_review_every_section(self):
        evaluation = self.submitted().evaluations.get(source="mentor")
        with self.assertRaises(ValidationError):
            complete_mentor_evaluation(actor=self.mentor_user, evaluation_id=evaluation.pk)
        SectionEvaluation.objects.create(evaluation=evaluation, attempt_section=evaluation.attempt.sections.get(), band_score=7, feedback="Detailed feedback")
        completed = complete_mentor_evaluation(actor=self.mentor_user, evaluation_id=evaluation.pk)
        self.assertEqual(completed.status, Evaluation.Status.COMPLETED)
        self.assertEqual(Notification.objects.filter(recipient=self.student, event="mentor_feedback_ready").count(), 2)
