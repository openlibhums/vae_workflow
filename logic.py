from django.utils import timezone

from core.models import AccountRole
from utils import models as utils_models, notify_helpers, render_template, setting_handler
from plugins.vae_workflow import models


def _get_setting(name, journal):
    return setting_handler.get_setting(
        'plugin:vae_workflow',
        name,
        journal,
    ).processed_value


def _journal_editors(journal):
    return AccountRole.objects.filter(
        journal=journal,
        role__slug='editor',
    ).select_related('user').values_list('user', flat=True)


def _send_email(request, setting_name, to, claim):
    template = _get_setting(setting_name, request.journal)
    context = {'claim': claim}
    body = render_template.get_message_content(
        request,
        context,
        template,
        template_is_setting=True,
    )
    log_dict = {
        'level': 'Info',
        'action_text': 'VAE Workflow: {}'.format(setting_name),
        'types': 'VAE Workflow',
        'actor': request.user,
        'target': claim.article,
    }
    notify_helpers.send_email_with_body_from_user(
        request=request,
        subject='[{}] VAE Claim — {}'.format(request.journal.code, claim.article.title),
        to=to,
        body=body,
        log_dict=log_dict,
    )


def notify_claim(request, claim):
    """Email journal editors when a VAE claims an article."""
    from core.models import Account
    editors = Account.objects.filter(
        accountrole__journal=request.journal,
        accountrole__role__slug='editor',
    )
    for editor in editors:
        _send_email(request, 'vae_claim_notification', editor.email, claim)


def notify_withdrawn(request, claim):
    """Email journal editors when a VAE withdraws their claim."""
    from core.models import Account
    editors = Account.objects.filter(
        accountrole__journal=request.journal,
        accountrole__role__slug='editor',
    )
    for editor in editors:
        _send_email(request, 'vae_withdrawn_notification', editor.email, claim)


def notify_confirmed(request, claim):
    """Email the VAE when their claim is confirmed."""
    _send_email(request, 'vae_confirmed_notification', claim.claimed_by.email, claim)


def notify_rejected(request, claim, custom_message=None):
    """Email the VAE when their claim is rejected."""
    if custom_message:
        log_dict = {
            'level': 'Info',
            'action_text': 'VAE Workflow: vae_rejected_notification',
            'types': 'VAE Workflow',
            'actor': request.user,
            'target': claim.article,
        }
        notify_helpers.send_email_with_body_from_user(
            request=request,
            subject='[{}] VAE Claim — {}'.format(request.journal.code, claim.article.title),
            to=claim.claimed_by.email,
            body=custom_message,
            log_dict=log_dict,
        )
    else:
        _send_email(request, 'vae_rejected_notification', claim.claimed_by.email, claim)


def allow_multiple_claims(journal):
    return setting_handler.get_setting(
        'plugin:vae_workflow',
        'allow_multiple_claims',
        journal,
    ).processed_value


def user_is_in_pool(user, journal):
    return models.VAEPoolMember.objects.filter(
        journal=journal,
        account=user,
    ).exists()


def get_active_claim(article):
    """Return the confirmed or most recent pending claim for an article."""
    confirmed = article.vae_claims.filter(status='confirmed').first()
    if confirmed:
        return confirmed
    return article.vae_claims.filter(status='pending').order_by('-date_claimed').first()


def article_is_claimable(article, user, journal):
    """
    Returns True if the user can claim the article.
    Rules:
    - The article must have been made available to the pool by an editor.
    - User must be in the VAE pool.
    - User must not already have a pending/confirmed claim on this article.
    - If allow_multiple_claims is False, no other pending claim may exist.
    """
    availability = getattr(article, 'pool_availability', None)
    if availability is None or not availability.available:
        return False
    if not user_is_in_pool(user, journal):
        return False
    if article.vae_claims.filter(claimed_by=user, status__in=('pending', 'confirmed')).exists():
        return False
    if not allow_multiple_claims(journal):
        if article.vae_claims.filter(status__in=('pending', 'confirmed')).exists():
            return False
    return True


