import importlib
from unittest import mock

from django.conf import settings
from django.test import TestCase, override_settings
from django.urls import clear_url_caches

from utils.testing import helpers
from utils import models as utils_models
from plugins.vae_workflow import logic, models
from plugins.vae_workflow import plugin_settings as vae_plugin_settings


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


@override_settings(URL_CONFIG="domain")
class TestNotificationDateTracking(TestCase):
    @classmethod
    def setUpTestData(cls):
        helpers.create_press()
        cls.journal_one, cls.journal_two = helpers.create_journals()
        helpers.create_roles(
            ["editor", "section-editor", "journal-manager", "author"],
        )
        vae_plugin_settings.install()
        clear_url_caches()
        importlib.reload(importlib.import_module(settings.ROOT_URLCONF))
        importlib.reload(importlib.import_module("core.include_urls"))

        cls.editor = helpers.create_editor(cls.journal_one)
        cls.vae_member = helpers.create_user(
            "vae-notify-date@example.com",
            journal=cls.journal_one,
            is_active=True,
        )
        models.VAEPoolMember.objects.create(
            journal=cls.journal_one,
            account=cls.vae_member,
        )

    def test_notify_vaes_pool_sets_date_last_notified(self):
        article = helpers.create_article(
            self.journal_one,
            title="Notify Date Tracking",
        )
        availability = models.ArticlePoolAvailability.objects.create(
            article=article,
            available=True,
        )
        self.assertIsNone(availability.date_last_notified)

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
            logic.notify_vaes_pool(request, article)

        availability.refresh_from_db()
        self.assertIsNotNone(availability.date_last_notified)

    @mock.patch("plugins.vae_workflow.logic.notify_vaes_pool")
    @mock.patch("plugins.vae_workflow.logic.has_preprint", return_value=True)
    def test_make_available_sets_both_dates(self, mock_preprint, mock_notify):
        article = helpers.create_article(
            self.journal_one,
            title="Make Available Dates",
        )
        request = mock.Mock()
        request.journal = self.journal_one
        request.user = self.editor
        request.META = {}

        availability = logic.make_available_for_pool(article, self.editor, request)

        self.assertIsNotNone(availability)
        self.assertIsNotNone(availability.date_made_available)
        self.assertIsNotNone(availability.date_last_notified)


@override_settings(URL_CONFIG="domain")
class TestConfirmationEmailLinkSetting(TestCase):
    @classmethod
    def setUpTestData(cls):
        helpers.create_press()
        cls.journal_one, cls.journal_two = helpers.create_journals()
        helpers.create_roles(
            ["editor", "section-editor", "journal-manager", "author"],
        )
        vae_plugin_settings.install()
        clear_url_caches()
        importlib.reload(importlib.import_module(settings.ROOT_URLCONF))
        importlib.reload(importlib.import_module("core.include_urls"))

    def test_confirmed_notification_contains_journal_url(self):
        from utils import setting_handler
        setting_value = setting_handler.get_setting(
            "plugin:vae_workflow",
            "vae_confirmed_notification",
            self.journal_one,
        ).processed_value
        self.assertIn("journal_url", setting_value)
