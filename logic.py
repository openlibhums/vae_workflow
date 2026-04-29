from django.utils import timezone

from core.models import AccountRole
from utils import notify_helpers, render_template, setting_handler
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


def notify_rejected(request, claim):
    """Email the VAE when their claim is rejected."""
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


def confirm_claim(claim, confirmed_by):
    """
    Confirm a claim: reject all other pending claims for the same article,
    assign the VAE as section editor, and return the claim.
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


def confirmed_claim(article):
    """Return the confirmed claim for an article, if one exists."""
    return article.vae_claims.filter(status='confirmed').first()


def create_pool_availability(article, **kwargs):
    """
    Event handler for ON_ARTICLE_SUBMITTED.

    Creates an ArticlePoolAvailability record for the article so that
    editors can later mark it as available to the VAE pool. Idempotent.
    """
    models.ArticlePoolAvailability.objects.get_or_create(article=article)


def make_available_for_pool(article, editor, request):
    """
    Mark an article as available to the VAE pool, recording who did it
    and when, then notify all VAEs in the pool.
    """
    availability, _ = models.ArticlePoolAvailability.objects.get_or_create(
        article=article,
    )
    availability.available = True
    availability.made_available_by = editor
    availability.date_made_available = timezone.now()
    availability.save()
    notify_vaes_pool(request, article)
    return availability