def rescind_confirmed_claim(claim, rescinded_by):
    """
    Withdraw a confirmed claim and remove the VAE's editor assignment.
    Used both when a VAE rescinds their own claim and when an editor removes one.
    """
    from review.models import EditorAssignment
    claim.resolve('withdrawn', rescinded_by)
    EditorAssignment.objects.filter(
        article=claim.article,
        editor=claim.claimed_by,
    ).delete()


def ensure_review_round(article):
    """
    Create the first review round, as core's move_to_review does, so
    review views that look up the latest round do not fail.
    """
    from review.models import ReviewRound

    review_round, _ = ReviewRound.objects.get_or_create(
        article=article,
        round_number=1,
    )
    return review_round


def confirm_claim(claim, confirmed_by):
    """
    Confirm a claim: reject all other pending claims for the same article,
    assign the VAE as section editor, create the first review round and
    return the claim.
    """
    from review.models import EditorAssignment

    article = claim.article

    # Reject all other pending claims
    now = timezone.now()
    for other in article.vae_claims.filter(status='pending').exclude(pk=claim.pk):
        other.status = 'rejected'
        other.date_resolved = now
        other.resolved_by = confirmed_by
        other.save()

    # Confirm this claim
    claim.resolve('confirmed', confirmed_by)

    # Assign the VAE as section editor
    EditorAssignment.objects.get_or_create(
        article=article,
        editor=claim.claimed_by,
        defaults={'editor_type': 'section-editor'},
    )
    ensure_review_round(article)

    return claim


def notify_vaes_pool(request, article):
    """Email all VAEs in the pool that a new article is available for claiming."""
    pool = models.VAEPoolMember.objects.filter(journal=request.journal).select_related('account')
    template = _get_setting('vae_new_article_notification', request.journal)
    log_dict = {
        'level': 'Info',
        'action_text': 'VAE Workflow: new article notification sent',
        'types': 'VAE Workflow',
        'actor': request.user,
        'target': article,
    }
    notified_count = 0
    for member in pool:
        context = {'article': article, 'recipient': member.account}
        body = render_template.get_message_content(
            request, context, template, template_is_setting=True,
        )
        notify_helpers.send_email_with_body_from_user(
            request=request,
            subject='[{}] New preprint available — {}'.format(request.journal.code, article.title),
            to=member.account.email,
            body=body,
            log_dict=log_dict,
        )
        notified_count += 1

    utils_models.LogEntry.add_entry(
        types='VAE Workflow',
        description='Notified {} VAE pool member(s) that the article is available for claiming.'.format(
            notified_count,
        ),
        level='Info',
        actor=request.user,
        request=request,
        target=article,
    )

    availability = getattr(article, 'pool_availability', None)
    if availability:
        availability.date_last_notified = timezone.now()
        availability.save(update_fields=['date_last_notified'])


def confirmed_claim(article):
    """Return the confirmed claim for an article, if one exists."""
    return article.vae_claims.filter(status='confirmed').first()


def return_to_vae_after_pre_review_revision(revision, request=None, **kwargs):
    """
    Event handler for ON_REVISIONS_COMPLETE.

    "Request Pre-Review Revision" uses core's revision request, which moves
    the article to Under Revision. When the author submits, put the article
    back in the VAE stage it left, as long as the VAE stage was the last
    workflow element it entered and no VAE has claimed it since.
    """
    from core.models import WorkflowLog
    from submission.models import STAGE_UNDER_REVISION
    from plugins.vae_workflow import plugin_settings

    article = revision.article
    if article.stage != STAGE_UNDER_REVISION or confirmed_claim(article):
        return

    last_log = WorkflowLog.objects.filter(
        article=article,
    ).select_related('element').order_by('timestamp', 'pk').last()
    if not last_log or last_log.element.stage != plugin_settings.STAGE:
        return

    article.stage = plugin_settings.STAGE
    article.save()

    utils_models.LogEntry.add_entry(
        types='VAE Workflow',
        description='Returned to the VAE workflow after a pre-review revision.',
        level='Info',
        actor=request.user if request else None,
        request=request,
        target=article,
    )


