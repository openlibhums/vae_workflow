from events import logic as event_logic
from utils import plugins
from utils.install import update_settings

PLUGIN_NAME = 'VAE Workflow'
DESCRIPTION = 'Volunteer Associate Editor self-claiming workflow.'
AUTHOR = 'Open Library of Humanities'
VERSION = '0.1'
SHORT_NAME = 'vae_workflow'
DISPLAY_NAME = 'VAE Workflow'
MANAGER_URL = 'vae_manager'
JANEWAY_VERSION = '1.7.0'

IS_WORKFLOW_PLUGIN = True
JUMP_URL = 'vae_article'
HANDSHAKE_URL = 'vae_articles'
ARTICLE_PK_IN_HANDSHAKE_URL = True
STAGE = 'vae_claiming'
KANBAN_CARD = 'vae_workflow/elements/card.html'


class VAEWorkflowPlugin(plugins.Plugin):
    plugin_name = PLUGIN_NAME
    display_name = DISPLAY_NAME
    description = DESCRIPTION
    author = AUTHOR
    short_name = SHORT_NAME
    manager_url = MANAGER_URL
    version = VERSION
    janeway_version = JANEWAY_VERSION
    is_workflow_plugin = IS_WORKFLOW_PLUGIN
    stage = STAGE
    handshake_url = HANDSHAKE_URL
    article_pk_in_handshake_url = ARTICLE_PK_IN_HANDSHAKE_URL
    jump_url = JUMP_URL


def install():
    VAEWorkflowPlugin.install()
    update_settings(
        file_path='plugins/vae_workflow/install/settings.json',
    )
    register_for_events()


def hook_registry():
    return {}


def register_for_events():
    from plugins.vae_workflow import logic
    event_logic.Events.register_for_event(
        event_logic.Events.ON_ARTICLE_SUBMITTED,
        logic.create_pool_availability,
    )
