from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('journal', '0001_initial'),
        ('submission', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='VAEPoolMember',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('added', models.DateTimeField(default=django.utils.timezone.now)),
                ('account', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='vae_pool_memberships', to=settings.AUTH_USER_MODEL)),
                ('added_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='vae_pool_additions', to=settings.AUTH_USER_MODEL)),
                ('journal', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='journal.journal')),
            ],
            options={
                'ordering': ('account__last_name', 'account__first_name'),
                'unique_together': {('journal', 'account')},
            },
        ),
        migrations.CreateModel(
            name='EditorClaim',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date_claimed', models.DateTimeField(default=django.utils.timezone.now)),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('confirmed', 'Confirmed'), ('rejected', 'Rejected'), ('withdrawn', 'Withdrawn')], default='pending', max_length=20)),
                ('notes', models.TextField(blank=True, default='', help_text='Optional notes from the VAE about why they are claiming this article.')),
                ('date_resolved', models.DateTimeField(blank=True, null=True)),
                ('article', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='vae_claims', to='submission.article')),
                ('claimed_by', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='vae_claims_made', to=settings.AUTH_USER_MODEL)),
                ('resolved_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='vae_claims_resolved', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ('date_claimed',),
            },
        ),
    ]
