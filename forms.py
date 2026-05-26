from django import forms

from plugins.vae_workflow import models


class ClaimForm(forms.ModelForm):
    class Meta:
        model = models.EditorClaim
        fields = ('notes',)
        widgets = {
            'notes': forms.Textarea(attrs={'rows': 3}),
        }


class AccountChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return '{} ({})'.format(obj.full_name(), obj.email)


class AssignEditorForm(forms.Form):
    editor = AccountChoiceField(
        queryset=None,
        label='Editor',
    )

    def __init__(self, *args, article=None, journal=None, **kwargs):
        super().__init__(*args, **kwargs)
        from core.models import Account, AccountRole
        from review.models import EditorAssignment
        assigned_ids = EditorAssignment.objects.filter(
            article=article,
        ).values_list('editor_id', flat=True) if article else []
        editor_ids = AccountRole.objects.filter(
            journal=journal,
            role__slug='editor',
        ).values_list('user_id', flat=True)
        self.fields['editor'].queryset = Account.objects.filter(
            pk__in=editor_ids,
        ).exclude(
            pk__in=assigned_ids,
        ).order_by('last_name', 'first_name')


class AddPoolMemberForm(forms.Form):
    account = forms.ModelChoiceField(
        queryset=None,
        label='Section Editor',
        help_text='Select a section editor to add to the VAE pool.',
    )

    def __init__(self, *args, journal=None, **kwargs):
        super().__init__(*args, **kwargs)
        if journal:
            from core.models import Account, AccountRole
            already_in_pool = models.VAEPoolMember.objects.filter(
                journal=journal,
            ).values_list('account_id', flat=True)
            section_editor_ids = AccountRole.objects.filter(
                journal=journal,
                role__slug='section-editor',
            ).values_list('user_id', flat=True)
            self.fields['account'].queryset = Account.objects.filter(
                pk__in=section_editor_ids,
            ).exclude(
                pk__in=already_in_pool,
            ).order_by('last_name', 'first_name')
