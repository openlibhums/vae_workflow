from django.test import TestCase, override_settings

from core import models as core_models
from events import logic as event_logic
from submission import models as submission_models
from utils.testing import helpers
from plugins.vae_workflow import logic, models
from plugins.vae_workflow import plugin_settings as vae_plugin_settings


@override_settings(URL_CONFIG="domain")
class TestReturnToVAEAfterPreReviewRevision(TestCase):
    @classmethod
    def setUpTestData(cls):
        helpers.create_press()
        cls.journal_one, cls.journal_two = helpers.create_journals()
        helpers.create_roles(["editor", "section-editor", "author"])
        vae_plugin_settings.install()
        cls.editor = helpers.create_editor(cls.journal_one)
        cls.vae = helpers.create_user(
            "vae@example.com",
            ["section-editor"],
            journal=cls.journal_one,
        )
        cls.vae_element = core_models.WorkflowElement.objects.create(
            journal=cls.journal_one,
            element_name=vae_plugin_settings.PLUGIN_NAME,
            handshake_url=vae_plugin_settings.HANDSHAKE_URL,
            jump_url=vae_plugin_settings.JUMP_URL,
            stage=vae_plugin_settings.STAGE,
        )
        cls.review_element = core_models.WorkflowElement.objects.create(
            journal=cls.journal_one,
            element_name="review",
            handshake_url="review_home",
            jump_url="review_in_review",
            stage=submission_models.STAGE_UNASSIGNED,
        )

    def setUp(self):
        self.article = helpers.create_article(self.journal_one)
        core_models.WorkflowLog.objects.create(
            article=self.article,
            element=self.vae_element,
        )
        self.article.stage = submission_models.STAGE_UNDER_REVISION
        self.article.save()
        self.revision = helpers.create_revision_request(
            self.article,
            self.editor,
        )

    def test_pre_review_revision_returns_to_vae_stage(self):
        logic.return_to_vae_after_pre_review_revision(revision=self.revision)
        self.article.refresh_from_db()
        self.assertEqual(self.article.stage, vae_plugin_settings.STAGE)

    def test_return_does_not_change_pool_availability(self):
        availability, _ = models.ArticlePoolAvailability.objects.get_or_create(
            article=self.article,
        )
        availability.available = True
        availability.save()
        logic.return_to_vae_after_pre_review_revision(revision=self.revision)
        availability.refresh_from_db()
        self.assertTrue(availability.available)

    def test_claimed_article_stays_in_review(self):
        models.EditorClaim.objects.create(
            article=self.article,
            claimed_by=self.vae,
            status="confirmed",
        )
        logic.return_to_vae_after_pre_review_revision(revision=self.revision)
        self.article.refresh_from_db()
        self.assertEqual(
            self.article.stage,
            submission_models.STAGE_UNDER_REVISION,
        )

    def test_article_that_entered_review_stays_in_review(self):
        core_models.WorkflowLog.objects.create(
            article=self.article,
            element=self.review_element,
        )
        logic.return_to_vae_after_pre_review_revision(revision=self.revision)
        self.article.refresh_from_db()
        self.assertEqual(
            self.article.stage,
            submission_models.STAGE_UNDER_REVISION,
        )

    def test_article_with_review_assignments_stays_in_review(self):
        helpers.create_review_assignment(
            journal=self.journal_one,
            article=self.article,
            editor=self.editor,
        )
        logic.return_to_vae_after_pre_review_revision(revision=self.revision)
        self.article.refresh_from_db()
        self.assertEqual(
            self.article.stage,
            submission_models.STAGE_UNDER_REVISION,
        )

    def test_article_not_under_revision_is_left_alone(self):
        self.article.stage = submission_models.STAGE_UNDER_REVIEW
        self.article.save()
        logic.return_to_vae_after_pre_review_revision(revision=self.revision)
        self.article.refresh_from_db()
        self.assertEqual(
            self.article.stage,
            submission_models.STAGE_UNDER_REVIEW,
        )

    def test_handler_is_registered_for_revisions_complete(self):
        self.assertIn(
            logic.return_to_vae_after_pre_review_revision,
            event_logic.Events._hooks.get(
                event_logic.Events.ON_REVISIONS_COMPLETE,
                [],
            ),
        )
