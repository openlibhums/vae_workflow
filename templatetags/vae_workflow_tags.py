from django import template

from plugins.vae_workflow import logic, views

register = template.Library()


@register.simple_tag
def vae_dashboard_counts(journal):
    return views.dashboard_counts(journal)


@register.simple_tag
def vae_user_dashboard_counts(user, journal):
    return views.user_dashboard_counts(user, journal)


@register.simple_tag
def user_in_vae_pool(user, journal):
    return logic.user_is_in_pool(user, journal)
