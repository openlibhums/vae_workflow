import importlib
from unittest import mock

from django.conf import settings
from django.test import TestCase, override_settings
from django.urls import clear_url_caches, reverse

from utils.testing import helpers
from plugins.vae_workflow import forms, models
from plugins.vae_workflow import plugin_settings as vae_plugin_settings


@override_settings(URL_CONFIG="domain")
class TestClaimFormCOI(TestCase):
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

    def test_claim_form_has_notes_field_labelled_coi(self):
        form = forms.ClaimForm()
        self.assertIn("notes", form.fields)
        self.assertEqual(form.fields["notes"].label, "Conflicts of Interest")

    def test_claim_form_empty_notes_is_invalid(self):
        form = forms.ClaimForm(data={"notes": ""})
        self.assertFalse(form.is_valid())
        self.assertIn("notes", form.errors)

    def test_claim_form_with_notes_is_valid(self):
        form = forms.ClaimForm(data={"notes": "None declared."})
        self.assertTrue(form.is_valid())


@override_settings(URL_CONFIG="domain")
class TestRejectClaimWithMessage(TestCase):
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
        cls.vae_user = helpers.create_user(
            "vae-reject-msg@example.com",
            journal=cls.journal_one,
            is_active=True,
        )
        models.VAEPoolMember.objects.create(
            journal=cls.journal_one,
            account=cls.vae_user,
        )
        cls.article = helpers.create_article(
            cls.journal_one,
            title="Reject Message Article",
            stage=vae_plugin_settings.STAGE,
        )
        models.ArticlePoolAvailability.objects.create(
            article=cls.article,
            available=True,
        )
        cls.claim = models.EditorClaim.objects.create(
            article=cls.article,
            claimed_by=cls.vae_user,
            status="pending",
        )

    @mock.patch("plugins.vae_workflow.logic.notify_rejected")
    def test_reject_with_message_passes_custom_message(self, mock_notify):
        self.client.force_login(self.editor)
        self.client.post(
            reverse("vae_article", kwargs={"article_id": self.article.pk}),
            data={
                "action": "reject",
                "claim_id": self.claim.pk,
                "message": "Custom rejection text",
            },
            SERVER_NAME=self.journal_one.domain,
        )
        mock_notify.assert_called_once()
        call_kwargs = mock_notify.call_args
        self.assertEqual(call_kwargs[1]["custom_message"], "Custom rejection text")

    @mock.patch("plugins.vae_workflow.logic.notify_rejected")
    def test_reject_without_message_passes_none(self, mock_notify):
        claim = models.EditorClaim.objects.create(
            article=self.article,
            claimed_by=self.vae_user,
            status="pending",
        )
        self.client.force_login(self.editor)
        self.client.post(
            reverse("vae_article", kwargs={"article_id": self.article.pk}),
            data={
                "action": "reject",
                "claim_id": claim.pk,
            },
            SERVER_NAME=self.journal_one.domain,
        )
        mock_notify.assert_called_once()
        call_kwargs = mock_notify.call_args
        self.assertIsNone(call_kwargs[1]["custom_message"])


