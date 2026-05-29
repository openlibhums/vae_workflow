import importlib

from django.conf import settings
from django.test import TestCase, override_settings
from django.urls import clear_url_caches, reverse

from utils.testing import helpers
from plugins.vae_workflow import plugin_settings as vae_plugin_settings


@override_settings(URL_CONFIG="domain")
class TestIsolinearUrlContext(TestCase):
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
