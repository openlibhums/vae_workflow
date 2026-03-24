from django.db.models import Q
from django.shortcuts import render
from django.views.decorators.http import require_GET, require_POST

from core.models import Account, AccountRole
from security import decorators

from plugins.vae_workflow import htmx, models


@decorators.has_journal
@decorators.editor_user_required
@require_GET
def pool_search(request):
    query = request.GET.get('q', '').strip()
    results = []
    if query:
        already_in_pool = models.VAEPoolMember.objects.filter(
            journal=request.journal,
        ).values_list('account_id', flat=True)
        section_editor_ids = AccountRole.objects.filter(
            journal=request.journal,
            role__slug='section-editor',
        ).values_list('user_id', flat=True)
        results = Account.objects.filter(
            pk__in=section_editor_ids,
        ).exclude(
            pk__in=already_in_pool,
        ).filter(
            Q(first_name__icontains=query)
            | Q(last_name__icontains=query)
            | Q(email__icontains=query)
        ).order_by('last_name', 'first_name')[:20]
    return render(request, 'vae_workflow/partials/pool_search_results.html', {
        'results': results,
        'query': query,
    })


@decorators.has_journal
@decorators.editor_user_required
@require_POST
def pool_add(request):
    account_id = request.POST.get('account_id')
    try:
        account = Account.objects.get(pk=account_id)
        _, created = models.VAEPoolMember.objects.get_or_create(
            journal=request.journal,
            account=account,
            defaults={'added_by': request.user},
        )
        if created:
            msg = '{} added to the VAE pool.'.format(account.full_name())
            level = 'success'
        else:
            msg = '{} is already in the pool.'.format(account.full_name())
            level = 'info'
    except Account.DoesNotExist:
        msg = 'Account not found.'
        level = 'error'

    pool_members = models.VAEPoolMember.objects.filter(
        journal=request.journal,
    ).select_related('account', 'added_by')
    response = render(request, 'vae_workflow/partials/pool_table.html', {
        'pool_members': pool_members,
    })
    return htmx.hx_show_message(response, msg, level=level)
