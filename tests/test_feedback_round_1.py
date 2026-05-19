import importlib
from unittest import mock

from django.conf import settings
from django.test import TestCase, override_settings
from django.urls import clear_url_caches, reverse

from utils.testing import helpers
from utils import models as utils_models
from plugins.vae_workflow import logic, models, views
from plugins.vae_workflow import plugin_settings as vae_plugin_settings


@override_settings(URL_CONFIG="domain")
class TestDashboardTemplateSetting(TestCase):
    def test_dashboard_template_setting_present(self):
        self.assertEqual(
            vae_plugin_settings.DASHBOARD_TEMPLATE,
            "vae_workflow/elements/dashboard.html",
        )


@override_settings(URL_CONFIG="domain")
class TestDashboardCounts(TestCase):
    @classmethod
    def setUpTestData(cls):
        helpers.create_press()
        cls.journal_one, cls.journal_two = helpers.create_journals()
        helpers.create_roles(["editor", "author"])
        vae_plugin_settings.install()

        cls.awaiting_article = helpers.create_article(
            cls.journal_one,
            title="Awaiting Release",
        )
        cls.awaiting_article.stage = vae_plugin_settings.STAGE
        cls.awaiting_article.save()
        models.ArticlePoolAvailability.objects.get_or_create(
            article=cls.awaiting_article,
            defaults={"available": False},
        )

        cls.available_article = helpers.create_article(
            cls.journal_one,
            title="Available to Claim",
        )
        cls.available_article.stage = vae_plugin_settings.STAGE
        cls.available_article.save()
        availability, _ = models.ArticlePoolAvailability.objects.get_or_create(
            article=cls.available_article,
        )
        availability.available = True
        availability.save()

        cls.confirmed_article = helpers.create_article(
            cls.journal_one,
            title="Confirmed Article",
        )
        cls.confirmed_user = helpers.create_user(
            "confirmed-vae@example.com",
            journal=cls.journal_one,
            is_active=True,
        )
        models.EditorClaim.objects.create(
            article=cls.confirmed_article,
            claimed_by=cls.confirmed_user,
            status="confirmed",
        )

    def test_dashboard_counts_returns_expected_keys(self):
        counts = views.dashboard_counts(self.journal_one)
        self.assertEqual(counts["awaiting_release"], 1)
        self.assertEqual(counts["available_to_claim"], 1)
        self.assertEqual(counts["confirmed_claims"], 1)


@override_settings(URL_CONFIG="domain")
class TestOverviewView(TestCase):
    @classmethod
    def setUpTestData(cls):
        helpers.create_press()
        cls.journal_one, cls.journal_two = helpers.create_journals()
        helpers.create_roles(["editor", "author"])
        vae_plugin_settings.install()
        clear_url_caches()
        importlib.reload(importlib.import_module(settings.ROOT_URLCONF))
        importlib.reload(importlib.import_module("core.include_urls"))

        cls.editor = helpers.create_editor(cls.journal_one)
        cls.author = helpers.create_author(cls.journal_one)

        cls.claimed_article = helpers.create_article(
            cls.journal_one,
            title="Claimed Article",
        )
        cls.claimant = helpers.create_user(
            "vae-overview@example.com",
            journal=cls.journal_one,
            is_active=True,
        )
        models.EditorClaim.objects.create(
            article=cls.claimed_article,
            claimed_by=cls.claimant,
            status="confirmed",
        )

        cls.released_article = helpers.create_article(
            cls.journal_one,
            title="Released Article",
        )
        availability, _ = models.ArticlePoolAvailability.objects.get_or_create(
            article=cls.released_article,
        )
        availability.available = True
        availability.save()

        cls.uninvolved_article = helpers.create_article(
            cls.journal_one,
            title="Uninvolved Article",
        )

    def test_overview_requires_editor(self):
        self.client.force_login(self.author)
        response = self.client.get(
            reverse("vae_overview"),
            SERVER_NAME=self.journal_one.domain,
        )
        self.assertNotEqual(response.status_code, 200)

    def test_overview_lists_claimed_and_released_articles(self):
        self.client.force_login(self.editor)
        response = self.client.get(
            reverse("vae_overview"),
            SERVER_NAME=self.journal_one.domain,
        )
        self.assertEqual(response.status_code, 200)

        flat_articles = [
            article
            for _, articles in response.context["grouped_articles"]
            for article in articles
        ]
        flat_ids = {article.pk for article in flat_articles}
        self.assertIn(self.claimed_article.pk, flat_ids)
        self.assertIn(self.released_article.pk, flat_ids)
        self.assertNotIn(self.uninvolved_article.pk, flat_ids)


