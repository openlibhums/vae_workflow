from django.shortcuts import render, get_object_or_404, redirect, reverse
from django.contrib import messages
from django.contrib.auth.decorators import login_required

from events import logic as event_logic
from security import decorators
from submission import models as submission_models

from plugins.vae_workflow import forms, logic, models, plugin_settings


@decorators.has_journal
@decorators.editor_user_required
def manager(request):
    """Plugin settings and VAE pool management."""
    pool_members = models.VAEPoolMember.objects.filter(
        journal=request.journal,
    ).select_related('account', 'added_by')

    add_form = forms.AddPoolMemberForm(journal=request.journal)

    if request.method == 'POST':
        if 'add_member' in request.POST:
            add_form = forms.AddPoolMemberForm(
                request.POST,
                journal=request.journal,
            )
            if add_form.is_valid():
                account = add_form.cleaned_data['account']
                models.VAEPoolMember.objects.get_or_create(
                    journal=request.journal,
                    account=account,
                    defaults={'added_by': request.user},
                )
                messages.success(
                    request,
                    '{} added to the VAE pool.'.format(account.full_name()),
                )
                return redirect(reverse('vae_manager'))

        elif 'remove_member' in request.POST:
            member_id = request.POST.get('remove_member')
            try:
                member = models.VAEPoolMember.objects.get(
                    pk=member_id,
                    journal=request.journal,
                )
                name = member.account.full_name()
                member.delete()
                messages.success(
                    request,
                    '{} removed from the VAE pool.'.format(name),
                )
            except models.VAEPoolMember.DoesNotExist:
                messages.error(request, 'Pool member not found.')
            return redirect(reverse('vae_manager'))

    template = 'vae_workflow/manager.html'
    context = {
        'pool_members': pool_members,
        'add_form': add_form,
    }
    return render(request, template, context)


VAE_VISIBLE_STAGES = [
    plugin_settings.STAGE,
    submission_models.STAGE_UNASSIGNED,
    submission_models.STAGE_ASSIGNED,
    submission_models.STAGE_UNDER_REVIEW,
    submission_models.STAGE_UNDER_REVISION,
]


@decorators.has_journal
@decorators.editor_user_required
def articles(request):
    """
    HANDSHAKE_URL — lists articles relevant to the VAE workflow.

    Shows articles in the VAE claiming stage or any review/revision stage
    that do not yet have a confirmed VAE claim.

    VAEs in the pool see articles available to claim plus their own claims.
    Non-pool editors (HE) see all articles with their claim summaries.
    """
    confirmed_article_ids = models.EditorClaim.objects.filter(
        article__journal=request.journal,
        status='confirmed',
    ).values_list('article_id', flat=True)

    articles_in_stage = submission_models.Article.objects.filter(
        journal=request.journal,
        stage__in=VAE_VISIBLE_STAGES,
    ).exclude(
        pk__in=confirmed_article_ids,
    ).prefetch_related('vae_claims')

    user_in_pool = logic.user_is_in_pool(request.user, request.journal)

    template = 'vae_workflow/articles.html'
    context = {
        'articles_in_stage': articles_in_stage,
        'user_in_pool': user_in_pool,
    }
    return render(request, template, context)