@override_settings(URL_CONFIG="domain")
class TestRejectClaimFormEndpoint(TestCase):
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
        cls.vae_user = helpers.create_user(
            "vae-reject-form@example.com",
            journal=cls.journal_one,
            is_active=True,
        )
        cls.article = helpers.create_article(
            cls.journal_one,
            title="Reject Form Article",
            stage=vae_plugin_settings.STAGE,
        )
        cls.claim = models.EditorClaim.objects.create(
            article=cls.article,
            claimed_by=cls.vae_user,
            status="pending",
        )

    @mock.patch(
        "plugins.vae_workflow.htmx.render_template.get_message_content",
        return_value="Default rejection body",
    )
    def test_reject_claim_form_returns_form(self, mock_render):
        self.client.force_login(self.editor)
        response = self.client.get(
            reverse("vae_reject_claim_form", kwargs={"claim_id": self.claim.pk}),
            SERVER_NAME=self.journal_one.domain,
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("reject_form", response.context)


@override_settings(URL_CONFIG="domain")
class TestRescissionHelpText(TestCase):
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
        cls.vae_pending = helpers.create_section_editor(
            cls.journal_one,
            email="vae-pending-text@example.com",
        )
        models.VAEPoolMember.objects.create(
            journal=cls.journal_one,
            account=cls.vae_pending,
        )
        cls.vae_confirmed = helpers.create_section_editor(
            cls.journal_one,
            email="vae-confirmed-text@example.com",
        )
        models.VAEPoolMember.objects.create(
            journal=cls.journal_one,
            account=cls.vae_confirmed,
        )

        cls.pending_article = helpers.create_article(
            cls.journal_one,
            title="Pending Claim Article",
            stage=vae_plugin_settings.STAGE,
        )
        models.ArticlePoolAvailability.objects.create(
            article=cls.pending_article,
            available=True,
        )
        cls.pending_claim = models.EditorClaim.objects.create(
            article=cls.pending_article,
            claimed_by=cls.vae_pending,
            status="pending",
        )

        cls.confirmed_article = helpers.create_article(
            cls.journal_one,
            title="Confirmed Claim Article",
            stage=vae_plugin_settings.STAGE,
        )
        models.ArticlePoolAvailability.objects.create(
            article=cls.confirmed_article,
            available=True,
        )
        cls.confirmed_claim = models.EditorClaim.objects.create(
            article=cls.confirmed_article,
            claimed_by=cls.vae_confirmed,
            status="confirmed",
        )

    def test_pending_claim_shows_withdrawing_text(self):
        self.client.force_login(self.vae_pending)
        response = self.client.get(
            reverse(
                "vae_article",
                kwargs={"article_id": self.pending_article.pk},
            ),
            SERVER_NAME=self.journal_one.domain,
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Withdrawing removes")

    def test_confirmed_claim_shows_rescinding_text(self):
        self.client.force_login(self.vae_confirmed)
        response = self.client.get(
            reverse(
                "vae_article",
                kwargs={"article_id": self.confirmed_article.pk},
            ),
            SERVER_NAME=self.journal_one.domain,
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Rescinding removes")


@override_settings(URL_CONFIG="domain")
class TestConfirmClaimMovesToReview(TestCase):
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
        cls.vae_user = helpers.create_user(
            "vae-confirm-stage@example.com",
            journal=cls.journal_one,
            is_active=True,
        )
        models.VAEPoolMember.objects.create(
            journal=cls.journal_one,
            account=cls.vae_user,
        )

    @mock.patch("events.logic.Events.raise_event")
    @mock.patch("plugins.vae_workflow.logic.notify_confirmed")
    @mock.patch("plugins.vae_workflow.logic._send_email")
    def test_confirm_advances_workflow(
        self, mock_send, mock_notify, mock_raise_event,
    ):
        from django.http import HttpResponseRedirect
        mock_raise_event.return_value = HttpResponseRedirect("/")

        article = helpers.create_article(
            self.journal_one,
            title="Confirm Stage Article",
            stage=vae_plugin_settings.STAGE,
        )
        models.ArticlePoolAvailability.objects.create(
            article=article,
            available=True,
        )
        claim = models.EditorClaim.objects.create(
            article=article,
            claimed_by=self.vae_user,
            status="pending",
        )
        self.client.force_login(self.editor)
        self.client.post(
            reverse("vae_article", kwargs={"article_id": article.pk}),
            data={"action": "confirm", "claim_id": claim.pk},
            SERVER_NAME=self.journal_one.domain,
        )
        claim.refresh_from_db()
        self.assertEqual(claim.status, "confirmed")
        mock_raise_event.assert_called_once()
        kwargs = mock_raise_event.call_args.kwargs
        self.assertEqual(kwargs.get("handshake_url"), "vae_articles")
        self.assertTrue(kwargs.get("switch_stage"))