@override_settings(URL_CONFIG="domain")
class TestMakeAvailablePreprintGuard(TestCase):
    @classmethod
    def setUpTestData(cls):
        helpers.create_press()
        cls.journal_one, cls.journal_two = helpers.create_journals()
        helpers.create_roles(["editor", "author"])
        vae_plugin_settings.install()
        clear_url_caches()
        importlib.reload(importlib.import_module(settings.ROOT_URLCONF))
        importlib.reload(importlib.import_module("core.include_urls"))

        cls.editor = helpers.create_editor(cls.journal_one)
        cls.assigned_editor = helpers.create_editor(
            cls.journal_one,
            email="assigned-preprint@example.com",
        )
        cls.article = helpers.create_article(
            cls.journal_one,
            title="Preprint Guard Article",
        )
        helpers.create_editor_assignment(cls.article, cls.assigned_editor)

    def article_url(self):
        return reverse("vae_article", kwargs={"article_id": self.article.pk})

    @mock.patch("plugins.vae_workflow.views.logic.has_preprint", return_value=False)
    def test_make_available_blocked_without_preprint(self, mock_has):
        with mock.patch(
            "plugins.vae_workflow.logic.notify_helpers.send_email_with_body_from_user",
        ) as mock_email:
            self.client.force_login(self.editor)
            response = self.client.post(
                self.article_url(),
                data={"action": "make_available"},
                SERVER_NAME=self.journal_one.domain,
            )
        self.assertEqual(response.status_code, 302)
        availability = models.ArticlePoolAvailability.objects.get(
            article=self.article,
        )
        self.assertFalse(availability.available)
        mock_email.assert_not_called()

    @mock.patch("plugins.vae_workflow.views.logic.has_preprint", return_value=True)
    @mock.patch("plugins.vae_workflow.logic.has_preprint", return_value=True)
    @mock.patch("plugins.vae_workflow.logic.notify_vaes_pool")
    def test_make_available_succeeds_with_preprint(
        self, mock_notify, mock_logic_has, mock_view_has,
    ):
        self.client.force_login(self.editor)
        response = self.client.post(
            self.article_url(),
            data={"action": "make_available"},
            SERVER_NAME=self.journal_one.domain,
        )
        self.assertEqual(response.status_code, 302)
        availability = models.ArticlePoolAvailability.objects.get(
            article=self.article,
        )
        self.assertTrue(availability.available)
        mock_notify.assert_called_once()


@override_settings(URL_CONFIG="domain")
class TestNotifyVAEsAuditLog(TestCase):
    @classmethod
    def setUpTestData(cls):
        helpers.create_press()
        cls.journal_one, cls.journal_two = helpers.create_journals()
        helpers.create_roles(["editor", "author"])
        vae_plugin_settings.install()

        cls.editor = helpers.create_editor(cls.journal_one)
        cls.vae_one = helpers.create_user(
            "vae-audit-1@example.com",
            journal=cls.journal_one,
            is_active=True,
        )
        cls.vae_two = helpers.create_user(
            "vae-audit-2@example.com",
            journal=cls.journal_one,
            is_active=True,
        )
        models.VAEPoolMember.objects.create(
            journal=cls.journal_one,
            account=cls.vae_one,
        )
        models.VAEPoolMember.objects.create(
            journal=cls.journal_one,
            account=cls.vae_two,
        )
        cls.article = helpers.create_article(
            cls.journal_one,
            title="Audit Article",
        )

    def test_notify_vaes_pool_writes_audit_log(self):
        request = mock.Mock()
        request.journal = self.journal_one
        request.user = self.editor
        request.META = {}

        with mock.patch(
            "plugins.vae_workflow.logic.notify_helpers.send_email_with_body_from_user",
        ), mock.patch(
            "plugins.vae_workflow.logic.render_template.get_message_content",
            return_value="body",
        ), mock.patch(
            "plugins.vae_workflow.logic._get_setting",
            return_value="template body",
        ):
            logic.notify_vaes_pool(request, self.article)

        entries = utils_models.LogEntry.objects.filter(
            types="VAE Workflow",
            object_id=self.article.pk,
        )
        self.assertEqual(entries.count(), 1)
        self.assertIn("2", entries.first().description)
