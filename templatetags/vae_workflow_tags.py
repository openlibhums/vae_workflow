from django import template

from plugins.vae_workflow import views

register = template.Library()


@register.simple_tag
def vae_dashboard_counts(journal):
    return views.dashboard_counts(journal)
