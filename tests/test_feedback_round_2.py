import importlib
from unittest import mock

from django.conf import settings
from django.db import IntegrityError
from django.test import TestCase, override_settings
from django.urls import clear_url_caches, reverse
from django.utils import timezone

from submission import models as submission_models
from utils.testing import helpers
from plugins.vae_workflow import forms, logic, models
from plugins.vae_workflow import plugin_settings as vae_plugin_settings


def setup_plugin():
    helpers.create_roles(
        ["editor", "section-editor", "journal-manager", "author"],
    )
    vae_plugin_settings.install()
    clear_url_caches()
    importlib.reload(importlib.import_module(settings.ROOT_URLCONF))
    importlib.reload(importlib.import_module("core.include_urls"))


@override_settings(URL_CONFIG="domain")
class TestEditorAssignmentContext(TestCase):
    @classmethod
    def setUpTestData(cls):
        helpers.create_press()
        cls.journal_one, cls.journal_two = helpers.create_journals()
        setup_plugin()

        cls.editor = helpers.create_editor(cls.journal_one)
        cls.article = helpers.create_article(
            cls.journal_one,
            title="Editor Assignment Context",
            stage=vae_plugin_settings.STAGE,
        )
        cls.assigned_editor = helpers.create_editor(
            cls.journal_one,
            email="assigned-editor-ctx@example.com",
        )
        cls.assignment = helpers.create_editor_assignment(
            cls.article,
            cls.assigned_editor,
        )

    def test_article_view_includes_editor_assignments(self):
        self.client.force_login(self.editor)
        response = self.client.get(
            reverse("vae_article", kwargs={"article_id": self.article.pk}),
            SERVER_NAME=self.journal_one.domain,
        )
        self.assertEqual(response.status_code, 200)
        assignments = list(response.context["editor_assignments"])
        self.assertEqual(len(assignments), 1)
        self.assertEqual(assignments[0].editor, self.assigned_editor)

    def test_article_view_lists_multiple_editor_assignments(self):
        second_editor = helpers.create_editor(
            self.journal_one,
            email="second-editor-ctx@example.com",
        )
        helpers.create_editor_assignment(self.article, second_editor)
        self.client.force_login(self.editor)
        response = self.client.get(
            reverse("vae_article", kwargs={"article_id": self.article.pk}),
            SERVER_NAME=self.journal_one.domain,
        )
        self.assertEqual(response.status_code, 200)
        assigned_editors = [
            ea.editor for ea in response.context["editor_assignments"]
        ]
        self.assertIn(self.assigned_editor, assigned_editors)
        self.assertIn(second_editor, assigned_editors)

    def test_article_view_editor_assignments_empty_when_unassigned(self):
        unassigned_article = helpers.create_article(
            self.journal_one,
            title="No Editor Assigned",
            stage=vae_plugin_settings.STAGE,
        )
        self.client.force_login(self.editor)
        response = self.client.get(
            reverse("vae_article", kwargs={"article_id": unassigned_article.pk}),
            SERVER_NAME=self.journal_one.domain,
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(list(response.context["editor_assignments"]))


@override_settings(URL_CONFIG="domain")
class TestNotificationDateTracking(TestCase):
    @classmethod
    def setUpTestData(cls):
        helpers.create_press()
        cls.journal_one, cls.journal_two = helpers.create_journals()
        setup_plugin()

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
class TestIsolinearUrlContext(TestCase):
    @classmethod
    def setUpTestData(cls):
        helpers.create_press()
        cls.journal_one, cls.journal_two = helpers.create_journals()
        setup_plugin()

        cls.editor = helpers.create_editor(cls.journal_one)
        cls.article = helpers.create_article(
            cls.journal_one,
            title="Isolinear URL Context",
            stage=vae_plugin_settings.STAGE,
        )

    def test_article_view_contains_isolinear_url_key(self):
        self.client.force_login(self.editor)
        response = self.client.get(
            reverse("vae_article", kwargs={"article_id": self.article.pk}),
            SERVER_NAME=self.journal_one.domain,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("isolinear_url", response.context)


@override_settings(URL_CONFIG="domain")
class TestClaimFormCOI(TestCase):
    @classmethod
    def setUpTestData(cls):
        helpers.create_press()
        cls.journal_one, cls.journal_two = helpers.create_journals()
        setup_plugin()

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
        setup_plugin()

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
        setup_plugin()

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
class TestHiddenRejectedVAENames(TestCase):
    @classmethod
    def setUpTestData(cls):
        helpers.create_press()
        cls.journal_one, cls.journal_two = helpers.create_journals()
        setup_plugin()

        cls.editor = helpers.create_editor(cls.journal_one)
        cls.vae_pool_member = helpers.create_section_editor(
            cls.journal_one,
            email="vae-hidden-reject@example.com",
        )
        models.VAEPoolMember.objects.create(
            journal=cls.journal_one,
            account=cls.vae_pool_member,
        )
        cls.rejected_vae = helpers.create_user(
            "rejected-vae@example.com",
            journal=cls.journal_one,
            is_active=True,
            first_name="RejectedFirst",
            last_name="RejectedLast",
        )
        cls.article = helpers.create_article(
            cls.journal_one,
            title="Hidden Rejected Article",
            stage=vae_plugin_settings.STAGE,
        )
        models.ArticlePoolAvailability.objects.create(
            article=cls.article,
            available=True,
        )
        models.EditorClaim.objects.create(
            article=cls.article,
            claimed_by=cls.rejected_vae,
            status="rejected",
        )

    def test_non_editor_vae_does_not_see_rejected_names(self):
        self.client.force_login(self.vae_pool_member)
        response = self.client.get(
            reverse("vae_articles"),
            SERVER_NAME=self.journal_one.domain,
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "RejectedFirst")

    def test_editor_sees_rejected_claim_names(self):
        self.client.force_login(self.editor)
        response = self.client.get(
            reverse("vae_articles"),
            SERVER_NAME=self.journal_one.domain,
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "RejectedFirst")


@override_settings(URL_CONFIG="domain")
class TestConfirmationEmailLinkSetting(TestCase):
    @classmethod
    def setUpTestData(cls):
        helpers.create_press()
        cls.journal_one, cls.journal_two = helpers.create_journals()
        setup_plugin()

    def test_confirmed_notification_contains_journal_url(self):
        from utils import setting_handler
        setting_value = setting_handler.get_setting(
            "plugin:vae_workflow",
            "vae_confirmed_notification",
            self.journal_one,
        ).processed_value
        self.assertIn("journal_url", setting_value)


@override_settings(URL_CONFIG="domain")
class TestRescissionHelpText(TestCase):
    @classmethod
    def setUpTestData(cls):
        helpers.create_press()
        cls.journal_one, cls.journal_two = helpers.create_journals()
        setup_plugin()

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
        setup_plugin()

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


@override_settings(URL_CONFIG="domain")
class TestEnsureDefaultChecklistSteps(TestCase):
    @classmethod
    def setUpTestData(cls):
        helpers.create_press()
        cls.journal_one, cls.journal_two = helpers.create_journals()
        setup_plugin()

    def test_creates_five_default_steps(self):
        models.ChecklistStep.objects.filter(journal=self.journal_one).delete()
        steps = logic.ensure_default_checklist_steps(self.journal_one)
        self.assertEqual(steps.count(), 5)

    def test_idempotent_does_not_duplicate(self):
        models.ChecklistStep.objects.filter(journal=self.journal_one).delete()
        logic.ensure_default_checklist_steps(self.journal_one)
        logic.ensure_default_checklist_steps(self.journal_one)
        count = models.ChecklistStep.objects.filter(journal=self.journal_one).count()
        self.assertEqual(count, 5)


@override_settings(URL_CONFIG="domain")
class TestResolveStepLink(TestCase):
    @classmethod
    def setUpTestData(cls):
        helpers.create_press()
        cls.journal_one, cls.journal_two = helpers.create_journals()
        setup_plugin()

        cls.article = helpers.create_article(
            cls.journal_one,
            title="Resolve Link Article",
        )

    def test_metadata_link(self):
        step = models.ChecklistStep.objects.create(
            journal=self.journal_one,
            label="Review metadata",
            link_type="metadata",
            order=1,
        )
        url = logic.resolve_step_link(step, self.article)
        self.assertEqual(url, reverse("edit_metadata", args=[self.article.pk]))

    def test_files_link(self):
        step = models.ChecklistStep.objects.create(
            journal=self.journal_one,
            label="Review files",
            link_type="files",
            order=2,
        )
        url = logic.resolve_step_link(step, self.article)
        self.assertEqual(
            url,
            reverse("document_management", args=[self.article.pk]),
        )

    def test_assign_editor_link(self):
        step = models.ChecklistStep.objects.create(
            journal=self.journal_one,
            label="Assign editor",
            link_type="assign_editor",
            order=3,
        )
        url = logic.resolve_step_link(step, self.article)
        self.assertEqual(url, "#assign-editor")

    def test_preprint_link_with_isolinear_url(self):
        step = models.ChecklistStep.objects.create(
            journal=self.journal_one,
            label="Create preprint",
            link_type="preprint",
            order=4,
        )
        url = logic.resolve_step_link(
            step,
            self.article,
            isolinear_url="/isolinear/123/",
        )
        self.assertEqual(url, "/isolinear/123/")

    def test_preprint_link_without_isolinear_falls_back(self):
        step = models.ChecklistStep.objects.create(
            journal=self.journal_one,
            label="Create preprint",
            link_type="preprint",
            order=5,
        )
        url = logic.resolve_step_link(step, self.article)
        self.assertEqual(
            url,
            reverse("document_management", args=[self.article.pk]),
        )

    def test_notify_vaes_link(self):
        step = models.ChecklistStep.objects.create(
            journal=self.journal_one,
            label="Notify all VAEs",
            link_type="notify_vaes",
            order=6,
        )
        url = logic.resolve_step_link(step, self.article)
        self.assertEqual(url, "#notify-status")

    def test_empty_link_type_returns_none(self):
        step = models.ChecklistStep.objects.create(
            journal=self.journal_one,
            label="Custom step",
            link_type="",
            order=7,
        )
        url = logic.resolve_step_link(step, self.article)
        self.assertIsNone(url)


@override_settings(URL_CONFIG="domain")
class TestGetChecklistWithCompletions(TestCase):
    @classmethod
    def setUpTestData(cls):
        helpers.create_press()
        cls.journal_one, cls.journal_two = helpers.create_journals()
        setup_plugin()

        cls.article = helpers.create_article(
            cls.journal_one,
            title="Checklist Completions Article",
        )

    def test_returns_all_steps_with_completion_state(self):
        models.ChecklistStep.objects.filter(journal=self.journal_one).delete()
        logic.ensure_default_checklist_steps(self.journal_one)

        result = logic.get_checklist_with_completions(
            self.journal_one,
            self.article,
        )
        self.assertEqual(len(result), 5)
        for item in result:
            self.assertIn("step", item)
            self.assertIn("completion", item)
            self.assertIn("completed", item)
            self.assertIn("link", item)
            self.assertFalse(item["completed"])

    def test_completed_step_reflected_in_result(self):
        models.ChecklistStep.objects.filter(journal=self.journal_one).delete()
        logic.ensure_default_checklist_steps(self.journal_one)
        first_step = models.ChecklistStep.objects.filter(
            journal=self.journal_one,
        ).first()
        models.ChecklistCompletion.objects.create(
            article=self.article,
            step=first_step,
            completed=True,
        )

        result = logic.get_checklist_with_completions(
            self.journal_one,
            self.article,
        )
        completed_items = [item for item in result if item["completed"]]
        self.assertEqual(len(completed_items), 1)
        self.assertEqual(completed_items[0]["step"].pk, first_step.pk)


@override_settings(URL_CONFIG="domain")
class TestChecklistStepFormSet(TestCase):
    @classmethod
    def setUpTestData(cls):
        helpers.create_press()
        cls.journal_one, cls.journal_two = helpers.create_journals()
        setup_plugin()

    def test_formset_can_save_new_step(self):
        existing = models.ChecklistStep.objects.filter(journal=self.journal_one)
        formset = forms.ChecklistStepFormSet(
            data={
                "form-TOTAL_FORMS": "1",
                "form-INITIAL_FORMS": "0",
                "form-MIN_NUM_FORMS": "0",
                "form-MAX_NUM_FORMS": "1000",
                "form-0-label": "New custom step",
                "form-0-help_text": "Help for custom step",
                "form-0-link_type": "",
                "form-0-order": "10",
                "form-0-active": "on",
            },
            queryset=existing,
        )
        self.assertTrue(formset.is_valid())
        steps = formset.save(commit=False)
        self.assertEqual(len(steps), 1)
        self.assertEqual(steps[0].label, "New custom step")


@override_settings(URL_CONFIG="domain")
class TestResetChecklistAction(TestCase):
    @classmethod
    def setUpTestData(cls):
        helpers.create_press()
        cls.journal_one, cls.journal_two = helpers.create_journals()
        setup_plugin()
        cls.editor = helpers.create_editor(cls.journal_one)

    def test_reset_replaces_custom_steps_with_defaults(self):
        models.ChecklistStep.objects.filter(journal=self.journal_one).delete()
        models.ChecklistStep.objects.create(
            journal=self.journal_one,
            label="Custom only step",
            order=1,
        )
        self.client.force_login(self.editor)
        response = self.client.post(
            reverse("vae_manager"),
            data={"reset_checklist": "1"},
            SERVER_NAME=self.journal_one.domain,
        )
        self.assertEqual(response.status_code, 302)
        labels = list(
            models.ChecklistStep.objects.filter(
                journal=self.journal_one,
            ).order_by("order").values_list("label", flat=True)
        )
        self.assertEqual(len(labels), 5)
        self.assertNotIn("Custom only step", labels)
        self.assertIn("Make Available for VAE Pool", labels)


@override_settings(URL_CONFIG="domain")
class TestChecklistToggleEndpoint(TestCase):
    @classmethod
    def setUpTestData(cls):
        helpers.create_press()
        cls.journal_one, cls.journal_two = helpers.create_journals()
        setup_plugin()

        cls.editor = helpers.create_editor(cls.journal_one)
        cls.author = helpers.create_user(
            "author-toggle@example.com",
            roles=["author"],
            journal=cls.journal_one,
            is_active=True,
        )
        cls.article = helpers.create_article(
            cls.journal_one,
            title="Toggle Checklist Article",
            stage=vae_plugin_settings.STAGE,
        )
        cls.step = models.ChecklistStep.objects.create(
            journal=cls.journal_one,
            label="Toggle Step",
            link_type="",
            order=1,
        )

    def test_toggle_creates_and_completes(self):
        self.client.force_login(self.editor)
        response = self.client.post(
            reverse(
                "vae_checklist_toggle",
                kwargs={
                    "step_id": self.step.pk,
                    "article_id": self.article.pk,
                },
            ),
            SERVER_NAME=self.journal_one.domain,
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 200)
        completion = models.ChecklistCompletion.objects.get(
            article=self.article,
            step=self.step,
        )
        self.assertTrue(completion.completed)

    def test_toggle_uncompletes_on_second_call(self):
        models.ChecklistCompletion.objects.create(
            article=self.article,
            step=self.step,
            completed=True,
            completed_by=self.editor,
            date_completed=timezone.now(),
        )
        self.client.force_login(self.editor)
        self.client.post(
            reverse(
                "vae_checklist_toggle",
                kwargs={
                    "step_id": self.step.pk,
                    "article_id": self.article.pk,
                },
            ),
            SERVER_NAME=self.journal_one.domain,
            HTTP_HX_REQUEST="true",
        )
        completion = models.ChecklistCompletion.objects.get(
            article=self.article,
            step=self.step,
        )
        self.assertFalse(completion.completed)

    def test_toggle_requires_editor(self):
        self.client.force_login(self.author)
        response = self.client.post(
            reverse(
                "vae_checklist_toggle",
                kwargs={
                    "step_id": self.step.pk,
                    "article_id": self.article.pk,
                },
            ),
            SERVER_NAME=self.journal_one.domain,
            HTTP_HX_REQUEST="true",
        )
        self.assertNotEqual(response.status_code, 200)


@override_settings(URL_CONFIG="domain")
class TestChecklistStepModel(TestCase):
    @classmethod
    def setUpTestData(cls):
        helpers.create_press()
        cls.journal_one, cls.journal_two = helpers.create_journals()
        setup_plugin()

    def test_checklist_step_str(self):
        step = models.ChecklistStep.objects.create(
            journal=self.journal_one,
            label="Test Label",
            order=1,
        )
        self.assertEqual(str(step), "{} — Test Label".format(self.journal_one.code))


@override_settings(URL_CONFIG="domain")
class TestChecklistCompletionModel(TestCase):
    @classmethod
    def setUpTestData(cls):
        helpers.create_press()
        cls.journal_one, cls.journal_two = helpers.create_journals()
        setup_plugin()

        cls.article = helpers.create_article(
            cls.journal_one,
            title="Completion Model Article",
        )
        cls.step = models.ChecklistStep.objects.create(
            journal=cls.journal_one,
            label="Completion Step",
            order=1,
        )

    def test_checklist_completion_str_pending(self):
        completion = models.ChecklistCompletion.objects.create(
            article=self.article,
            step=self.step,
            completed=False,
        )
        expected = 'Step "Completion Step" for article #{} (pending)'.format(
            self.article.pk,
        )
        self.assertEqual(str(completion), expected)

    def test_checklist_completion_str_done(self):
        completion = models.ChecklistCompletion.objects.create(
            article=self.article,
            step=self.step,
            completed=True,
        )
        expected = 'Step "Completion Step" for article #{} (done)'.format(
            self.article.pk,
        )
        self.assertEqual(str(completion), expected)

    def test_unique_together_constraint(self):
        models.ChecklistCompletion.objects.create(
            article=self.article,
            step=self.step,
            completed=False,
        )
        with self.assertRaises(IntegrityError):
            models.ChecklistCompletion.objects.create(
                article=self.article,
                step=self.step,
                completed=True,
            )
