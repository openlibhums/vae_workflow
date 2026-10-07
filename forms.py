from django import forms
try:
    from tinymce.widgets import TinyMCE as RichTextWidget
except ImportError:
    from django_summernote.widgets import SummernoteWidget as RichTextWidget

from plugins.vae_workflow import models


class ClaimForm(forms.ModelForm):
    class Meta:
        model = models.EditorClaim
        fields = ('notes',)
        labels = {
            'notes': 'Conflicts of Interest',
        }
        help_texts = {
            'notes': (
                'Please declare any potential conflicts of interest you may '
                'have with this manuscript. Please add "None" if you do not '
                'have any.'
            ),
        }
        widgets = {
            'notes': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['notes'].required = True


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


class RejectClaimForm(forms.Form):
    message = forms.CharField(
        widget=RichTextWidget(attrs={'cols': 80, 'rows': 12}),
        label='Rejection message',
        help_text='This message will be emailed to the VAE.',
    )


class ChecklistStepForm(forms.ModelForm):
    class Meta:
        model = models.ChecklistStep
        fields = ('label', 'help_text', 'link_type', 'order', 'active')
        widgets = {
            'help_text': forms.TextInput(),
            'order': forms.NumberInput(attrs={'style': 'width:4rem'}),
        }


ChecklistStepFormSet = forms.modelformset_factory(
    models.ChecklistStep,
    form=ChecklistStepForm,
    extra=1,
    can_delete=True,
)
