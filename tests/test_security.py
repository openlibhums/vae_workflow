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


@override_settings(URL_CONFIG="domain")
class TestArticlesViewIntegration(TestCase):
    """Integration tests hitting the actual vae_articles view via the
    test client, exercising the full middleware and decorator stack."""

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
        cls.vae_pool_section_editor = helpers.create_section_editor(
            cls.journal_one,
            email="vae_se@example.com",
        )
        models.VAEPoolMember.objects.create(
            journal=cls.journal_one,
            account=cls.vae_pool_section_editor,
            added_by=cls.editor,
        )
        cls.author = helpers.create_user(
            "author@example.com",
            roles=["author"],
            journal=cls.journal_one,
            is_active=True,
        )
        cls.url = reverse("vae_articles")

    def test_editor_can_access_articles_view(self):
        self.client.force_login(self.editor)
        response = self.client.get(
            self.url,
            SERVER_NAME=self.journal_one.domain,
        )
        self.assertEqual(response.status_code, 200)

    def test_section_editor_can_access_articles_view(self):
        self.client.force_login(self.section_editor)
        response = self.client.get(
            self.url,
            SERVER_NAME=self.journal_one.domain,
        )
        self.assertEqual(response.status_code, 200)

    def test_section_editor_in_pool_can_access_articles_view(self):
        self.client.force_login(self.vae_pool_section_editor)
        response = self.client.get(
            self.url,
            SERVER_NAME=self.journal_one.domain,
        )
        self.assertEqual(response.status_code, 200)

    def test_author_cannot_access_articles_view(self):
        self.client.force_login(self.author)
        response = self.client.get(
            self.url,
            SERVER_NAME=self.journal_one.domain,
        )
        self.assertEqual(response.status_code, 403)

    def test_section_editor_in_pool_sees_only_claiming_articles(self):
        from submission import models as submission_models
        article = helpers.create_article(
            self.journal_one,
            stage=vae_plugin_settings.STAGE,
        )
        models.ArticlePoolAvailability.objects.create(
            article=article,
            available=True,
            made_available_by=self.editor,
        )
        unassigned = helpers.create_article(
            self.journal_one,
            title="Unassigned Article",
            stage=vae_plugin_settings.STAGE,
        )
        models.ArticlePoolAvailability.objects.create(
            article=unassigned,
            available=False,
        )
        self.client.force_login(self.vae_pool_section_editor)
        response = self.client.get(
            self.url,
            SERVER_NAME=self.journal_one.domain,
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["is_editor"])
        self.assertIn(article, response.context["claiming_articles"])
        self.assertNotIn(
            unassigned,
            response.context.get("claiming_articles", []),
        )

    def test_editor_sees_unassigned_articles(self):
        self.client.force_login(self.editor)
        response = self.client.get(
            self.url,
            SERVER_NAME=self.journal_one.domain,
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["is_editor"])

    def test_section_editor_in_pool_can_access_article_detail(self):
        article = helpers.create_article(
            self.journal_one,
            stage=vae_plugin_settings.STAGE,
        )
        detail_url = reverse(
            "vae_article",
            kwargs={"article_id": article.pk},
        )
        self.client.force_login(self.vae_pool_section_editor)
        response = self.client.get(
            detail_url,
            SERVER_NAME=self.journal_one.domain,
        )
        self.assertEqual(response.status_code, 200)


@override_settings(URL_CONFIG="domain")
class TestHiddenRejectedVAENames(TestCase):
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
