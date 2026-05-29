import importlib

from django.conf import settings
from django.db import IntegrityError
from django.test import TestCase, override_settings
from django.urls import clear_url_caches, reverse
from django.utils import timezone

from utils.testing import helpers
from plugins.vae_workflow import forms, logic, models
from plugins.vae_workflow import plugin_settings as vae_plugin_settings


@override_settings(URL_CONFIG="domain")
class TestEnsureDefaultChecklistSteps(TestCase):
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
        helpers.create_roles(
            ["editor", "section-editor", "journal-manager", "author"],
        )
        vae_plugin_settings.install()
        clear_url_caches()
        importlib.reload(importlib.import_module(settings.ROOT_URLCONF))
        importlib.reload(importlib.import_module("core.include_urls"))

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
        helpers.create_roles(
            ["editor", "section-editor", "journal-manager", "author"],
        )
        vae_plugin_settings.install()
        clear_url_caches()
        importlib.reload(importlib.import_module(settings.ROOT_URLCONF))
        importlib.reload(importlib.import_module("core.include_urls"))

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
        helpers.create_roles(
            ["editor", "section-editor", "journal-manager", "author"],
        )
        vae_plugin_settings.install()
        clear_url_caches()
        importlib.reload(importlib.import_module(settings.ROOT_URLCONF))
        importlib.reload(importlib.import_module("core.include_urls"))

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
        helpers.create_roles(
            ["editor", "section-editor", "journal-manager", "author"],
        )
        vae_plugin_settings.install()
        clear_url_caches()
        importlib.reload(importlib.import_module(settings.ROOT_URLCONF))
        importlib.reload(importlib.import_module("core.include_urls"))
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
        helpers.create_roles(
            ["editor", "section-editor", "journal-manager", "author"],
        )
        vae_plugin_settings.install()
        clear_url_caches()
        importlib.reload(importlib.import_module(settings.ROOT_URLCONF))
        importlib.reload(importlib.import_module("core.include_urls"))

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
        helpers.create_roles(
            ["editor", "section-editor", "journal-manager", "author"],
        )
        vae_plugin_settings.install()
        clear_url_caches()
        importlib.reload(importlib.import_module(settings.ROOT_URLCONF))
        importlib.reload(importlib.import_module("core.include_urls"))

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
        helpers.create_roles(
            ["editor", "section-editor", "journal-manager", "author"],
        )
        vae_plugin_settings.install()
        clear_url_caches()
        importlib.reload(importlib.import_module(settings.ROOT_URLCONF))
        importlib.reload(importlib.import_module("core.include_urls"))

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