@decorators.has_journal
@decorators.editor_user_required
def article(request, article_id):
    """
    JUMP_URL — claim management page for a single article.

    VAEs can claim or withdraw. HE can confirm or reject individual claims.
    When HE confirms, the VAE is assigned as section editor and the workflow advances.
    """
    article_obj = get_object_or_404(
        submission_models.Article,
        pk=article_id,
        journal=request.journal,
    )

    in_claiming_stage = article_obj.stage == plugin_settings.STAGE
    claimable_stage = article_obj.stage in VAE_VISIBLE_STAGES
    claims = article_obj.vae_claims.select_related('claimed_by', 'resolved_by')
    user_claim = (
        claims.filter(claimed_by=request.user, status='confirmed').first()
        or claims.filter(claimed_by=request.user, status='pending').first()
        or claims.filter(claimed_by=request.user).order_by('-date_claimed').first()
    )
    user_in_pool = logic.user_is_in_pool(request.user, request.journal)
    can_claim = logic.article_is_claimable(article_obj, request.user, request.journal)
    existing_claim = logic.confirmed_claim(article_obj)

    claim_form = forms.ClaimForm()

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'advance' and existing_claim and in_claiming_stage:
            messages.success(
                request,
                'Article advancing to next stage with {} as handling editor.'.format(
                    existing_claim.claimed_by.full_name()
                ),
            )
            kwargs = {
                'handshake_url': 'vae_articles',
                'request': request,
                'article': article_obj,
                'switch_stage': True,
            }
            return event_logic.Events.raise_event(
                event_logic.Events.ON_WORKFLOW_ELEMENT_COMPLETE,
                task_object=article_obj,
                **kwargs,
            )

        elif action == 'reset' and existing_claim:
            logic.rescind_confirmed_claim(existing_claim, request.user)
            messages.success(
                request,
                'Claim removed. The article is now open for claiming.',
            )
            return redirect(reverse('vae_article', kwargs={'article_id': article_id}))

        elif action == 'rescind':
            if user_claim and user_claim.status == 'confirmed':
                logic.rescind_confirmed_claim(user_claim, request.user)
                messages.success(
                    request,
                    'Your claim has been rescinded.',
                )
                return redirect(reverse('vae_article', kwargs={'article_id': article_id}))

        elif action == 'claim' and can_claim and claimable_stage:
            claim_form = forms.ClaimForm(request.POST)
            if claim_form.is_valid():
                new_claim = claim_form.save(commit=False)
                new_claim.article = article_obj
                new_claim.claimed_by = request.user
                new_claim.save()
                logic.notify_claim(request, new_claim)
                messages.success(request, 'You have claimed this article.')
                return redirect(reverse('vae_article', kwargs={'article_id': article_id}))

        elif action == 'withdraw':
            if user_claim and user_claim.status == 'pending':
                user_claim.resolve('withdrawn', request.user)
                logic.notify_withdrawn(request, user_claim)
                messages.success(request, 'Your claim has been withdrawn.')
                return redirect(reverse('vae_article', kwargs={'article_id': article_id}))

        elif action == 'confirm' and claimable_stage:
            claim_id = request.POST.get('claim_id')
            try:
                claim_to_confirm = article_obj.vae_claims.get(
                    pk=claim_id,
                    status='pending',
                )
                # Collect other pending claimants before confirm_claim rejects them
                other_pending = list(
                    article_obj.vae_claims.filter(status='pending').exclude(pk=claim_to_confirm.pk)
                )
                logic.confirm_claim(claim_to_confirm, request.user)
                logic.notify_confirmed(request, claim_to_confirm)
                for other in other_pending:
                    other.refresh_from_db()
                    logic.notify_rejected(request, other)
                messages.success(
                    request,
                    '{} confirmed as handling editor. Article advancing to next stage.'.format(
                        claim_to_confirm.claimed_by.full_name()
                    ),
                )
                # Advance the workflow
                kwargs = {
                    'handshake_url': 'vae_articles',
                    'request': request,
                    'article': article_obj,
                    'switch_stage': True,
                }
                return event_logic.Events.raise_event(
                    event_logic.Events.ON_WORKFLOW_ELEMENT_COMPLETE,
                    task_object=article_obj,
                    **kwargs,
                )
            except models.EditorClaim.DoesNotExist:
                messages.error(request, 'Claim not found.')
                return redirect(reverse('vae_article', kwargs={'article_id': article_id}))

        elif action == 'notify_vaes' and in_claiming_stage:
            logic.notify_vaes_pool(request, article_obj)
            messages.success(request, 'All VAEs in the pool have been notified.')
            return redirect(reverse('vae_article', kwargs={'article_id': article_id}))

        elif action == 'reject':
            claim_id = request.POST.get('claim_id')
            try:
                claim_to_reject = article_obj.vae_claims.get(
                    pk=claim_id,
                    status='pending',
                )
                claim_to_reject.resolve('rejected', request.user)
                logic.notify_rejected(request, claim_to_reject)
                messages.success(
                    request,
                    'Claim from {} rejected.'.format(claim_to_reject.claimed_by.full_name()),
                )
            except models.EditorClaim.DoesNotExist:
                messages.error(request, 'Claim not found.')
            return redirect(reverse('vae_article', kwargs={'article_id': article_id}))

    template = 'vae_workflow/article.html'
    context = {
        'article': article_obj,
        'in_claiming_stage': in_claiming_stage,
        'claimable_stage': claimable_stage,
        'claims': claims,
        'user_claim': user_claim,
        'user_in_pool': user_in_pool,
        'can_claim': can_claim,
        'claim_form': claim_form,
        'existing_claim': existing_claim,
    }
    return render(request, template, context)
