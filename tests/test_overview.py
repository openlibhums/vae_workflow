import importlib

from django.conf import settings
from django.test import TestCase, override_settings
from django.urls import clear_url_caches, reverse

from utils.testing import helpers
from plugins.vae_workflow import models
from plugins.vae_workflow import plugin_settings as vae_plugin_settings


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
