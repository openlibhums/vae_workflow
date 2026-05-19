from security.decorators import base_check_required, deny_access

from plugins.vae_workflow import logic


def editor_or_vae_required(func):
    """Allow access to editors, journal managers, staff, section editors,
    and members of the journal's VAE pool.

    Used for journal-wide VAE workflow listings where pool members must be
    able to see articles available to claim, even when they hold no editor
    role.
    """

    @base_check_required
    def wrapper(request, *args, **kwargs):
        user = request.user
        journal = getattr(request, "journal", None)

        if (
            user.is_staff
            or user.is_editor(request)
            or user.is_section_editor(request)
            or (journal and user.is_journal_manager(journal))
            or (journal and logic.user_is_in_pool(user, journal))
        ):
            return func(request, *args, **kwargs)

        deny_access(request)

    return wrapper
