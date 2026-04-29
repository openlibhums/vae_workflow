import importlib

from django.conf import settings
from django.test import TestCase, override_settings
from django.urls import clear_url_caches, reverse

from utils.testing import helpers
from plugins.vae_workflow import logic, models
from plugins.vae_workflow import plugin_settings as vae_plugin_settings


@override_settings(URL_CONFIG="domain")
class TestCreatePoolAvailability(TestCase):
    @classmethod
    def setUpTestData(cls):
        helpers.create_press()
        cls.journal_one, cls.journal_two = helpers.create_journals()
        helpers.create_roles(["editor", "author"])
        vae_plugin_settings.install()
        cls.article = helpers.create_article(cls.journal_one)

    def test_create_pool_availability_creates_record(self):
        models.ArticlePoolAvailability.objects.filter(
            article=self.article,
        ).delete()
        logic.create_pool_availability(self.article)
        self.assertTrue(
            models.ArticlePoolAvailability.objects.filter(
                article=self.article,
            ).exists()
        )

    def test_create_pool_availability_is_idempotent(self):
        models.ArticlePoolAvailability.objects.filter(
            article=self.article,
        ).delete()
        logic.create_pool_availability(self.article)
        logic.create_pool_availability(self.article)
        self.assertEqual(
            models.ArticlePoolAvailability.objects.filter(
                article=self.article,
            ).count(),
            1,
        )


@override_settings(URL_CONFIG="domain")
class TestArticleViewAvailability(TestCase):
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
        cls.assigned_editor = helpers.create_editor(
            cls.journal_one,
            email="assigned@example.com",
        )
        cls.article = helpers.create_article(cls.journal_one)
        cls.article_with_editor = helpers.create_article(
            cls.journal_one,
            title="Has Editor",
        )
        helpers.create_editor_assignment(
            cls.article_with_editor,
            cls.assigned_editor,
        )

    def article_url(self, article):
        return reverse(
            "vae_article",
            kwargs={"article_id": article.pk},
        )

    def test_article_view_creates_availability_if_missing(self):
        models.ArticlePoolAvailability.objects.filter(
            article=self.article,
        ).delete()
        self.client.force_login(self.editor)
        response = self.client.get(
            self.article_url(self.article),
            SERVER_NAME=self.journal_one.domain,
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            models.ArticlePoolAvailability.objects.filter(
                article=self.article,
            ).exists()
        )

    def test_make_available_blocked_without_editor(self):
        self.client.force_login(self.editor)
        response = self.client.post(
            self.article_url(self.article),
            data={"action": "make_available"},
            SERVER_NAME=self.journal_one.domain,
        )
        self.assertEqual(response.status_code, 302)
        availability = models.ArticlePoolAvailability.objects.get(
            article=self.article,
        )
        self.assertFalse(availability.available)

    def test_make_available_succeeds_with_editor_assigned(self):
        self.client.force_login(self.editor)
        response = self.client.post(
            self.article_url(self.article_with_editor),
            data={"action": "make_available"},
            SERVER_NAME=self.journal_one.domain,
        )
        self.assertEqual(response.status_code, 302)
        availability = models.ArticlePoolAvailability.objects.get(
            article=self.article_with_editor,
        )
        self.assertTrue(availability.available)
        self.assertEqual(availability.made_available_by, self.editor)
        self.assertIsNotNone(availability.date_made_available)


@override_settings(URL_CONFIG="domain")
class TestArticleIsClaimable(TestCase):
    @classmethod
    def setUpTestData(cls):
        helpers.create_press()
        cls.journal_one, cls.journal_two = helpers.create_journals()
        helpers.create_roles(["editor", "author"])
        vae_plugin_settings.install()

        cls.vae_user = helpers.create_user(
            "vae@example.com",
            journal=cls.journal_one,
            is_active=True,
        )
        models.VAEPoolMember.objects.create(
            journal=cls.journal_one,
            account=cls.vae_user,
        )
        cls.article = helpers.create_article(cls.journal_one)
        models.ArticlePoolAvailability.objects.get_or_create(
            article=cls.article,
        )

    def test_article_is_not_claimable_when_unavailable(self):
        availability = self.article.pool_availability
        availability.available = False
        availability.save()
        self.assertFalse(
            logic.article_is_claimable(
                self.article,
                self.vae_user,
                self.journal_one,
            )
        )

    def test_article_is_claimable_when_available(self):
        availability = self.article.pool_availability
        availability.available = True
        availability.save()
        self.assertTrue(
            logic.article_is_claimable(
                self.article,
                self.vae_user,
                self.journal_one,
            )
        )


@override_settings(URL_CONFIG="domain")
class TestArticlesViewSplit(TestCase):
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

        cls.unassigned_article = helpers.create_article(
            cls.journal_one,
            title="Unassigned Article",
        )
        cls.unassigned_article.stage = vae_plugin_settings.STAGE
        cls.unassigned_article.save()
        models.ArticlePoolAvailability.objects.get_or_create(
            article=cls.unassigned_article,
            defaults={"available": False},
        )

        cls.claiming_article = helpers.create_article(
            cls.journal_one,
            title="Claiming Article",
        )
        cls.claiming_article.stage = vae_plugin_settings.STAGE
        cls.claiming_article.save()
        availability, _ = models.ArticlePoolAvailability.objects.get_or_create(
            article=cls.claiming_article,
        )
        availability.available = True
        availability.save()

    def test_articles_view_splits_into_correct_buckets(self):
        self.client.force_login(self.editor)
        response = self.client.get(
            reverse("vae_articles"),
            SERVER_NAME=self.journal_one.domain,
        )
        self.assertEqual(response.status_code, 200)
        unassigned_ids = list(
            response.context["unassigned_articles"].values_list(
                "pk",
                flat=True,
            ),
        )
        claiming_ids = list(
            response.context["claiming_articles"].values_list(
                "pk",
                flat=True,
            ),
        )
        self.assertIn(self.unassigned_article.pk, unassigned_ids)
        self.assertNotIn(self.unassigned_article.pk, claiming_ids)
        self.assertIn(self.claiming_article.pk, claiming_ids)
        self.assertNotIn(self.claiming_article.pk, unassigned_ids)
