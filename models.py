from django.conf import settings
from django.db import models
from django.utils import timezone


CLAIM_STATUS_CHOICES = (
    ('pending', 'Pending'),
    ('confirmed', 'Confirmed'),
    ('rejected', 'Rejected'),
    ('withdrawn', 'Withdrawn'),
)


class VAEPoolMember(models.Model):
    """Tracks which accounts are in the VAE pool for a given journal."""
    journal = models.ForeignKey(
        'journal.Journal',
        on_delete=models.CASCADE,
    )
    account = models.ForeignKey(
        'core.Account',
        on_delete=models.CASCADE,
        related_name='vae_pool_memberships',
    )
    added = models.DateTimeField(default=timezone.now)
    added_by = models.ForeignKey(
        'core.Account',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='vae_pool_additions',
    )

    class Meta:
        unique_together = ('journal', 'account')
        ordering = ('account__last_name', 'account__first_name')

    def __str__(self):
        return '{} — {}'.format(self.journal.code, self.account.full_name())


class EditorClaim(models.Model):
    """A VAE's claim on an article."""
    article = models.ForeignKey(
        'submission.Article',
        on_delete=models.CASCADE,
        related_name='vae_claims',
    )
    claimed_by = models.ForeignKey(
        'core.Account',
        on_delete=models.CASCADE,
        related_name='vae_claims_made',
    )
    date_claimed = models.DateTimeField(default=timezone.now)
    status = models.CharField(
        max_length=20,
        choices=CLAIM_STATUS_CHOICES,
        default='pending',
    )
    notes = models.TextField(
        blank=True,
        default='',
        help_text='Optional notes from the VAE about why they are claiming this article.',
    )
    date_resolved = models.DateTimeField(null=True, blank=True)
    resolved_by = models.ForeignKey(
        'core.Account',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='vae_claims_resolved',
    )

    class Meta:
        ordering = ('date_claimed',)

    def __str__(self):
        return 'Claim by {} on article #{} ({})'.format(
            self.claimed_by.full_name(),
            self.article.pk,
            self.status,
        )

    def resolve(self, status, resolved_by):
        self.status = status
        self.date_resolved = timezone.now()
        self.resolved_by = resolved_by
        self.save()


class ArticlePoolAvailability(models.Model):
    """Tracks whether an article has been made available to the VAE pool."""
    article = models.OneToOneField(
        'submission.Article',
        on_delete=models.CASCADE,
        related_name='pool_availability',
    )
    available = models.BooleanField(default=False)
    made_available_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='pool_availabilities_made',
    )
    date_made_available = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return 'Pool availability for article #{} ({})'.format(
            self.article_id,
            'available' if self.available else 'unassigned',
        )
