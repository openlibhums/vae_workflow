import importlib

from django.conf import settings
from django.test import TestCase, override_settings
from django.urls import clear_url_caches, reverse

from core import models as core_models
from review import models as review_models
from utils.testing import helpers
from plugins.vae_workflow import plugin_settings as vae_plugin_settings


@override_settings(URL_CONFIG="domain")
class TestVAEAssignEditor(TestCase):
    @classmethod
    def setUpTestData(cls):
        helpers.create_press()
        cls.journal_one, cls.journal_two = helpers.create_journals()
        helpers.create_roles(
            ["editor", "section-editor", "journal-manager", "author"],
        )
        vae_plugin_settings.VAEWorkflowPlugin.install()
        clear_url_caches()
        importlib.reload(importlib.import_module(settings.ROOT_URLCONF))
        importlib.reload(importlib.import_module("core.include_urls"))

        cls.editor = helpers.create_editor(cls.journal_one)
        cls.other_editor = helpers.create_editor(
            cls.journal_one,
            email="other_editor@example.com",
        )
        cls.section_editor = helpers.create_section_editor(cls.journal_one)
        cls.staff_user = helpers.create_user(
            "staff@example.com",
            journal=cls.journal_one,
            is_staff=True,
            is_active=True,
        )
        cls.journal_manager = helpers.create_user(
            "jm@example.com",
            roles=["journal-manager", "editor"],
            journal=cls.journal_one,
            is_active=True,
        )
        cls.assigning_editor = helpers.create_user(
            "assigning_editor@example.com",
            roles=["editor"],
            journal=cls.journal_one,
            is_active=True,
        )

        cls.article = helpers.create_article(cls.journal_one)
        cls.already_assigned_editor = helpers.create_editor(
            cls.journal_one,
            email="already_assigned@example.com",
        )
        helpers.create_editor_assignment(
            cls.article,
            cls.already_assigned_editor,
        )

    def assign_editor_url(self):
        return reverse(
            "vae_article",
            kwargs={"article_id": self.article.pk},
        )

    def test_editor_can_assign_editor(self):
        self.client.force_login(self.assigning_editor)
        response = self.client.post(
            self.assign_editor_url(),
            data={
                "action": "assign_editor",
                "editor_id": self.other_editor.pk,
            },
            SERVER_NAME=self.journal_one.domain,
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            review_models.EditorAssignment.objects.filter(
                article=self.article,
                editor=self.other_editor,
                editor_type="editor",
            ).exists()
        )

    def test_staff_can_assign_editor(self):
        self.client.force_login(self.staff_user)
        response = self.client.post(
            self.assign_editor_url(),
            data={
                "action": "assign_editor",
                "editor_id": self.other_editor.pk,
            },
            SERVER_NAME=self.journal_one.domain,
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            review_models.EditorAssignment.objects.filter(
                article=self.article,
                editor=self.other_editor,
                editor_type="editor",
            ).exists()
        )

    def test_journal_manager_can_assign_editor(self):
        self.client.force_login(self.journal_manager)
        response = self.client.post(
            self.assign_editor_url(),
            data={
                "action": "assign_editor",
                "editor_id": self.other_editor.pk,
            },
            SERVER_NAME=self.journal_one.domain,
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            review_models.EditorAssignment.objects.filter(
                article=self.article,
                editor=self.other_editor,
                editor_type="editor",
            ).exists()
        )

    def test_section_editor_cannot_assign_editor(self):
        existing_assignments = set(
            review_models.EditorAssignment.objects.filter(
                article=self.article,
            ).values_list("editor_id", flat=True),
        )
        self.client.force_login(self.section_editor)
        self.client.post(
            self.assign_editor_url(),
            data={
                "action": "assign_editor",
                "editor_id": self.other_editor.pk,
            },
            SERVER_NAME=self.journal_one.domain,
        )
        post_assignments = set(
            review_models.EditorAssignment.objects.filter(
                article=self.article,
            ).values_list("editor_id", flat=True),
        )
        self.assertEqual(existing_assignments, post_assignments)

    def test_already_assigned_editor_excluded_from_available(self):
        self.client.force_login(self.assigning_editor)
        response = self.client.get(
            self.assign_editor_url(),
            SERVER_NAME=self.journal_one.domain,
        )
        self.assertEqual(response.status_code, 200)
        available_editor_ids = list(
            response.context["available_editors"].values_list(
                "user_id",
                flat=True,
            ),
        )
        self.assertNotIn(
            self.already_assigned_editor.pk,
            available_editor_ids,
        )
        self.assertIn(
            self.other_editor.pk,
            available_editor_ids,
        )

    def test_assign_editor_rejects_non_editor_user(self):
        non_editor = helpers.create_user(
            "non_editor@example.com",
            roles=["author"],
            journal=self.journal_one,
            is_active=True,
        )
        self.client.force_login(self.assigning_editor)
        response = self.client.post(
            self.assign_editor_url(),
            data={
                "action": "assign_editor",
                "editor_id": non_editor.pk,
            },
            SERVER_NAME=self.journal_one.domain,
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(
            review_models.EditorAssignment.objects.filter(
                article=self.article,
                editor=non_editor,
            ).exists(),
        )