def create_pool_availability(article, **kwargs):
    """
    Event handler for ON_ARTICLE_SUBMITTED.

    Creates an ArticlePoolAvailability record for the article so that
    editors can later mark it as available to the VAE pool. Idempotent.
    """
    models.ArticlePoolAvailability.objects.get_or_create(article=article)


def has_preprint(article):
    """Whether the article has a posted preprint (via Isolinear)."""
    return bool(getattr(article, 'preprint', None))


def make_available_for_pool(article, editor, request):
    """
    Mark an article as available to the VAE pool, recording who did it
    and when, then notify all VAEs in the pool.

    Refuses if no preprint has been posted via Isolinear yet — the preprint
    must be live online when the article is released to the pool.
    Returns the availability record on success, or None if blocked.
    """
    if not has_preprint(article):
        return None

    availability, _ = models.ArticlePoolAvailability.objects.get_or_create(
        article=article,
    )
    availability.available = True
    availability.made_available_by = editor
    now = timezone.now()
    availability.date_made_available = now
    availability.date_last_notified = now
    availability.save()
    notify_vaes_pool(request, article)
    return availability


DEFAULT_CHECKLIST_STEPS = [
    {'label': 'Review metadata', 'link_type': 'metadata', 'order': 1},
    {'label': 'Review files', 'link_type': 'files', 'order': 2},
    {'label': 'Assign Editor', 'link_type': 'assign_editor', 'order': 3},
    {'label': 'Create preprint', 'link_type': 'preprint', 'order': 4},
    {'label': 'Make Available for VAE Pool', 'link_type': 'notify_vaes', 'order': 5},
]


def ensure_default_checklist_steps(journal):
    if not models.ChecklistStep.objects.filter(journal=journal).exists():
        for step_data in DEFAULT_CHECKLIST_STEPS:
            models.ChecklistStep.objects.create(journal=journal, **step_data)
    return models.ChecklistStep.objects.filter(journal=journal, active=True)


def resolve_step_link(step, article, isolinear_url=None):
    from django.urls import reverse
    link_type = step.link_type
    if link_type == 'metadata':
        return reverse('edit_metadata', args=[article.pk])
    elif link_type == 'files':
        return reverse('document_management', args=[article.pk])
    elif link_type == 'assign_editor':
        return '#assign-editor'
    elif link_type == 'preprint':
        return isolinear_url or reverse('document_management', args=[article.pk])
    elif link_type == 'notify_vaes':
        return '#notify-status'
    return None


def get_step_auto_completed(step, article):
    """Return True/False if completion is system-derived, or None if manual."""
    if step.link_type == 'assign_editor':
        from review.models import EditorAssignment
        return EditorAssignment.objects.filter(article=article).exists()
    if step.link_type == 'notify_vaes':
        availability = getattr(article, 'pool_availability', None)
        return bool(availability and availability.available)
    return None


def get_checklist_with_completions(journal, article, isolinear_url=None):
    steps = ensure_default_checklist_steps(journal)
    completions = {
        c.step_id: c
        for c in models.ChecklistCompletion.objects.filter(
            article=article,
            step__in=steps,
        ).select_related('completed_by')
    }
    result = []
    for step in steps:
        completion = completions.get(step.pk)
        auto = get_step_auto_completed(step, article)
        if auto is not None:
            completed = auto
        else:
            completed = completion.completed if completion else False
        result.append({
            'step': step,
            'completion': completion,
            'completed': completed,
            'auto_completed': auto is not None,
            'link': resolve_step_link(step, article, isolinear_url),
        })
    return result
