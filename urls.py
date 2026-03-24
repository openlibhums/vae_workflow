from django.urls import re_path

from plugins.vae_workflow import partial_views, views

urlpatterns = [
    re_path(
        r'^pool/search/$',
        partial_views.pool_search,
        name='vae_pool_search',
    ),
    re_path(
        r'^pool/add/$',
        partial_views.pool_add,
        name='vae_pool_add',
    ),
    re_path(
        r'^$',
        views.manager,
        name='vae_manager',
    ),
    re_path(
        r'^articles/$',
        views.articles,
        name='vae_articles',
    ),
    re_path(
        r'^articles/(?P<article_id>\d+)/$',
        views.article,
        name='vae_article',
    ),
]
