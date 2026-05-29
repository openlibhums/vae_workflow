from django.urls import re_path

from plugins.vae_workflow import htmx, partial_views, views

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
        r'^checklist/(?P<step_id>\d+)/(?P<article_id>\d+)/toggle/$',
        htmx.checklist_toggle,
        name='vae_checklist_toggle',
    ),
    re_path(
        r'^checklist/(?P<step_id>\d+)/(?P<article_id>\d+)/click/$',
        htmx.checklist_track_click,
        name='vae_checklist_track_click',
    ),
    re_path(
        r'^checklist/(?P<article_id>\d+)/refresh/$',
        htmx.checklist_refresh,
        name='vae_checklist_refresh',
    ),
    re_path(
        r'^claim/(?P<claim_id>\d+)/reject-form/$',
        htmx.reject_claim_form,
        name='vae_reject_claim_form',
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
        r'^overview/$',
        views.overview,
        name='vae_overview',
    ),
    re_path(
        r'^articles/(?P<article_id>\d+)/$',
        views.article,
        name='vae_article',
    ),
]
