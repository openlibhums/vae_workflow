import json

from django.shortcuts import get_object_or_404, redirect, render
from django.urls import NoReverseMatch, reverse
from django.utils import timezone
from django.views.decorators.http import require_POST, require_GET

from security import decorators
from submission import models as submission_models
from utils import render_template, setting_handler

from plugins.vae_workflow import forms, logic, models


def hx_show_message(response, message, level="success"):
    """Set HX-Trigger on a response to fire a toastr notification."""
    response["HX-Trigger"] = json.dumps(
        {"showMessage": {"type": level, "message": message}}
    )
    return response


@decorators.has_journal
@decorators.editor_user_required
@require_POST
def checklist_toggle(request, step_id, article_id):
    step = get_object_or_404(
        models.ChecklistStep,
        pk=step_id,
        journal=request.journal,
    )
    article = get_object_or_404(
        submission_models.Article,
        pk=article_id,
        journal=request.journal,
    )
    completion, _ = models.ChecklistCompletion.objects.get_or_create(
        article=article,
        step=step,
    )
    completion.completed = not completion.completed
    if completion.completed:
        completion.completed_by = request.user
        completion.date_completed = timezone.now()
    else:
        completion.completed_by = None
        completion.date_completed = None
    completion.save()

    isolinear_url = None
    try:
        from django.urls import reverse, NoReverseMatch
        isolinear_url = reverse(
            'isolinear_publish_preprint',
            kwargs={'article_id': article.pk},
        )
    except (NoReverseMatch, Exception):
        pass

    context = {
        'item': {
            'step': step,
            'completion': completion,
            'completed': completion.completed,
            'link': logic.resolve_step_link(step, article, isolinear_url),
        },
        'article': article,
    }
    return render(request, 'vae_workflow/elements/checklist_step.html', context)


@decorators.has_journal
@decorators.editor_user_required
@require_GET
def checklist_refresh(request, article_id):
    article = get_object_or_404(
        submission_models.Article,
        pk=article_id,
        journal=request.journal,
    )
    isolinear_url = None
    try:
        isolinear_url = reverse(
            'isolinear_publish_preprint',
            kwargs={'article_id': article.pk},
        )
    except NoReverseMatch:
        pass
    availability = getattr(article, 'pool_availability', None)
    checklist_items = logic.get_checklist_with_completions(
        request.journal,
        article,
        isolinear_url=isolinear_url,
    )
    return render(request, 'vae_workflow/elements/checklist_box.html', {
        'article': article,
        'availability': availability,
        'checklist_items': checklist_items,
    })


@decorators.has_journal
@decorators.editor_user_required
@require_GET
def checklist_track_click(request, step_id, article_id):
    step = get_object_or_404(
        models.ChecklistStep,
        pk=step_id,
        journal=request.journal,
    )
    article = get_object_or_404(
        submission_models.Article,
        pk=article_id,
        journal=request.journal,
    )
    completion, _ = models.ChecklistCompletion.objects.get_or_create(
        article=article,
        step=step,
    )
    if not completion.completed:
        completion.completed = True
        completion.completed_by = request.user
        completion.date_completed = timezone.now()
        completion.save()
    isolinear_url = None
    try:
        isolinear_url = reverse(
            'isolinear_publish_preprint',
            kwargs={'article_id': article.pk},
        )
    except NoReverseMatch:
        pass
    destination = logic.resolve_step_link(step, article, isolinear_url)
    if not destination or destination.startswith('#'):
        destination = reverse('vae_article', kwargs={'article_id': article.pk})
    return redirect(destination)


@decorators.has_journal
@decorators.editor_user_required
@require_GET
def reject_claim_form(request, claim_id):
    claim = get_object_or_404(
        models.EditorClaim,
        pk=claim_id,
        article__journal=request.journal,
        status='pending',
    )
    template_text = setting_handler.get_setting(
        'plugin:vae_workflow',
        'vae_rejected_notification',
        request.journal,
    ).processed_value
    context = {'claim': claim}
    default_message = render_template.get_message_content(
        request,
        context,
        template_text,
        template_is_setting=True,
    )
    form = forms.RejectClaimForm(initial={'message': default_message})
    return render(request, 'vae_workflow/elements/reject_form.html', {
        'claim': claim,
        'reject_form': form,
        'article': claim.article,
    })
