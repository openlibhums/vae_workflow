import importlib

from django.conf import settings
from django.test import TestCase, override_settings
from django.urls import clear_url_caches

from utils.testing import helpers
from plugins.vae_workflow import logic, models, views
from plugins.vae_workflow import plugin_settings as vae_plugin_settings


@override_settings(URL_CONFIG="domain")
class TestUserDashboardCounts(TestCase):
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

        cls.article_available = helpers.create_article(
            cls.journal_one,
            title="Available Article",
            stage=vae_plugin_settings.STAGE,
        )
        models.ArticlePoolAvailability.objects.create(
            article=cls.article_available,
            available=True,
            made_available_by=cls.editor,
        )

        cls.article_not_available = helpers.create_article(
            cls.journal_one,
            title="Not Available",
            stage=vae_plugin_settings.STAGE,
        )
        models.ArticlePoolAvailability.objects.create(
            article=cls.article_not_available,
            available=False,
        )

    def test_available_to_claim_counts_only_available_articles(self):
        counts = views.user_dashboard_counts(self.vae_user, self.journal_one)
        self.assertEqual(counts['available_to_claim'], 1)

    def test_available_excludes_articles_already_claimed_by_user(self):
        claim = models.EditorClaim.objects.create(
            article=self.article_available,
            claimed_by=self.vae_user,
            status='pending',
        )
        counts = views.user_dashboard_counts(self.vae_user, self.journal_one)
        self.assertEqual(counts['available_to_claim'], 0)
        claim.delete()

    def test_my_pending_counts_pending_claims(self):
        claim = models.EditorClaim.objects.create(
            article=self.article_available,
            claimed_by=self.vae_user,
            status='pending',
        )
        counts = views.user_dashboard_counts(self.vae_user, self.journal_one)
        self.assertEqual(counts['my_pending'], 1)
        self.assertEqual(counts['my_confirmed'], 0)
        claim.delete()

    def test_my_confirmed_counts_confirmed_claims(self):
        claim = models.EditorClaim.objects.create(
            article=self.article_available,
            claimed_by=self.vae_user,
            status='confirmed',
        )
        counts = views.user_dashboard_counts(self.vae_user, self.journal_one)
        self.assertEqual(counts['my_confirmed'], 1)
        self.assertEqual(counts['my_pending'], 0)
        claim.delete()

    def test_counts_are_zero_for_user_with_no_claims(self):
        counts = views.user_dashboard_counts(self.vae_user, self.journal_one)
        self.assertEqual(counts['my_pending'], 0)
        self.assertEqual(counts['my_confirmed'], 0)

    def test_rejected_claims_not_counted(self):
        claim = models.EditorClaim.objects.create(
            article=self.article_available,
            claimed_by=self.vae_user,
            status='rejected',
        )
        counts = views.user_dashboard_counts(self.vae_user, self.journal_one)
        self.assertEqual(counts['my_pending'], 0)
        self.assertEqual(counts['my_confirmed'], 0)
        self.assertEqual(counts['available_to_claim'], 1)
        claim.delete()

    def test_counts_scoped_to_journal(self):
        other_article = helpers.create_article(
            self.journal_two,
            title="Other Journal Article",
            stage=vae_plugin_settings.STAGE,
        )
        models.ArticlePoolAvailability.objects.create(
            article=other_article,
            available=True,
        )
        models.EditorClaim.objects.create(
            article=other_article,
            claimed_by=self.vae_user,
            status='pending',
        )
        counts = views.user_dashboard_counts(self.vae_user, self.journal_one)
        self.assertEqual(counts['available_to_claim'], 1)
        self.assertEqual(counts['my_pending'], 0)


@override_settings(URL_CONFIG="domain")
class TestUserInVaePoolTag(TestCase):
    @classmethod
    def setUpTestData(cls):
        helpers.create_press()
        cls.journal_one, cls.journal_two = helpers.create_journals()
        helpers.create_roles(["editor", "author"])
        cls.editor = helpers.create_editor(cls.journal_one)
        cls.pool_member = helpers.create_user(
            "pool@example.com",
            roles=["author"],
            journal=cls.journal_one,
            is_active=True,
        )
        models.VAEPoolMember.objects.create(
            journal=cls.journal_one,
            account=cls.pool_member,
            added_by=cls.editor,
        )
        cls.non_member = helpers.create_user(
            "notpool@example.com",
            roles=["author"],
            journal=cls.journal_one,
            is_active=True,
        )

    def test_pool_member_returns_true(self):
        self.assertTrue(logic.user_is_in_pool(self.pool_member, self.journal_one))

    def test_non_member_returns_false(self):
        self.assertFalse(logic.user_is_in_pool(self.non_member, self.journal_one))

    def test_member_on_other_journal_returns_false(self):
        self.assertFalse(logic.user_is_in_pool(self.pool_member, self.journal_two))


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
