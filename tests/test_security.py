import importlib

from django.conf import settings
from django.test import RequestFactory, TestCase, override_settings
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.urls import clear_url_caches, reverse

from utils.testing import helpers
from plugins.vae_workflow import models
from plugins.vae_workflow import plugin_settings as vae_plugin_settings
from plugins.vae_workflow.security import editor_or_vae_required


SENTINEL_BODY = b"ok"


def example_view(request, *args, **kwargs):
    return HttpResponse(SENTINEL_BODY)


@override_settings(URL_CONFIG="domain")
class TestEditorOrVAERequired(TestCase):
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
        cls.section_editor = helpers.create_section_editor(cls.journal_one)
        cls.staff_user = helpers.create_user(
            "staff@example.com",
            journal=cls.journal_one,
            is_staff=True,
            is_active=True,
        )
        cls.journal_manager = helpers.create_user(
            "jm@example.com",
            roles=["journal-manager"],
            journal=cls.journal_one,
            is_active=True,
        )
        cls.author = helpers.create_user(
            "author@example.com",
            roles=["author"],
            journal=cls.journal_one,
            is_active=True,
        )
        cls.vae_user = helpers.create_user(
            "vae@example.com",
            roles=["author"],
            journal=cls.journal_one,
            is_active=True,
        )
        models.VAEPoolMember.objects.create(
            journal=cls.journal_one,
            account=cls.vae_user,
            added_by=cls.editor,
        )
        cls.factory = RequestFactory()
        cls.url = reverse("vae_articles")

    def build_request(self, user):
        request = self.factory.get(self.url)
        request.user = user
        request.journal = self.journal_one
        return request

    def call_decorated_view(self, user):
        wrapped = editor_or_vae_required(example_view)
        return wrapped(self.build_request(user))

    def assert_allowed(self, user):
        response = self.call_decorated_view(user)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, SENTINEL_BODY)

    def test_editor_is_allowed(self):
        self.assert_allowed(self.editor)

    def test_section_editor_is_allowed(self):
        self.assert_allowed(self.section_editor)

    def test_staff_user_is_allowed(self):
        self.assert_allowed(self.staff_user)

    def test_journal_manager_is_allowed(self):
        self.assert_allowed(self.journal_manager)

    def test_vae_pool_member_is_allowed(self):
        self.assert_allowed(self.vae_user)

    def test_non_pool_non_editor_user_is_denied(self):
        with self.assertRaises(PermissionDenied):
            self.call_decorated_view(self.author)

    def test_pool_member_on_other_journal_is_denied(self):
        other_journal_pool_user = helpers.create_user(
            "other_pool@example.com",
            roles=["author"],
            journal=self.journal_two,
            is_active=True,
        )
        models.VAEPoolMember.objects.create(
            journal=self.journal_two,
            account=other_journal_pool_user,
            added_by=self.editor,
        )
        with self.assertRaises(PermissionDenied):
            self.call_decorated_view(other_journal_pool_user)

    def test_anonymous_user_is_redirected_to_login(self):
        response = self.call_decorated_view(AnonymousUser())
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("core_login"), response.url)

    def test_inactive_user_is_redirected_to_login(self):
        inactive = helpers.create_user(
            "inactive@example.com",
            roles=["editor"],
            journal=self.journal_one,
            is_active=False,
        )
        response = self.call_decorated_view(inactive)
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("core_login"), response.url)
